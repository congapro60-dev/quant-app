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
def _find_col(df, name):
    up = {c.upper(): c for c in df.columns}
    return up.get(name.strip().upper())


def eviews_expr_to_series(formula, df):
    """
    Dịch biểu thức kiểu Eviews sang pandas Series.
    Hỗ trợ: + - * / ** , LOG(), EXP(), ABS(), SQR()/SQRT(), D() (sai phân),
    biến trễ VAR(-k), @TREND, và biểu thức so sánh (tạo biến giả).
    """
    work = df.copy()
    f = formula.strip()

    # @TREND -> chuỗi 0,1,2,...
    if '@TREND' in f.upper():
        work['__TREND__'] = np.arange(len(work), dtype=float)
        f = re.sub('@TREND', '__TREND__', f, flags=re.I)

    # Biến trễ VAR(-k)
    def _lag(m):
        name, k = m.group(1), int(m.group(2))
        col = _find_col(work, name)
        if col is None:
            raise ValueError(f"Không tìm thấy biến '{name}' để lấy trễ.")
        newname = f"__{name}_L{k}__"
        work[newname] = work[col].shift(k)
        return newname
    f = re.sub(r'([A-Za-z_@]\w*)\s*\(\s*-\s*(\d+)\s*\)', _lag, f)

    # Không gian tên cho eval
    ns = {}
    for c in work.columns:
        ns[c] = work[c]
        ns.setdefault(c.upper(), work[c])
        ns.setdefault(c.lower(), work[c])
    funcs = {'LOG': np.log, 'EXP': np.exp, 'ABS': np.abs,
             'SQR': np.sqrt, 'SQRT': np.sqrt,
             'D': lambda s: pd.Series(s).diff()}
    for k, v in list(funcs.items()):
        ns[k] = v
        ns[k.lower()] = v

    val = eval(f, {"__builtins__": {}}, ns)
    if np.isscalar(val):
        val = pd.Series(val, index=work.index)
    val = pd.Series(val, index=work.index)
    if val.dtype == bool:
        val = val.astype(int)
    return val


# ==================== BỘ PHÂN TÍCH LỆNH ====================
def parse_and_execute_command(command, data_df):
    command = command.strip()
    if not command:
        return {"error": "Lệnh trống."}
    parts = command.split()
    cmd = parts[0].upper()
    col_map = {c.upper(): c for c in data_df.columns}

    # ---------- LS / OLS ----------
    if cmd in ('LS', 'OLS'):
        if len(parts) < 3:
            return {"error": "Lệnh LS cần ≥1 biến phụ thuộc và ≥1 biến độc lập. VD: LS Y C X"}
        dep_in = parts[1].upper()
        dep_col = col_map.get(dep_in)
        if dep_col is None:
            return {"error": f"Không tìm thấy biến phụ thuộc '{parts[1]}'."}
        terms = parts[2:]
        X_data = pd.DataFrame(index=data_df.index)
        for t in terms:
            tU = t.upper()
            if tU == 'C':
                X_data['C'] = 1.0
            elif tU in col_map:
                X_data[col_map[tU]] = data_df[col_map[tU]]
            else:
                # thử biểu thức (biến trễ, log, ...)
                try:
                    X_data[t] = eviews_expr_to_series(t, data_df)
                except Exception:
                    return {"error": f"Không hiểu số hạng độc lập '{t}'."}
        temp = pd.concat([data_df[dep_col].rename(dep_col), X_data], axis=1).dropna()
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
        series = pd.to_numeric(data_df[col], errors='coerce').dropna()
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
        <p style="margin:2px 0;"><b>Biến phụ thuộc (Dependent Variable):</b> {dep_var}</p>
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
            html += f"<tr><td><b>{var}</b></td><td>{vif:.4f}</td><td style='padding-left:20px;'>{a}</td></tr>"
        html += "</table>"
    html += "</div>"
    return html


def _wrap(inner):
    return (f"<div style='font-family:monospace;font-size:14px;background:#f8f9fa;"
            f"padding:15px;border:1px solid #ddd;border-radius:5px;color:#111;'>{inner}</div>")


def format_eviews_output(res_dict):
    if "error" in res_dict:
        return f"<div style='color:red;'><b>Lỗi:</b> {res_dict['error']}</div>"
    if "message" in res_dict:
        return f"<div style='color:green;'><b>Thành công:</b> {res_dict['message']}</div>"

    if "results" in res_dict:
        return _format_ls(res_dict)

    if "adf" in res_dict:
        a = res_dict["adf"]
        concl = ("✅ Chuỗi DỪNG (bác bỏ H₀ có nghiệm đơn vị)" if a["pvalue"] < 0.05
                 else "⚠️ Chuỗi KHÔNG dừng (chưa bác bỏ được nghiệm đơn vị)")
        crit = " | ".join(f"{k}: {v:.4f}" for k, v in a["crit"].items())
        inner = (f"<p><b>Kiểm định nghiệm đơn vị ADF — biến {a['var']}</b></p>"
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
