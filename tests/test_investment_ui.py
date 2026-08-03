import numpy as np
import pandas as pd

from investment_ui import _cap_long_weights, _scenario_from_prices, _screen_assets


def _prices(rows=100):
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "FPT": 100 * np.exp(np.linspace(0, 0.18, rows) + 0.01 * np.sin(np.arange(rows))),
            "HPG": 30 * np.exp(np.linspace(0, -0.06, rows) + 0.015 * np.cos(np.arange(rows))),
        },
        index=idx,
    )


def test_scenario_has_expiry_stop_and_two_to_one_first_target():
    plan = _scenario_from_prices("FPT", _prices()["FPT"])
    assert plan.stop_price < plan.entry_zone_low <= plan.entry_zone_high
    assert plan.expires_at > plan.created_at
    assert plan.risk_reward_ratios[0] == 2.0
    assert 0 <= plan.confidence <= 0.75


def test_weight_cap_leaves_cash_when_needed():
    capped = _cap_long_weights(pd.Series({"A": 0.9, "B": 0.1}), 0.35)
    assert (capped <= 0.35 + 1e-12).all()
    assert np.isclose(capped.sum(), 0.70)


def test_screen_exposes_trend_risk_and_drawdown_without_buy_label():
    frame = _screen_assets(
        _prices(), ["FPT", "HPG"],
        [{"Mã CP": "FPT", "Beta (Độ nhạy)": 1.1}, {"Mã CP": "HPG", "Beta (Độ nhạy)": 0.9}],
    )
    assert set(frame["Mã"]) == {"FPT", "HPG"}
    assert {"Biến động năm hóa", "Drawdown 60 phiên", "Trạng thái mẫu"}.issubset(frame.columns)
    assert not frame.astype(str).apply(lambda col: col.str.contains("mua", case=False).any()).any()
