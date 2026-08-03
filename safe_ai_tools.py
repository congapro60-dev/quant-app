"""Deterministic analysis tools for the natural-language study assistant.

The LLM is deliberately kept out of the calculation path.  A user request is
mapped to one of a small number of audited operations; only the compact result
may then be sent to an LLM for explanation.  No generated Python is executed.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller


MAX_ROWS = 100_000
MAX_COLUMNS = 100
MAX_PROMPT_CHARS = 12_000


class SafeAnalysisError(ValueError):
    """Raised when a request cannot be calculated safely or unambiguously."""


@dataclass(frozen=True)
class AnalysisBundle:
    tool: str
    narrative: str
    result: Any
    assumptions: tuple[str, ...] = ()


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value).lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def _requested_nobs(request: str) -> int | None:
    match = re.search(r"(\d{1,6})\s*(?:so lieu|quan sat|dong)\s*dau", _plain(request))
    if not match:
        return None
    nobs = int(match.group(1))
    if nobs < 2:
        raise SafeAnalysisError("Số quan sát phải từ 2 trở lên.")
    return min(nobs, MAX_ROWS)


def _numeric_frame(df: pd.DataFrame, request: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise SafeAnalysisError("Chưa có dữ liệu để phân tích.")
    if len(df) > MAX_ROWS:
        raise SafeAnalysisError(f"Dữ liệu vượt giới hạn {MAX_ROWS:,} dòng.")
    if len(df.columns) > MAX_COLUMNS:
        raise SafeAnalysisError(f"Dữ liệu vượt giới hạn {MAX_COLUMNS} cột.")

    nobs = _requested_nobs(request)
    work = df.head(nobs).copy() if nobs else df.copy()
    mapping = {str(col): col for col in work.columns}
    numeric = work.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.empty:
        raise SafeAnalysisError("Không tìm thấy cột số hợp lệ trong dữ liệu.")
    return numeric, mapping


def _mentioned_columns(request: str, numeric: pd.DataFrame) -> list[Any]:
    text = _plain(request)
    found: list[Any] = []
    for col in numeric.columns:
        token = _plain(str(col))
        if token and re.search(rf"(?<![\w]){re.escape(token)}(?![\w])", text):
            found.append(col)
    return found


def _returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if (prices <= 0).any().any():
        bad = [str(c) for c in prices.columns if (prices[c] <= 0).any()]
        raise SafeAnalysisError(
            "Giá phải dương để tính log-return. Cột lỗi: " + ", ".join(bad)
        )
    returns = np.log(prices / prices.shift(1))
    return returns.replace([np.inf, -np.inf], np.nan).dropna(how="all")


def _treat_as_returns(request: str, columns: list[Any]) -> bool:
    text = _plain(request)
    explicit = any(term in text for term in ("da la loi suat", "du lieu loi suat", "return data"))
    named = bool(columns) and all(_plain(str(c)).startswith(("r_", "return")) for c in columns)
    return explicit or named


def _aligned(data: pd.DataFrame, minimum: int = 20) -> pd.DataFrame:
    clean = data.replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < minimum:
        raise SafeAnalysisError(
            f"Cần ít nhất {minimum} quan sát hợp lệ; hiện chỉ có {len(clean)}."
        )
    return clean


def _parse_weights(request: str, count: int) -> np.ndarray | None:
    text = request.replace("−", "-")
    match = re.search(r"(?:w|trọng\s*số|trong\s*so)\s*=\s*[\[(]([^\])]+)[\])]", text, re.I)
    if not match:
        return None
    raw = match.group(1).strip()
    parts = re.split(r"[;\s]+", raw) if ";" in raw else re.split(r"[,\s]+", raw)
    parts = [p for p in parts if p]
    try:
        values = np.asarray([float(p.replace(",", ".")) for p in parts], dtype=float)
    except ValueError as exc:
        raise SafeAnalysisError("Không đọc được trọng số W. Hãy dùng dạng W=(0.25; 0.45; 0.30).") from exc
    if len(values) != count:
        raise SafeAnalysisError(f"Có {count} tài sản nhưng nhận {len(values)} trọng số.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise SafeAnalysisError("Trọng số phải là số hữu hạn và không âm.")
    total = float(values.sum())
    if total <= 0:
        raise SafeAnalysisError("Tổng trọng số phải lớn hơn 0.")
    return values / total


def _serializable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.reset_index().to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def analyze_request(df: pd.DataFrame, request: str) -> AnalysisBundle:
    """Map a Vietnamese natural-language request to an audited calculation."""

    if not str(request).strip():
        raise SafeAnalysisError("Hãy nhập yêu cầu phân tích.")
    numeric, _ = _numeric_frame(df, request)
    mentioned = _mentioned_columns(request, numeric)
    selected = mentioned or list(numeric.columns)
    text = _plain(request)
    assumptions: list[str] = []

    if any(term in text for term in ("adf", "nghiem don vi", "dung")):
        col = selected[0]
        series = numeric[col].dropna()
        if len(series) < 20:
            raise SafeAnalysisError("ADF cần ít nhất 20 quan sát hợp lệ.")
        stat, pvalue, lags, nobs, critical, _ = adfuller(series, autolag="AIC")
        result = {
            "column": str(col), "adf_statistic": float(stat), "p_value": float(pvalue),
            "lags": int(lags), "n_observations": int(nobs), "critical_values": critical,
        }
        return AnalysisBundle("adf", "Kiểm định nghiệm đơn vị ADF được tính cục bộ.", result)

    if any(term in text for term in ("hoi quy", "ols", "regression")):
        if len(selected) < 2:
            raise SafeAnalysisError("Hồi quy cần nêu ít nhất hai cột: biến phụ thuộc trước, biến giải thích sau.")
        dep, independents = selected[0], selected[1:]
        data = _aligned(numeric[[dep] + independents], minimum=max(20, len(independents) + 5))
        model = sm.OLS(data[dep], sm.add_constant(data[independents], has_constant="add")).fit()
        result = {
            "dependent": str(dep), "independents": [str(c) for c in independents],
            "n_observations": int(model.nobs), "r_squared": float(model.rsquared),
            "r_squared_adj": float(model.rsquared_adj), "f_p_value": float(model.f_pvalue),
            "coefficients": {str(k): float(v) for k, v in model.params.items()},
            "p_values": {str(k): float(v) for k, v in model.pvalues.items()},
        }
        assumptions.append(f"Giả định {dep} là biến phụ thuộc vì được nhắc trước.")
        return AnalysisBundle("ols", "Hồi quy OLS được tính bằng statsmodels, không chạy mã do AI sinh.", result, tuple(assumptions))

    if any(term in text for term in ("sim", "beta", "he thong", "phi he thong")):
        if len(selected) < 2:
            raise SafeAnalysisError("SIM cần nêu mã tài sản và cột thị trường.")
        asset, market = selected[0], selected[-1]
        data = numeric[[asset, market]]
        if not _treat_as_returns(request, [asset, market]):
            data = _returns_from_prices(data)
            assumptions.append("Hai cột được xem là giá và đã chuyển thành log-return.")
        data = _aligned(data)
        model = sm.OLS(data[asset], sm.add_constant(data[market], has_constant="add")).fit()
        beta = float(model.params[market])
        market_var = float(data[market].var(ddof=1))
        unsystematic = float(model.mse_resid)
        result = {
            "asset": str(asset), "market": str(market), "n_observations": int(model.nobs),
            "alpha": float(model.params["const"]), "beta": beta,
            "r_squared": float(model.rsquared), "systematic_risk": beta * beta * market_var,
            "unsystematic_risk": unsystematic,
            "total_risk": beta * beta * market_var + unsystematic,
        }
        return AnalysisBundle("sim", "Mô hình chỉ số đơn được tính cục bộ và kiểm tra cỡ mẫu.", result, tuple(assumptions))

    if any(term in text for term in ("danh muc", "portfolio", "w=")):
        data = numeric[selected]
        if not _treat_as_returns(request, selected):
            data = _returns_from_prices(data)
            assumptions.append("Các cột được xem là giá và đã chuyển thành log-return.")
        data = _aligned(data)
        weights = _parse_weights(request, len(selected))
        if weights is None:
            weights = np.repeat(1.0 / len(selected), len(selected))
            assumptions.append("Không thấy W nên dùng trọng số đều.")
        portfolio_returns = data.to_numpy() @ weights
        cov = data.cov()
        result = {
            "assets": [str(c) for c in selected], "weights": dict(zip(map(str, selected), weights.tolist())),
            "n_observations": len(data), "mean_per_period": float(np.mean(portfolio_returns)),
            "variance_per_period": float(np.var(portfolio_returns, ddof=1)),
            "volatility_per_period": float(np.std(portfolio_returns, ddof=1)),
            "covariance": cov,
        }
        return AnalysisBundle("portfolio", "Danh mục được tính bằng W'VW trong bộ máy cố định.", result, tuple(assumptions))

    if any(term in text for term in ("hiep phuong sai", "covariance", "ma tran v")):
        data = numeric[selected]
        if not _treat_as_returns(request, selected):
            data = _returns_from_prices(data)
            assumptions.append("Các cột được xem là giá và đã chuyển thành log-return.")
        data = _aligned(data)
        return AnalysisBundle("covariance", "Ma trận hiệp phương sai được tính cục bộ.", data.cov(), tuple(assumptions))

    if any(term in text for term in ("tuong quan", "correlation")):
        return AnalysisBundle("correlation", "Ma trận tương quan được tính cục bộ.", _aligned(numeric[selected]).corr())

    if any(term in text for term in ("loi suat", "return")):
        returns = _returns_from_prices(numeric[selected])
        result = {
            "returns": returns.tail(200),
            "summary": returns.agg(["mean", "std", "min", "max"]).T,
        }
        return AnalysisBundle("returns", "Đã tính log-return ln(Pt/Pt-1).", result)

    summary = numeric[selected].describe().T
    assumptions.append("Yêu cầu không khớp phép tính chuyên biệt nên trả thống kê mô tả an toàn.")
    return AnalysisBundle("describe", "Thống kê mô tả các cột số.", summary, tuple(assumptions))


def build_explanation_prompt(request: str, bundle: AnalysisBundle) -> str:
    """Build a compact prompt containing results, never raw workbook rows."""

    payload = json.dumps(_serializable(bundle.result), ensure_ascii=False, default=str)
    payload = payload[:MAX_PROMPT_CHARS]
    assumptions = "\n".join(f"- {item}" for item in bundle.assumptions) or "- Không có."
    return (
        "Bạn là giảng viên Kinh tế lượng Tài chính và trợ lý quản trị rủi ro. "
        "Chỉ diễn giải kết quả đã được máy tính cục bộ; không viết mã, không tự tạo thêm con số, "
        "không hứa lợi nhuận và không ra lệnh mua/bán vô điều kiện. Trả lời tiếng Việt ngắn gọn, "
        "nêu ý nghĩa học thuật, giới hạn mẫu và cách kiểm chứng.\n\n"
        f"Yêu cầu người dùng: {request}\n"
        f"Công cụ đã chạy: {bundle.tool}\n"
        f"Giả định:\n{assumptions}\n"
        f"Kết quả máy tính cục bộ:\n{payload}"
    )


def result_for_display(bundle: AnalysisBundle) -> dict[str, Any]:
    return {
        "tool": bundle.tool,
        "narrative": bundle.narrative,
        "result": bundle.result,
        "assumptions": list(bundle.assumptions),
        "code": None,
        "stdout": "",
        "error": None,
    }
