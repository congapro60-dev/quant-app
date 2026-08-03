import json
from collections.abc import Mapping

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize
from statsmodels.stats.diagnostic import (
    acorr_breusch_godfrey,
    het_white,
    linear_reset,
)
from statsmodels.stats.stattools import jarque_bera


TRADING_DAYS = 252
DEFAULT_RISK_FREE_RATE = 0.04
DEFAULT_FRONTIER_SEED = 42
DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
MIN_SIM_OBSERVATIONS = 8
MIN_PORTFOLIO_OBSERVATIONS = 20
_WEIGHT_TOLERANCE = 1e-6


class AnalyticsValidationError(ValueError):
    """Raised when an analytics result would not be safe to present."""


def _finite_series(values, name):
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        try:
            series = pd.Series(values)
        except Exception as exc:
            raise AnalyticsValidationError(f"{name} không phải chuỗi dữ liệu hợp lệ.") from exc
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def run_sim(asset_returns, market_returns, min_observations=MIN_SIM_OBSERVATIONS):
    """Run the Single Index Model after validating the aligned return sample."""
    if int(min_observations) < 3:
        raise AnalyticsValidationError("min_observations phải >= 3.")

    asset = _finite_series(asset_returns, "Lợi suất tài sản")
    market = _finite_series(market_returns, "Lợi suất thị trường")
    df = pd.concat([asset, market], axis=1).dropna()
    df.columns = ["Asset", "Market"]

    if len(df) < int(min_observations):
        raise AnalyticsValidationError(
            f"SIM cần ít nhất {int(min_observations)} quan sát hữu hạn; hiện có {len(df)}."
        )
    if not np.isfinite(df.to_numpy(dtype=float)).all():
        raise AnalyticsValidationError("Mẫu SIM còn chứa giá trị không hữu hạn.")
    if float(df["Market"].var(ddof=1)) <= np.finfo(float).eps:
        raise AnalyticsValidationError("Lợi suất thị trường không có đủ biến động để ước lượng Beta.")

    y = df["Asset"]
    X = sm.add_constant(df["Market"], has_constant="add")
    results = sm.OLS(y, X).fit()

    beta = float(results.params["Market"])
    alpha = float(results.params["const"])
    market_var = float(df["Market"].var(ddof=1))
    residual_var = float(results.resid.var(ddof=1))
    total_risk = float(df["Asset"].var(ddof=1))
    values = np.array(
        [beta, alpha, market_var, residual_var, total_risk, results.rsquared],
        dtype=float,
    )
    if not np.isfinite(values).all():
        raise AnalyticsValidationError("SIM tạo ra hệ số hoặc rủi ro không hữu hạn.")

    return {
        "alpha": alpha,
        "beta": beta,
        "systematic_risk": (beta**2) * market_var,
        "unsystematic_risk": residual_var,
        "total_risk": total_risk,
        "r_squared": float(results.rsquared),
        "model": results,
        "X": X,
        "n_observations": len(df),
    }


def _validated_diagnostic_inputs(sim_results, min_observations):
    if not isinstance(sim_results, Mapping):
        raise AnalyticsValidationError("Kết quả SIM phải là một mapping.")
    model = sim_results.get("model")
    X = sim_results.get("X")
    if model is None or X is None or not hasattr(model, "resid"):
        raise AnalyticsValidationError("Kết quả SIM thiếu model hoặc ma trận X.")

    resid = np.asarray(model.resid, dtype=float).reshape(-1)
    exog = np.asarray(X, dtype=float)
    if exog.ndim == 1:
        exog = exog.reshape(-1, 1)
    if len(resid) != exog.shape[0]:
        raise AnalyticsValidationError("Số dòng phần dư không khớp ma trận X.")
    if len(resid) < int(min_observations):
        raise AnalyticsValidationError(
            f"Chẩn đoán SIM cần ít nhất {int(min_observations)} quan sát; hiện có {len(resid)}."
        )
    if exog.shape[1] < 2:
        raise AnalyticsValidationError("Ma trận X phải chứa hằng số và biến thị trường.")
    if not np.isfinite(resid).all() or not np.isfinite(exog).all():
        raise AnalyticsValidationError("Dữ liệu chẩn đoán chứa NaN hoặc vô cực.")
    return model, exog, resid


def _validated_pvalue(value, test_name):
    pvalue = float(value)
    if not np.isfinite(pvalue) or not 0.0 <= pvalue <= 1.0:
        raise AnalyticsValidationError(f"{test_name} trả về p-value không hợp lệ.")
    return pvalue


def run_diagnostics(sim_results, min_observations=MIN_SIM_OBSERVATIONS):
    """Run model diagnostics with contract validation and explicit partial errors."""
    model, X, resid = _validated_diagnostic_inputs(sim_results, min_observations)
    diagnostics = {
        "White_pvalue": None,
        "Heteroskedasticity": "Error",
        "BG_pvalue": None,
        "Autocorrelation": "Error",
        "RESET_pvalue": None,
        "SpecificationError": "Error",
        "JB_stat": None,
        "JB_pvalue": None,
        "JB_skewness": None,
        "JB_kurtosis": None,
        "Normality": "Error",
    }
    errors = {}

    try:
        white_test = het_white(resid, X)
        pvalue = _validated_pvalue(white_test[1], "White")
        diagnostics["White_pvalue"] = pvalue
        diagnostics["Heteroskedasticity"] = "Yes" if pvalue < 0.05 else "No"
    except Exception as exc:
        errors["White"] = str(exc)

    try:
        bg_test = acorr_breusch_godfrey(model, nlags=1)
        pvalue = _validated_pvalue(bg_test[1], "Breusch-Godfrey")
        diagnostics["BG_pvalue"] = pvalue
        diagnostics["Autocorrelation"] = "Yes" if pvalue < 0.05 else "No"
    except Exception as exc:
        errors["Breusch-Godfrey"] = str(exc)

    try:
        reset = linear_reset(model, power=2, use_f=True)
        pvalue = _validated_pvalue(reset.pvalue, "Ramsey RESET")
        diagnostics["RESET_pvalue"] = pvalue
        diagnostics["SpecificationError"] = "Có thể có" if pvalue < 0.05 else "Không"
    except Exception as exc:
        errors["Ramsey RESET"] = str(exc)

    try:
        jb_stat, jb_pvalue, jb_skew, jb_kurt = jarque_bera(resid)
        pvalue = _validated_pvalue(jb_pvalue, "Jarque-Bera")
        jb_values = np.asarray([jb_stat, jb_skew, jb_kurt], dtype=float)
        if not np.isfinite(jb_values).all():
            raise AnalyticsValidationError("Jarque-Bera trả về thống kê không hữu hạn.")
        diagnostics["JB_stat"] = float(jb_stat)
        diagnostics["JB_pvalue"] = pvalue
        diagnostics["JB_skewness"] = float(jb_skew)
        diagnostics["JB_kurtosis"] = float(jb_kurt)
        diagnostics["Normality"] = "Chuẩn" if pvalue > 0.05 else "Không chuẩn"
    except Exception as exc:
        errors["Jarque-Bera"] = str(exc)

    diagnostics["status"] = "ok" if not errors else "partial"
    diagnostics["errors"] = errors
    diagnostics["n_observations"] = len(resid)
    return diagnostics


def _prepare_portfolio_returns(returns_df, min_observations):
    if not isinstance(returns_df, pd.DataFrame):
        try:
            returns_df = pd.DataFrame(returns_df)
        except Exception as exc:
            raise AnalyticsValidationError("Lợi suất danh mục phải chuyển được thành DataFrame.") from exc
    if returns_df.shape[1] == 0:
        raise AnalyticsValidationError("Cần ít nhất một tài sản để tối ưu danh mục.")
    if returns_df.columns.duplicated().any():
        raise AnalyticsValidationError("Tên tài sản trong danh mục không được trùng nhau.")
    if int(min_observations) < 3:
        raise AnalyticsValidationError("min_observations phải >= 3.")

    numeric = returns_df.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if len(numeric) < int(min_observations):
        raise AnalyticsValidationError(
            f"Markowitz cần ít nhất {int(min_observations)} quan sát chung hữu hạn; hiện có {len(numeric)}."
        )
    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise AnalyticsValidationError("Lợi suất danh mục chứa giá trị không hữu hạn.")

    variances = numeric.var(ddof=1)
    invalid_assets = variances.index[
        (~np.isfinite(variances.to_numpy(dtype=float)))
        | (variances.to_numpy(dtype=float) <= np.finfo(float).eps)
    ].tolist()
    if invalid_assets:
        raise AnalyticsValidationError(
            "Tài sản không có đủ biến động để tối ưu: " + ", ".join(map(str, invalid_assets))
        )
    return numeric, len(returns_df) - len(numeric)


def _regularize_covariance(cov_matrix, strength):
    strength = float(strength)
    if not np.isfinite(strength) or strength < 0:
        raise AnalyticsValidationError("covariance_regularization phải là số hữu hạn >= 0.")
    covariance = np.asarray(cov_matrix, dtype=float)
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise AnalyticsValidationError("Ma trận hiệp phương sai không vuông.")
    if not np.isfinite(covariance).all():
        raise AnalyticsValidationError("Ma trận hiệp phương sai chứa NaN hoặc vô cực.")

    covariance = (covariance + covariance.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    scale = max(
        float(np.trace(covariance) / max(len(covariance), 1)),
        float(np.max(np.abs(eigenvalues))),
        np.finfo(float).eps,
    )
    floor = max(scale * strength, scale * np.finfo(float).eps)
    clipped = np.maximum(eigenvalues, floor)
    regularized = (eigenvectors * clipped) @ eigenvectors.T
    regularized = (regularized + regularized.T) / 2.0
    adjustment = float(np.max(clipped - eigenvalues))
    return regularized, adjustment


def _validated_solver_weights(result, num_assets, label):
    if result is None or not bool(getattr(result, "success", False)):
        message = getattr(result, "message", "không có phản hồi từ solver")
        raise AnalyticsValidationError(f"{label} thất bại: {message}")
    weights = np.asarray(getattr(result, "x", []), dtype=float).reshape(-1)
    if weights.shape != (num_assets,) or not np.isfinite(weights).all():
        raise AnalyticsValidationError(f"{label} trả về vector trọng số không hợp lệ.")
    if np.any(weights < -_WEIGHT_TOLERANCE) or np.any(weights > 1 + _WEIGHT_TOLERANCE):
        raise AnalyticsValidationError(f"{label} trả về trọng số ngoài miền [0, 1].")
    total = float(weights.sum())
    if abs(total - 1.0) > _WEIGHT_TOLERANCE:
        raise AnalyticsValidationError(f"{label} trả về tổng trọng số {total:.8f}, khác 1.")

    weights = np.clip(weights, 0.0, 1.0)
    weights /= weights.sum()
    return weights


def markowitz_optimization(
    returns_df,
    risk_free_rate=DEFAULT_RISK_FREE_RATE,
    trading_days=TRADING_DAYS,
    num_portfolios=500,
    random_seed=DEFAULT_FRONTIER_SEED,
    min_observations=MIN_PORTFOLIO_OBSERVATIONS,
    covariance_regularization=1e-8,
):
    """Optimize a long-only risky portfolio and expose cash as a separate option.

    Existing keys consumed by the Streamlit UI are preserved. New metadata makes
    solver, cash and regularization decisions explicit for safer integrations.
    """
    risk_free_rate = float(risk_free_rate)
    trading_days = int(trading_days)
    num_portfolios = int(num_portfolios)
    if not np.isfinite(risk_free_rate):
        raise AnalyticsValidationError("risk_free_rate phải là số hữu hạn.")
    if trading_days <= 0:
        raise AnalyticsValidationError("trading_days phải > 0.")
    if not 1 <= num_portfolios <= 100_000:
        raise AnalyticsValidationError("num_portfolios phải nằm trong [1, 100000].")
    if random_seed is None:
        raise AnalyticsValidationError("random_seed phải được đặt để frontier có thể tái lập.")

    clean_returns, dropped_rows = _prepare_portfolio_returns(
        returns_df, min_observations=min_observations
    )
    assets = clean_returns.columns.tolist()
    num_assets = len(assets)
    mean_returns = clean_returns.mean().to_numpy(dtype=float) * trading_days
    raw_covariance = clean_returns.cov().to_numpy(dtype=float) * trading_days
    covariance, regularization_adjustment = _regularize_covariance(
        raw_covariance, covariance_regularization
    )
    if not np.isfinite(mean_returns).all():
        raise AnalyticsValidationError("Lợi suất kỳ vọng năm hóa không hữu hạn.")

    def performance(weights):
        weights = np.asarray(weights, dtype=float)
        expected_return = float(mean_returns @ weights)
        variance = float(weights @ covariance @ weights)
        if not np.isfinite(expected_return) or not np.isfinite(variance):
            return np.nan, np.nan
        volatility = float(np.sqrt(max(variance, 0.0)))
        return volatility, expected_return

    def portfolio_variance(weights):
        weights = np.asarray(weights, dtype=float)
        value = float(weights @ covariance @ weights)
        return value if np.isfinite(value) else 1e100

    def negative_sharpe_ratio(weights):
        volatility, expected_return = performance(weights)
        if not np.isfinite(volatility) or volatility <= np.finfo(float).eps:
            return 1e100
        return -((expected_return - risk_free_rate) / volatility)

    constraints = ({"type": "eq", "fun": lambda x: np.sum(x) - 1.0},)
    bounds = tuple((0.0, 1.0) for _ in range(num_assets))
    initial_weights = np.full(num_assets, 1.0 / num_assets, dtype=float)
    solver_options = {"maxiter": 2_000, "ftol": 1e-12}

    min_vol_result = minimize(
        portfolio_variance,
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options=solver_options,
    )
    min_vol_weights = _validated_solver_weights(
        min_vol_result, num_assets, "Tối ưu Min Volatility"
    )
    min_vol_perf = performance(min_vol_weights)
    if not np.isfinite(min_vol_perf).all():
        raise AnalyticsValidationError("Min Volatility tạo ra hiệu suất không hữu hạn.")

    warning_msg = None
    cash_weight = 0.0
    max_sharpe_result = None
    if float(np.max(mean_returns)) <= risk_free_rate + 1e-12:
        max_sharpe_weights = np.zeros(num_assets, dtype=float)
        cash_weight = 1.0
        warning_msg = (
            "Lợi suất kỳ vọng năm hóa của mọi tài sản rủi ro không vượt lãi suất "
            f"phi rủi ro ({risk_free_rate:.2%}); mô hình giữ 100% ở phương án tiền mặt."
        )
        max_sharpe_status = {
            "success": True,
            "mode": "cash",
            "message": "Không tối ưu tài sản rủi ro vì tiền mặt chi phối theo giả định đầu vào.",
        }
    else:
        max_sharpe_result = minimize(
            negative_sharpe_ratio,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options=solver_options,
        )
        max_sharpe_weights = _validated_solver_weights(
            max_sharpe_result, num_assets, "Tối ưu Max Sharpe"
        )
        max_sharpe_perf = performance(max_sharpe_weights)
        if not np.isfinite(max_sharpe_perf).all():
            raise AnalyticsValidationError("Max Sharpe tạo ra hiệu suất không hữu hạn.")
        max_sharpe_status = {
            "success": True,
            "mode": "risky_portfolio",
            "message": str(getattr(max_sharpe_result, "message", "Thành công")),
        }

    rng = np.random.default_rng(int(random_seed))
    if num_assets == 1:
        frontier_weights = np.ones((num_portfolios, 1), dtype=float)
    else:
        frontier_weights = rng.dirichlet(np.ones(num_assets), size=num_portfolios)
    frontier_returns = frontier_weights @ mean_returns
    frontier_variances = np.einsum(
        "ij,jk,ik->i", frontier_weights, covariance, frontier_weights
    )
    frontier_volatility = np.sqrt(np.maximum(frontier_variances, 0.0))
    frontier_sharpes = np.divide(
        frontier_returns - risk_free_rate,
        frontier_volatility,
        out=np.zeros_like(frontier_returns),
        where=frontier_volatility > np.finfo(float).eps,
    )
    if not (
        np.isfinite(frontier_returns).all()
        and np.isfinite(frontier_volatility).all()
        and np.isfinite(frontier_sharpes).all()
    ):
        raise AnalyticsValidationError("Efficient frontier chứa giá trị không hữu hạn.")

    return {
        "min_vol_weights": min_vol_weights,
        "max_sharpe_weights": max_sharpe_weights,
        "assets": assets,
        "warning": warning_msg,
        "ef_vols": frontier_volatility,
        "ef_rets": frontier_returns,
        "ef_sharpes": frontier_sharpes,
        "cash_weight": cash_weight,
        "max_sharpe_cash_weight": cash_weight,
        "risk_free_rate": risk_free_rate,
        "n_observations": len(clean_returns),
        "dropped_rows": dropped_rows,
        "covariance_regularization": regularization_adjustment,
        "regularized_covariance": pd.DataFrame(covariance, index=assets, columns=assets),
        "optimizer_status": {
            "min_vol": {
                "success": True,
                "mode": "risky_portfolio",
                "message": str(getattr(min_vol_result, "message", "Thành công")),
            },
            "max_sharpe": max_sharpe_status,
        },
        "frontier_seed": int(random_seed),
    }


def _extract_anthropic_text(content):
    texts = []
    for block in content or []:
        if isinstance(block, Mapping):
            block_type = block.get("type")
            text = block.get("text")
        else:
            block_type = getattr(block, "type", None)
            text = getattr(block, "text", None)
        if (block_type in (None, "text")) and isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return "\n".join(texts)


def _extract_gemini_text(response):
    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    if isinstance(text, str) and text.strip():
        return text.strip()

    texts = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                texts.append(part_text.strip())
    return "\n".join(texts)


def call_llm(prompt, config):
    """Call a configured provider without process-global SDK configuration."""
    if not config or not config.get("api_key"):
        return None
    provider = config.get("provider")
    api_key = str(config.get("api_key", "")).strip()
    if not api_key:
        return None

    try:
        if provider == "Anthropic (Claude)":
            import anthropic

            model_name = str(config.get("model") or "").strip()
            if not model_name:
                raise AnalyticsValidationError("Chưa cấu hình model Anthropic.")
            client = anthropic.Anthropic(api_key=api_key)
            try:
                message = client.messages.create(
                    model=model_name,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": str(prompt)}],
                )
                text = _extract_anthropic_text(getattr(message, "content", None))
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
            if not text:
                raise AnalyticsValidationError("Anthropic không trả về content block dạng text.")
            return text

        if provider == "Google (Gemini)":
            from google import genai

            model_name = str(config.get("model") or DEFAULT_GEMINI_MODEL).strip()
            client = genai.Client(api_key=api_key)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=str(prompt),
                )
                text = _extract_gemini_text(response)
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
            if not text:
                raise AnalyticsValidationError("Gemini không trả về nội dung text.")
            return text

        raise AnalyticsValidationError(f"Nhà cung cấp AI không được hỗ trợ: {provider!r}.")
    except Exception as exc:
        return f"Lỗi gọi API: {exc}"


_ACTIONABLE_LANGUAGE = (
    "nên mua",
    "nên bán",
    "khuyến nghị mua",
    "khuyến nghị bán",
    "giải ngân",
    "đầu tư ngay",
    "phân bổ phần lớn vốn",
)


def _contains_actionable_language(text):
    normalized = " ".join(str(text).lower().split())
    return any(phrase in normalized for phrase in _ACTIONABLE_LANGUAGE)


def _safe_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _structured_metrics(sim_results_list, opt_res, market_prices):
    market = _finite_series(market_prices, "Giá thị trường").dropna()
    if len(market) < 2:
        raise AnalyticsValidationError("Cần ít nhất hai mức giá thị trường để diễn giải xu hướng.")
    values = market.to_numpy(dtype=float)
    x = np.arange(len(values), dtype=float)
    if np.all(values > 0):
        slope = float(sm.OLS(np.log(values), sm.add_constant(x)).fit().params[1])
        change = float(values[-1] / values[0] - 1.0)
    else:
        scale = max(float(np.mean(np.abs(values))), np.finfo(float).eps)
        slope = float(sm.OLS(values / scale, sm.add_constant(x)).fit().params[1])
        change = None
    trend = "TĂNG" if slope > 1e-12 else "GIẢM" if slope < -1e-12 else "ĐI NGANG"

    sim_metrics = []
    for item in sim_results_list or []:
        if not isinstance(item, Mapping):
            continue
        sim_metrics.append(
            {
                "asset": str(item.get("Mã CP", "")),
                "beta": _safe_number(item.get("Beta (Độ nhạy)")),
                "alpha": _safe_number(item.get("Alpha")),
                "r_squared": _safe_number(item.get("R^2")),
                "systematic_risk": _safe_number(item.get("Rủi ro Hệ thống")),
                "unsystematic_risk": _safe_number(item.get("Rủi ro Phi hệ thống")),
                "total_risk": _safe_number(item.get("Tổng Rủi ro")),
            }
        )

    assets = [str(asset) for asset in opt_res.get("assets", [])]
    weights = np.asarray(opt_res.get("max_sharpe_weights", []), dtype=float).reshape(-1)
    allocation_warning = None
    if weights.shape != (len(assets),) or not np.isfinite(weights).all():
        allocation_warning = "Vector trọng số Max Sharpe không hợp lệ nên không được diễn giải."
        allocations = []
    else:
        allocations = [
            {"asset": asset, "model_weight": float(weight)}
            for asset, weight in zip(assets, weights)
        ]

    cash_weight = _safe_number(
        opt_res.get("max_sharpe_cash_weight", opt_res.get("cash_weight", 0.0))
    )
    if cash_weight is None or not 0.0 <= cash_weight <= 1.0 + _WEIGHT_TOLERANCE:
        allocation_warning = "Trọng số tiền mặt không hợp lệ nên được đặt về 0."
        cash_weight = 0.0

    warnings = [warning for warning in (opt_res.get("warning"), allocation_warning) if warning]
    return {
        "scope": "historical_sample_only",
        "market_sample": {
            "observations": len(values),
            "trend_label": trend,
            "log_trend_per_observation": slope,
            "sample_total_change": change,
        },
        "single_index_model": sim_metrics,
        "portfolio_model": {
            "risky_asset_allocations": allocations,
            "cash_weight": cash_weight,
            "risk_free_rate": _safe_number(
                opt_res.get("risk_free_rate", DEFAULT_RISK_FREE_RATE)
            ),
            "optimizer_status": opt_res.get("optimizer_status"),
            "warnings": warnings,
        },
        "limitations": [
            "Các ước lượng chỉ mô tả mẫu lịch sử.",
            "Chưa chứng minh hiệu quả ngoài mẫu hoặc sau chi phí giao dịch.",
            "Trọng số là đầu ra toán học, không phải lệnh mua bán.",
        ],
    }


def _fallback_metric_explanation(metrics):
    market = metrics["market_sample"]
    sim_metrics = metrics["single_index_model"]
    portfolio = metrics["portfolio_model"]
    lines = [
        "### 📊 Diễn giải kết quả định lượng",
        (
            f"- Trong mẫu lịch sử {market['observations']} quan sát, nhãn xu hướng là "
            f"**{market['trend_label']}**. Đây chỉ là mô tả của mẫu, không phải dự báo."
        ),
    ]

    beta_text = []
    for item in sim_metrics:
        if item["asset"] and item["beta"] is not None:
            beta_text.append(f"{item['asset']}: β={item['beta']:.3f}")
    if beta_text:
        lines.append("- Độ nhạy SIM ước lượng: " + "; ".join(beta_text) + ".")

    allocations = portfolio["risky_asset_allocations"]
    if allocations:
        allocation_text = "; ".join(
            f"{item['asset']}={item['model_weight']:.1%}" for item in allocations
        )
        lines.append(f"- Phân bổ toán học Max Sharpe trong mẫu: {allocation_text}.")
    if portfolio["cash_weight"] > _WEIGHT_TOLERANCE:
        lines.append(
            f"- Phương án tiền mặt trong mô hình: {portfolio['cash_weight']:.1%}."
        )
    for warning in portfolio["warnings"]:
        lines.append(f"- ⚠️ {warning}")

    lines.append(
        "> Kết quả chỉ dùng để giải thích số liệu lịch sử; chưa bao gồm kiểm định ngoài mẫu, "
        "phí giao dịch hoặc bảo đảm lợi nhuận, và không phải khuyến nghị mua/bán."
    )
    return "\n\n".join(lines)


def generate_expert_advice(sim_results_list, opt_res, market_prices, ai_config=None):
    """Explain structured historical metrics without issuing trading instructions."""
    if not isinstance(opt_res, Mapping):
        raise AnalyticsValidationError("Kết quả tối ưu phải là một mapping.")
    metrics = _structured_metrics(sim_results_list, opt_res, market_prices)
    fallback = _fallback_metric_explanation(metrics)

    if not (ai_config and ai_config.get("api_key")):
        return fallback

    prompt = (
        "Bạn là người diễn giải mô hình định lượng. Chỉ được giải thích dữ liệu JSON bên dưới "
        "bằng tiếng Việt, phân biệt mô tả lịch sử với dự báo và nêu giới hạn mô hình. "
        "Không đưa ra chỉ dẫn mua, bán, giải ngân, thời điểm giao dịch hoặc hứa hẹn lợi nhuận. "
        "Không bổ sung dữ kiện ngoài JSON. Trình bày ngắn bằng Markdown.\n\n"
        "METRICS_JSON:\n"
        + json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    )
    llm_explanation = call_llm(prompt, ai_config)
    if not llm_explanation:
        return "⚠️ **Không nhận được phản hồi AI; dùng diễn giải định lượng mặc định.**\n\n" + fallback
    if llm_explanation.startswith("Lỗi gọi API"):
        return f"⚠️ **{llm_explanation}; dùng diễn giải định lượng mặc định.**\n\n{fallback}"
    if _contains_actionable_language(llm_explanation):
        return (
            "⚠️ **Phản hồi AI chứa ngôn ngữ chỉ dẫn giao dịch nên đã bị loại; "
            "dùng diễn giải định lượng mặc định.**\n\n"
            + fallback
        )
    return (
        llm_explanation.strip()
        + "\n\n> Đây là diễn giải số liệu lịch sử, không phải khuyến nghị mua/bán hoặc bảo đảm lợi nhuận."
    )
