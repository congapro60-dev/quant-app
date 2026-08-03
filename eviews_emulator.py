import ast
import html as html_lib
import re
import pandas as pd
import statsmodels.api as sm
import numpy as np
from statsmodels.stats.stattools import jarque_bera, durbin_watson
from statsmodels.stats.diagnostic import het_white, acorr_breusch_godfrey, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor

try:
    from statsmodels.tsa.stattools import adfuller
except Exception:
    adfuller = None


# ==================== TIỆN ÍCH ====================
MAX_COMMAND_LENGTH = 2_000
MAX_FORMULA_LENGTH = 1_000
MAX_AST_NODES = 128
MAX_AST_DEPTH = 20
MAX_FUNCTION_CALLS = 32
MAX_LAG = 2_520
MAX_POWER_EXPONENT = 10
MAX_LS_TERMS = 50
MAX_ANALYSIS_ROWS = 100_000
MAX_ANALYSIS_COLUMNS = 256
_GENR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class ExpressionValidationError(ValueError):
    """Raised when an EViews-like expression is unsafe or too complex."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _casefold_column_map(df):
    mapping = {}
    for column in df.columns:
        label = str(column)
        key = label.upper()
        if key in mapping and mapping[key] != column:
            raise ExpressionValidationError(
                "AMBIGUOUS_COLUMN",
                f"Tên cột '{label}' bị trùng khi so sánh không phân biệt hoa/thường.",
            )
        mapping[key] = column
    return mapping


def _find_col(df, name):
    return _casefold_column_map(df).get(name.strip().upper())


def _validate_expression_tree(tree):
    node_count = 0
    call_count = 0
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        node_count += 1
        if node_count > MAX_AST_NODES:
            raise ExpressionValidationError(
                "EXPRESSION_TOO_COMPLEX",
                f"Biểu thức vượt giới hạn {MAX_AST_NODES} nút cú pháp.",
            )
        if depth > MAX_AST_DEPTH:
            raise ExpressionValidationError(
                "EXPRESSION_TOO_DEEP",
                f"Biểu thức vượt độ sâu tối đa {MAX_AST_DEPTH}.",
            )
        if isinstance(node, ast.Call):
            call_count += 1
            if call_count > MAX_FUNCTION_CALLS:
                raise ExpressionValidationError(
                    "TOO_MANY_FUNCTION_CALLS",
                    f"Biểu thức vượt giới hạn {MAX_FUNCTION_CALLS} lời gọi hàm.",
                )
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _reject_infinite(value):
    try:
        values = np.asarray(value)
        if np.issubdtype(values.dtype, np.number) and bool(np.isinf(values).any()):
            raise ExpressionValidationError(
                "NON_FINITE_RESULT", "Biểu thức tạo ra giá trị vô cực."
            )
    except TypeError:
        pass
    return value


class _SafeSeriesEvaluator:
    """Small allowlisted AST interpreter; it never compiles or executes code."""

    def __init__(self, namespace):
        self.namespace = namespace

    def evaluate(self, node):
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return node.value
            if not isinstance(node.value, (int, float)):
                raise ExpressionValidationError(
                    "UNSUPPORTED_LITERAL", "Chỉ hỗ trợ hằng số số hoặc logic."
                )
            if not np.isfinite(node.value) or abs(node.value) > 1e15:
                raise ExpressionValidationError(
                    "INVALID_LITERAL", "Hằng số không hữu hạn hoặc quá lớn."
                )
            return node.value
        if isinstance(node, ast.Name):
            try:
                return self.namespace[node.id.upper()]
            except KeyError as exc:
                raise ExpressionValidationError(
                    "UNKNOWN_VARIABLE", f"Không tìm thấy biến '{node.id}'."
                ) from exc
        if isinstance(node, ast.UnaryOp):
            operand = self.evaluate(node.operand)
            if isinstance(node.op, ast.UAdd):
                result = +operand
            elif isinstance(node.op, ast.USub):
                result = -operand
            elif isinstance(node.op, ast.Not):
                result = np.logical_not(operand)
            else:
                raise ExpressionValidationError(
                    "UNSUPPORTED_OPERATOR", "Toán tử một ngôi không được hỗ trợ."
                )
            return _reject_infinite(result)
        if isinstance(node, ast.BinOp):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            try:
                with np.errstate(all="ignore"):
                    if isinstance(node.op, ast.Add):
                        result = left + right
                    elif isinstance(node.op, ast.Sub):
                        result = left - right
                    elif isinstance(node.op, ast.Mult):
                        result = left * right
                    elif isinstance(node.op, ast.Div):
                        result = left / right
                    elif isinstance(node.op, ast.Pow):
                        if not np.isscalar(right) or isinstance(right, (bool, np.bool_)):
                            raise ExpressionValidationError(
                                "UNBOUNDED_POWER", "Số mũ phải là một hằng số hữu hạn."
                            )
                        if not np.isfinite(right) or abs(float(right)) > MAX_POWER_EXPONENT:
                            raise ExpressionValidationError(
                                "UNBOUNDED_POWER",
                                f"Trị tuyệt đối số mũ không được vượt {MAX_POWER_EXPONENT}.",
                            )
                        result = left ** right
                    elif isinstance(node.op, ast.BitAnd):
                        result = np.logical_and(left, right)
                    elif isinstance(node.op, ast.BitOr):
                        result = np.logical_or(left, right)
                    else:
                        raise ExpressionValidationError(
                            "UNSUPPORTED_OPERATOR", "Toán tử hai ngôi không được hỗ trợ."
                        )
            except ExpressionValidationError:
                raise
            except (ArithmeticError, TypeError, ValueError) as exc:
                raise ExpressionValidationError(
                    "ARITHMETIC_ERROR", "Không thể thực hiện phép toán trong biểu thức."
                ) from exc
            return _reject_infinite(result)
        if isinstance(node, ast.BoolOp):
            values = [self.evaluate(value) for value in node.values]
            if not values:
                raise ExpressionValidationError(
                    "INVALID_BOOLEAN", "Biểu thức logic không hợp lệ."
                )
            result = values[0]
            operation = np.logical_and if isinstance(node.op, ast.And) else np.logical_or
            for value in values[1:]:
                result = operation(result, value)
            return result
        if isinstance(node, ast.Compare):
            left = self.evaluate(node.left)
            result = True
            operations = {
                ast.Eq: lambda a, b: a == b,
                ast.NotEq: lambda a, b: a != b,
                ast.Lt: lambda a, b: a < b,
                ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b,
                ast.GtE: lambda a, b: a >= b,
            }
            for operator, comparator in zip(node.ops, node.comparators):
                right = self.evaluate(comparator)
                operation = operations.get(type(operator))
                if operation is None:
                    raise ExpressionValidationError(
                        "UNSUPPORTED_COMPARISON", "Phép so sánh không được hỗ trợ."
                    )
                result = np.logical_and(result, operation(left, right))
                left = right
            return result
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionValidationError(
                    "UNSUPPORTED_CALL", "Chỉ cho phép gọi hàm phân tích đã định danh."
                )
            if len(node.args) != 1 or node.keywords:
                raise ExpressionValidationError(
                    "INVALID_FUNCTION_ARGUMENTS", "Hàm phân tích nhận đúng một đối số."
                )
            name = node.func.id.upper()
            argument = self.evaluate(node.args[0])
            with np.errstate(all="ignore"):
                if name == "LOG":
                    values = np.asarray(argument)
                    if bool(np.less_equal(values, 0).any()):
                        raise ExpressionValidationError(
                            "FUNCTION_DOMAIN", "LOG chỉ nhận giá trị dương."
                        )
                    result = np.log(argument)
                elif name == "EXP":
                    result = np.exp(argument)
                elif name == "ABS":
                    result = np.abs(argument)
                elif name in ("SQR", "SQRT"):
                    values = np.asarray(argument)
                    if bool(np.less(values, 0).any()):
                        raise ExpressionValidationError(
                            "FUNCTION_DOMAIN", "SQRT/SQR không nhận giá trị âm."
                        )
                    result = np.sqrt(argument)
                elif name == "D":
                    if np.isscalar(argument):
                        raise ExpressionValidationError(
                            "FUNCTION_DOMAIN", "D cần một chuỗi dữ liệu."
                        )
                    result = pd.Series(argument).diff()
                else:
                    raise ExpressionValidationError(
                        "UNKNOWN_FUNCTION", f"Hàm '{node.func.id}' không được hỗ trợ."
                    )
            return _reject_infinite(result)
        raise ExpressionValidationError(
            "UNSUPPORTED_SYNTAX",
            f"Cú pháp '{type(node).__name__}' không được hỗ trợ.",
        )


def eviews_expr_to_series(formula, df):
    """
    Dịch biểu thức kiểu Eviews sang pandas Series.
    Hỗ trợ: + - * / ** , LOG(), EXP(), ABS(), SQR()/SQRT(), D() (sai phân),
    biến trễ VAR(-k), @TREND, và biểu thức so sánh (tạo biến giả).
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ExpressionValidationError("INVALID_DATA", "Bảng dữ liệu đang trống.")
    if len(df) > MAX_ANALYSIS_ROWS or df.shape[1] > MAX_ANALYSIS_COLUMNS:
        raise ExpressionValidationError(
            "DATA_TOO_LARGE", "Bảng dữ liệu vượt giới hạn phân tích tương tác."
        )
    if not isinstance(formula, str):
        raise ExpressionValidationError("INVALID_EXPRESSION", "Biểu thức phải là văn bản.")
    f = formula.strip()
    if not f:
        raise ExpressionValidationError("EMPTY_EXPRESSION", "Biểu thức đang trống.")
    if len(f) > MAX_FORMULA_LENGTH:
        raise ExpressionValidationError(
            "EXPRESSION_TOO_LONG",
            f"Biểu thức vượt giới hạn {MAX_FORMULA_LENGTH} ký tự.",
        )
    work = df.copy()
    column_map = _casefold_column_map(work)
    namespace = {
        str(key).upper(): pd.to_numeric(work[column], errors="coerce")
        for key, column in column_map.items()
    }

    # @TREND -> chuỗi 0,1,2,...
    if '@TREND' in f.upper():
        trend_name = "_QV_INTERNAL_TREND"
        while trend_name in namespace:
            trend_name += "_"
        namespace[trend_name] = pd.Series(
            np.arange(len(work), dtype=float), index=work.index
        )
        f = re.sub(r"@TREND\b", trend_name, f, flags=re.I)

    # Biến trễ VAR(-k)
    lag_counter = 0

    def _lag(match):
        nonlocal lag_counter
        name, lag = match.group(1), int(match.group(2))
        column = column_map.get(name.upper())
        if column is None:
            raise ExpressionValidationError(
                "UNKNOWN_VARIABLE", f"Không tìm thấy biến '{name}' để lấy trễ."
            )
        if not 1 <= lag <= MAX_LAG:
            raise ExpressionValidationError(
                "INVALID_LAG", f"Độ trễ phải từ 1 đến {MAX_LAG}."
            )
        placeholder = f"_QV_INTERNAL_LAG_{lag_counter}"
        while placeholder in namespace:
            lag_counter += 1
            placeholder = f"_QV_INTERNAL_LAG_{lag_counter}"
        lag_counter += 1
        namespace[placeholder] = pd.to_numeric(work[column], errors="coerce").shift(lag)
        return placeholder

    f = re.sub(r"\b([A-Za-z_]\w*)\s*\(\s*-\s*(\d+)\s*\)", _lag, f)
    try:
        tree = ast.parse(f, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ExpressionValidationError(
            "INVALID_SYNTAX", "Biểu thức có cú pháp không hợp lệ."
        ) from exc
    _validate_expression_tree(tree)
    value = _SafeSeriesEvaluator(namespace).evaluate(tree)
    if np.isscalar(value):
        result = pd.Series(value, index=work.index)
    elif isinstance(value, pd.Series):
        result = value.reindex(work.index)
    else:
        array = np.asarray(value)
        if array.ndim != 1 or len(array) != len(work):
            raise ExpressionValidationError(
                "INVALID_RESULT_SHAPE", "Biểu thức không trả về một chuỗi đúng độ dài."
            )
        result = pd.Series(array, index=work.index)
    if pd.api.types.is_bool_dtype(result.dtype):
        result = result.astype(int)
    else:
        result = pd.to_numeric(result, errors="coerce")
    if bool(np.isinf(result.to_numpy(dtype=float, na_value=np.nan)).any()):
        raise ExpressionValidationError(
            "NON_FINITE_RESULT", "Biểu thức tạo ra giá trị vô cực."
        )
    return result


# ==================== BỘ PHÂN TÍCH LỆNH ====================
def parse_and_execute_command(command, data_df):
    if not isinstance(command, str):
        return {"error": "Lệnh phải là văn bản."}
    command = command.strip()
    if not command:
        return {"error": "Lệnh trống."}
    if len(command) > MAX_COMMAND_LENGTH:
        return {"error": f"Lệnh vượt giới hạn {MAX_COMMAND_LENGTH} ký tự."}
    if not isinstance(data_df, pd.DataFrame) or data_df.empty:
        return {"error": "Bảng dữ liệu đang trống hoặc không hợp lệ."}
    if len(data_df) > MAX_ANALYSIS_ROWS or data_df.shape[1] > MAX_ANALYSIS_COLUMNS:
        return {"error": "Bảng dữ liệu vượt giới hạn phân tích tương tác."}
    parts = command.split()
    cmd = parts[0].upper()
    try:
        col_map = _casefold_column_map(data_df)
    except ExpressionValidationError as exc:
        return {"error": str(exc)}

    # ---------- LS / OLS ----------
    if cmd in ('LS', 'OLS'):
        if len(parts) < 3:
            return {"error": "Lệnh LS cần ≥1 biến phụ thuộc và ≥1 biến độc lập. VD: LS Y C X"}
        dep_in = parts[1].upper()
        dep_col = col_map.get(dep_in)
        if dep_col is None:
            return {"error": f"Không tìm thấy biến phụ thuộc '{parts[1]}'."}
        terms = parts[2:]
        if len(terms) > MAX_LS_TERMS:
            return {"error": f"Mô hình vượt giới hạn {MAX_LS_TERMS} số hạng độc lập."}
        X_data = pd.DataFrame(index=data_df.index)
        for t in terms:
            tU = t.upper()
            if tU == 'C':
                X_data['C'] = 1.0
            elif tU in col_map:
                X_data[col_map[tU]] = pd.to_numeric(
                    data_df[col_map[tU]], errors='coerce'
                )
            else:
                # thử biểu thức (biến trễ, log, ...)
                try:
                    X_data[t] = eviews_expr_to_series(t, data_df)
                except Exception:
                    return {"error": f"Không hiểu số hạng độc lập '{t}'."}
        dependent = pd.to_numeric(data_df[dep_col], errors='coerce').rename(dep_col)
        temp = pd.concat([dependent, X_data], axis=1)
        temp = temp.replace([np.inf, -np.inf], np.nan).dropna()
        y = temp[dep_col]
        X = temp.loc[:, ~temp.columns.duplicated()]
        X = X[[c for c in X.columns if c != dep_col]]
        if 'C' in X.columns:
            X = X.rename(columns={'C': 'const'})
        if len(y) < X.shape[1] + 2:
            return {"error": "Không đủ số quan sát sau khi loại giá trị thiếu."}
        try:
            results = sm.OLS(y, X).fit()
            return {"success": True, "results": results, "dep_var": dep_col, "nobs": len(y)}
        except Exception as e:
            return {"error": f"Lỗi khi chạy hồi quy: {e}"}

    # ---------- GENR ----------
    if cmd == 'GENR':
        try:
            expr = " ".join(parts[1:])
            var_name, formula = expr.split('=', 1)
            var_name = var_name.strip()
            if not _GENR_NAME_RE.fullmatch(var_name):
                raise ExpressionValidationError(
                    "INVALID_VARIABLE_NAME",
                    "Tên biến mới chỉ gồm chữ, số, gạch dưới và không bắt đầu bằng số.",
                )
            if not formula.strip():
                raise ExpressionValidationError(
                    "EMPTY_EXPRESSION", "Biểu thức tạo biến đang trống."
                )
            new_df = data_df.copy()
            new_df[var_name] = eviews_expr_to_series(formula, data_df)
            return {"success": True,
                    "message": f"Đã tạo/cập nhật biến '{var_name}'.",
                    "data": new_df}
        except Exception as e:
            return {"error": f"Lỗi khi tính biến mới: {e}"}

    # ---------- ADF (nghiệm đơn vị) ----------
    if cmd in ('ADF', 'UROOT'):
        if adfuller is None:
            return {"error": "Thiếu module ADF (statsmodels.tsa)."}
        if len(parts) < 2:
            return {"error": "Cú pháp: ADF <tên biến>."}
        col = col_map.get(parts[1].upper())
        if col is None:
            return {"error": f"Không tìm thấy biến '{parts[1]}'."}
        series = pd.to_numeric(data_df[col], errors='coerce')
        series = series.replace([np.inf, -np.inf], np.nan).dropna()
        try:
            stat, pval, usedlag, nobs, crit, _ = adfuller(series, autolag='AIC')
            return {"success": True, "adf": {
                "var": col, "stat": stat, "pvalue": pval, "lags": usedlag,
                "nobs": nobs, "crit": crit}}
        except Exception as e:
            return {"error": f"Lỗi ADF: {e}"}

    # ---------- Thống kê mô tả ----------
    if cmd in ('STATS', 'DESC', 'DESCRIBE'):
        if len(parts) < 2:
            cols = [c for c in data_df.columns]
        else:
            cols = [col_map.get(p.upper()) for p in parts[1:]]
            cols = [c for c in cols if c is not None]
        if not cols:
            return {"error": "Không tìm thấy biến để thống kê."}
        num = data_df[cols].apply(pd.to_numeric, errors='coerce')
        num = num.replace([np.inf, -np.inf], np.nan)
        rows = {}
        for c in cols:
            s = num[c].dropna()
            if s.empty:
                continue
            jb_s, jb_p, sk, ku = jarque_bera(s) if len(s) > 3 else (np.nan,)*4
            rows[c] = {
                'Trung bình (Mean)': s.mean(), 'Trung vị (Median)': s.median(),
                'Lớn nhất (Max)': s.max(), 'Nhỏ nhất (Min)': s.min(),
                'Độ lệch chuẩn (Std)': s.std(ddof=1),
                'Độ lệch (Skew)': sk, 'Độ nhọn (Kurt)': ku,
                'Jarque-Bera': jb_s, 'Prob(JB)': jb_p, 'Số qs (N)': int(s.count())}
        stats_df = pd.DataFrame(rows)
        return {"success": True, "stats": stats_df}

    # ---------- Ma trận tương quan ----------
    if cmd in ('COR', 'CORR', 'CORREL'):
        if len(parts) < 2:
            cols = list(data_df.columns)
        else:
            cols = [col_map.get(p.upper()) for p in parts[1:]]
            cols = [c for c in cols if c is not None]
        num = data_df[cols].apply(pd.to_numeric, errors='coerce')
        num = num.replace([np.inf, -np.inf], np.nan)
        num = num.select_dtypes(include=[np.number]).dropna()
        if num.shape[1] < 2:
            return {"error": "Cần ≥2 biến số để tính tương quan."}
        return {"success": True, "corr": num.corr()}

    # ---------- Đồ thị ----------
    if cmd in ('PLOT', 'LINE', 'SCAT', 'SCATTER', 'HIST', 'HISTOGRAM'):
        varnames = parts[1:]
        cols = [col_map.get(v.upper()) for v in varnames]
        cols = [c for c in cols if c is not None]
        if not cols:
            return {"error": f"Không tìm thấy biến để vẽ. Cú pháp: {cmd} <biến> [biến2]."}
        if cmd in ('SCAT', 'SCATTER'):
            if len(cols) < 2:
                return {"error": "SCAT cần 2 biến: SCAT X Y."}
            kind = 'scatter'
        elif cmd in ('HIST', 'HISTOGRAM'):
            kind = 'hist'
        else:
            kind = 'line'
        data = data_df[cols].apply(pd.to_numeric, errors='coerce')
        data = data.replace([np.inf, -np.inf], np.nan)
        return {"success": True, "plot": {"kind": kind, "cols": cols, "data": data}}

    return {"error": f"Lệnh '{cmd}' chưa hỗ trợ. Các lệnh có: LS, GENR, ADF, STATS, COR, PLOT/SCAT/HIST."}


# ==================== ĐỊNH DẠNG KẾT QUẢ (HTML) ====================
def _diagnostics_block(results):
    html = ""
    resid = results.resid
    exog = results.model.exog
    names = results.model.exog_names

    # White
    try:
        wt = het_white(resid, exog)
        wp = wt[1]
        wv = "⚠️ CÓ phương sai sai số thay đổi" if wp < 0.05 else "✅ Không có (phương sai đồng nhất)"
        html += f"<p style='margin:4px 0;'><b>Kiểm định White (PSSS thay đổi):</b> p-value = {wp:.4f} → <b>{wv}</b></p>"
    except Exception:
        pass
    # Breusch-Godfrey
    try:
        bg = acorr_breusch_godfrey(results, nlags=1)
        bp = bg[1]
        bv = "⚠️ CÓ tự tương quan" if bp < 0.05 else "✅ Không có tự tương quan"
        html += f"<p style='margin:4px 0;'><b>Kiểm định Breusch-Godfrey (tự tương quan):</b> p-value = {bp:.4f} → <b>{bv}</b></p>"
    except Exception:
        pass
    # Ramsey RESET
    try:
        rs = linear_reset(results, power=2, use_f=True)
        rp = float(rs.pvalue)
        rv = "⚠️ Mô hình có thể sai dạng hàm / thiếu biến" if rp < 0.05 else "✅ Dạng hàm phù hợp"
        html += f"<p style='margin:4px 0;'><b>Kiểm định Ramsey RESET (dạng hàm):</b> p-value = {rp:.4f} → <b>{rv}</b></p>"
    except Exception:
        pass
    return html


def _format_ls(res_dict):
    results = res_dict["results"]
    dep_var = res_dict["dep_var"]
    safe_dep_var = html_lib.escape(str(dep_var))
    nobs = res_dict["nobs"]

    r_squared = results.rsquared
    adj_r_squared = results.rsquared_adj
    f_stat = results.fvalue
    f_pvalue = results.f_pvalue
    log_likelihood = results.llf
    aic = results.aic
    bic = results.bic
    ssr = results.ssr
    se_regression = np.sqrt(ssr / results.df_resid) if results.df_resid > 0 else np.nan
    mean_dep = results.model.endog.mean()
    sd_dep = results.model.endog.std(ddof=1)
    dw_stat = durbin_watson(results.resid)
    jb_stat, jb_pvalue, jb_skew, jb_kurt = jarque_bera(results.resid)

    X_for_vif = results.model.exog
    col_names = results.model.exog_names
    non_const_idx = [i for i, n in enumerate(col_names) if n != 'const']
    vif_values = ({col_names[i]: variance_inflation_factor(X_for_vif, i) for i in non_const_idx}
                  if len(non_const_idx) >= 2 else {})

    coef_df = pd.DataFrame({
        'Hệ số (Coefficient)': results.params,
        'Sai số chuẩn (Std. Error)': results.bse,
        'Thống kê t (t-Statistic)': results.tvalues,
        'Xác suất (Prob.)': results.pvalues})
    if 'const' in coef_df.index:
        coef_df = coef_df.rename(index={'const': 'C'})

    html = f"""
    <div style="font-family: monospace; font-size: 14px; background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px; color:#111;">
        <p style="margin:2px 0;"><b>Biến phụ thuộc (Dependent Variable):</b> {safe_dep_var}</p>
        <p style="margin:2px 0;"><b>Phương pháp (Method):</b> Bình phương nhỏ nhất (Least Squares)</p>
        <p style="margin:2px 0;"><b>Số quan sát (Included observations):</b> {nobs}</p>
        <hr style="border-top: 1px solid #bbb; margin: 10px 0;">
    """
    html += coef_df.to_html(float_format=lambda x: f"{x:.6f}", border=0)
    html += f"""
        <hr style="border-top: 1px solid #bbb; margin: 10px 0;">
        <table style="width: 100%; font-size: 14px;">
            <tr><td style="width:50%;"><b>R-squared</b></td><td style="width:15%;">{r_squared:.6f}</td>
                <td style="width:50%;"><b>Mean dependent var</b></td><td>{mean_dep:.6f}</td></tr>
            <tr><td><b>Adjusted R-squared</b></td><td>{adj_r_squared:.6f}</td>
                <td><b>S.D. dependent var</b></td><td>{sd_dep:.6f}</td></tr>
            <tr><td><b>S.E. of regression</b></td><td>{se_regression:.6f}</td>
                <td><b>Akaike info criterion</b></td><td>{aic:.6f}</td></tr>
            <tr><td><b>Sum squared resid</b></td><td>{ssr:.6f}</td>
                <td><b>Schwarz criterion</b></td><td>{bic:.6f}</td></tr>
            <tr><td><b>Log likelihood</b></td><td>{log_likelihood:.6f}</td>
                <td><b>F-statistic</b></td><td>{f_stat:.6f}</td></tr>
            <tr><td><b>Durbin-Watson stat</b></td><td>{dw_stat:.6f}</td>
                <td><b>Prob(F-statistic)</b></td><td>{f_pvalue:.6f}</td></tr>
        </table>
        <hr style="border-top: 1px solid #bbb; margin: 10px 0;">
        <p style="margin:4px 0;"><b>Kiểm định chuẩn tắc phần dư (Jarque-Bera):</b>
           JB = {jb_stat:.4f} | p-value = {jb_pvalue:.4f} | Skew = {jb_skew:.4f} | Kurt = {jb_kurt:.4f}
           → <b>{"✅ Phần dư phân phối chuẩn" if jb_pvalue > 0.05 else "⚠️ Phần dư KHÔNG phân phối chuẩn"}</b></p>
    """
    html += _diagnostics_block(results)
    if vif_values:
        html += "<hr style='border-top:1px solid #bbb;margin:10px 0;'>"
        html += "<p style='margin:4px 0;'><b>Nhân tử phóng đại phương sai (VIF – Đa cộng tuyến):</b></p>"
        html += "<table style='font-size:14px;'><tr><th style='text-align:left;padding-right:20px;'>Biến</th><th>VIF</th><th style='padding-left:20px;'>Đánh giá</th></tr>"
        for var, vif in vif_values.items():
            a = ("⚠️ Đa cộng tuyến nghiêm trọng" if vif > 10
                 else "⚡ Đa cộng tuyến trung bình" if vif > 5 else "✅ Chấp nhận được")
            safe_var = html_lib.escape(str(var))
            html += f"<tr><td><b>{safe_var}</b></td><td>{vif:.4f}</td><td style='padding-left:20px;'>{a}</td></tr>"
        html += "</table>"
    html += "</div>"
    return html


def _wrap(inner):
    return (f"<div style='font-family:monospace;font-size:14px;background:#f8f9fa;"
            f"padding:15px;border:1px solid #ddd;border-radius:5px;color:#111;'>{inner}</div>")


def format_eviews_output(res_dict):
    if "error" in res_dict:
        error = html_lib.escape(str(res_dict['error']))
        return f"<div style='color:red;'><b>Lỗi:</b> {error}</div>"
    if "message" in res_dict:
        message = html_lib.escape(str(res_dict['message']))
        return f"<div style='color:green;'><b>Thành công:</b> {message}</div>"

    if "results" in res_dict:
        return _format_ls(res_dict)

    if "adf" in res_dict:
        a = res_dict["adf"]
        safe_var = html_lib.escape(str(a['var']))
        concl = ("✅ Chuỗi DỪNG (bác bỏ H₀ có nghiệm đơn vị)" if a["pvalue"] < 0.05
                 else "⚠️ Chuỗi KHÔNG dừng (chưa bác bỏ được nghiệm đơn vị)")
        crit = " | ".join(
            f"{html_lib.escape(str(k))}: {v:.4f}" for k, v in a["crit"].items()
        )
        inner = (f"<p><b>Kiểm định nghiệm đơn vị ADF — biến {safe_var}</b></p>"
                 f"<p>ADF Test Statistic = <b>{a['stat']:.6f}</b> | p-value = <b>{a['pvalue']:.4f}</b></p>"
                 f"<p>Giá trị tới hạn: {crit}</p>"
                 f"<p>Số trễ (lags) = {a['lags']} | Số quan sát = {a['nobs']}</p>"
                 f"<p>→ <b>{concl}</b> (H₀: chuỗi có nghiệm đơn vị / không dừng)</p>")
        return _wrap(inner)

    if "stats" in res_dict:
        df = res_dict["stats"]
        return _wrap("<p><b>Thống kê mô tả (Descriptive Statistics)</b></p>" +
                     df.to_html(float_format=lambda x: f"{x:.6f}", border=0))

    if "corr" in res_dict:
        df = res_dict["corr"]
        return _wrap("<p><b>Ma trận hệ số tương quan (Correlation)</b></p>" +
                     df.to_html(float_format=lambda x: f"{x:.4f}", border=0))

    if "plot" in res_dict:
        return None  # đồ thị do app tự vẽ

    return "<div style='color:red;'>Không có kết quả để hiển thị.</div>"
