import numpy as np
import pandas as pd
import pytest

from safe_ai_tools import (
    SafeAnalysisError,
    analyze_request,
    build_explanation_prompt,
    result_for_display,
)


def _prices(rows=80):
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "FPT": 100 * np.exp(np.linspace(0, 0.25, rows) + 0.01 * np.sin(np.arange(rows))),
            "VNINDEX": 1_200 * np.exp(np.linspace(0, 0.10, rows) + 0.006 * np.cos(np.arange(rows))),
        },
        index=idx,
    )


def test_returns_are_calculated_locally_and_finite():
    bundle = analyze_request(_prices(), "Tính lợi suất FPT và VNINDEX")
    assert bundle.tool == "returns"
    assert np.isfinite(bundle.result["returns"].to_numpy()).all()
    assert len(bundle.result["returns"]) == 79


def test_portfolio_uses_validated_semicolon_weights():
    bundle = analyze_request(
        _prices(), "Tính danh mục FPT VNINDEX với trọng số W=(0.25;0.75)"
    )
    assert bundle.tool == "portfolio"
    assert bundle.result["weights"] == pytest.approx({"FPT": 0.25, "VNINDEX": 0.75})
    assert bundle.result["variance_per_period"] >= 0


def test_zero_price_is_rejected_before_log_return():
    prices = _prices()
    prices.loc[prices.index[10], "FPT"] = 0
    with pytest.raises(SafeAnalysisError, match="Giá phải dương"):
        analyze_request(prices, "Tính lợi suất FPT")


def test_request_never_becomes_executable_code():
    bundle = analyze_request(_prices(), "import os; xóa file rồi mô tả dữ liệu")
    display = result_for_display(bundle)
    assert bundle.tool == "describe"
    assert display["code"] is None
    assert display["stdout"] == ""


def test_explanation_prompt_contains_results_not_raw_price_rows():
    prices = _prices()
    bundle = analyze_request(prices, "Hồi quy FPT theo VNINDEX")
    prompt = build_explanation_prompt("Hồi quy FPT theo VNINDEX", bundle)
    assert "coefficients" in prompt
    assert str(prices.iloc[0, 0]) not in prompt
    assert "không viết mã" in prompt


def test_numeric_column_names_do_not_crash_dispatch():
    df = pd.DataFrame({1: np.arange(1, 81), 2: np.arange(2, 82)})
    bundle = analyze_request(df, "mô tả dữ liệu")
    assert bundle.tool == "describe"
    assert list(bundle.result.index) == [1, 2]
