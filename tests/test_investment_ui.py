from datetime import datetime, timedelta
import json

import numpy as np
import pandas as pd
import pytest

from investment_ui import (
    DEFAULT_PAPER_COMMISSION_BPS,
    DEFAULT_PAPER_SELL_TAX_BPS,
    PAPER_LEDGER_MONEY_UNIT,
    PAPER_LEDGER_PRICE_UNIT,
    VIETNAM_TZ,
    _backtest_research_gate,
    _cap_long_weights,
    _eligible_paper_marks,
    _estimate_paper_trade_costs,
    _latest_marks,
    _ledger_backup_bytes,
    _ledger_from_backup_bytes,
    _ledger_payload,
    _monitor_open_positions,
    _paper_fill_from_board_price,
    _scenario_from_prices,
    _screen_assets,
    _size_plan_in_vnd,
)
from portfolio import PortfolioLedger, PortfolioValidationError, TradePlan


def _prices(rows=100):
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "FPT": 100 * np.exp(np.linspace(0, 0.18, rows) + 0.01 * np.sin(np.arange(rows))),
            "HPG": 30 * np.exp(np.linspace(0, -0.06, rows) + 0.015 * np.cos(np.arange(rows))),
        },
        index=idx,
    )


def _open_ctg_ledger() -> PortfolioLedger:
    ledger = PortfolioLedger(500_000_000)
    ledger.record_fill(
        _paper_fill_from_board_price(
            symbol="CTG",
            timestamp=datetime(2026, 8, 14, 9, 15, tzinfo=VIETNAM_TZ),
            side="BUY",
            quantity=100,
            board_price=32.4,
            commission=0,
            tax=0,
        )
    )
    return ledger


def _ctg_monitor_plan(now: datetime, *, expired: bool = False) -> TradePlan:
    return TradePlan(
        plan_id="ctg-monitor",
        symbol="CTG",
        direction="LONG",
        created_at=now - timedelta(days=2),
        expires_at=now - timedelta(seconds=1) if expired else now + timedelta(days=2),
        entry_zone_low=32.0,
        entry_zone_high=32.4,
        trigger="Only enter inside the validated zone",
        stop_price=30.0,
        targets=(35.0, 38.0),
        confidence=0.5,
    )


def test_scenario_has_expiry_stop_and_two_to_one_first_target():
    plan = _scenario_from_prices("FPT", _prices()["FPT"])
    assert plan.stop_price < plan.entry_zone_low <= plan.entry_zone_high
    assert plan.expires_at > plan.created_at
    assert plan.risk_reward_ratios[0] == 2.0
    assert 0 <= plan.confidence <= 0.75
    assert str(plan.created_at.tzinfo) == "Asia/Ho_Chi_Minh"


def test_weight_cap_leaves_cash_when_needed():
    capped = _cap_long_weights(pd.Series({"A": 0.9, "B": 0.1}), 0.35)
    assert (capped <= 0.35 + 1e-12).all()
    assert np.isclose(capped.sum(), 0.70)


def test_backtest_research_gate_requires_meaningful_oos_evidence():
    passed, table = _backtest_research_gate(
        {
            "sharpe": 0.75,
            "max_drawdown": -0.18,
            "observations": 126,
            "rebalance_count": 6,
        },
        {"total_return_excess": 0.01},
    )
    assert passed
    assert set(table["Trạng thái"]) == {"ĐẠT"}

    too_short, failed_table = _backtest_research_gate(
        {
            "sharpe": 1.50,
            "max_drawdown": -0.05,
            "observations": 60,
            "rebalance_count": 3,
        },
        {"total_return_excess": 0.20},
    )
    assert not too_short
    assert "CHƯA ĐẠT" in set(failed_table["Trạng thái"])


@pytest.mark.parametrize(
    "metrics, comparison",
    [
        ({"sharpe": pd.NA, "max_drawdown": -0.1, "observations": 126, "rebalance_count": 6}, {"total_return_excess": 0.1}),
        ({"sharpe": np.inf, "max_drawdown": -0.1, "observations": 126, "rebalance_count": 6}, {"total_return_excess": 0.1}),
        ({"sharpe": 1.0, "max_drawdown": np.inf, "observations": 126, "rebalance_count": 6}, {"total_return_excess": 0.1}),
        ({"sharpe": 1.0, "max_drawdown": -0.1, "observations": "N/A", "rebalance_count": 6}, {"total_return_excess": 0.1}),
        ({"sharpe": 1.0, "max_drawdown": -0.1, "observations": 126, "rebalance_count": 6}, {"total_return_excess": np.inf}),
    ],
)
def test_backtest_research_gate_fails_closed_on_invalid_metrics(metrics, comparison):
    passed, table = _backtest_research_gate(metrics, comparison)
    assert not passed
    assert "CHƯA ĐẠT" in set(table["Trạng thái"])


def test_screen_exposes_trend_risk_and_drawdown_without_buy_label():
    frame = _screen_assets(
        _prices(), ["FPT", "HPG"],
        [{"Mã CP": "FPT", "Beta (Độ nhạy)": 1.1}, {"Mã CP": "HPG", "Beta (Độ nhạy)": 0.9}],
    )
    assert set(frame["Mã"]) == {"FPT", "HPG"}
    assert {"Biến động năm hóa", "Drawdown 60 phiên", "Trạng thái mẫu"}.issubset(frame.columns)
    assert not frame.astype(str).apply(lambda col: col.str.contains("mua", case=False).any()).any()


def test_paper_trade_marks_fail_closed_without_analyzed_equities():
    prices = pd.DataFrame(
        {
            "CTG": [32.4],
            "FPT": [101.5],
            "VNINDEX": [1_650.0],
        }
    )

    assert _eligible_paper_marks(prices, []) == {}
    assert _eligible_paper_marks(prices, None) == {}

    marks = _eligible_paper_marks(prices, ["CTG"])
    assert marks == {"CTG": 32_400.0}
    assert "FPT" not in marks
    assert "VNINDEX" not in marks


def test_ctg_board_quote_is_converted_to_vnd_before_position_sizing():
    now = pd.Timestamp("2026-08-14 09:00:00").to_pydatetime()
    plan = TradePlan(
        plan_id="ctg-unit-regression",
        symbol="CTG",
        direction="LONG",
        created_at=now,
        expires_at=now + timedelta(days=5),
        entry_zone_low=32.0,
        entry_zone_high=32.4,
        trigger="Only enter inside the price zone",
        stop_price=30.0,
        targets=(37.2,),
        confidence=0.5,
    )

    sizing = _size_plan_in_vnd(
        plan,
        capital=500_000_000,
        risk_fraction=0.0075,
        max_position_fraction=0.20,
    )

    assert sizing.quantity == 1_400
    assert sizing.quantity < 10_000
    assert sizing.capital_required == pytest.approx(45_428_040)
    assert sizing.capital_required <= 100_000_000


def test_paper_fill_and_marks_use_vnd_inside_ledger():
    ledger = PortfolioLedger(500_000_000)
    timestamp = pd.Timestamp("2026-08-14 09:15:00").to_pydatetime()
    fill = _paper_fill_from_board_price(
        symbol="CTG",
        timestamp=timestamp,
        side="BUY",
        quantity=100,
        board_price=32.4,
    )
    ledger.record_fill(fill)

    assert fill.price == pytest.approx(32_400)
    assert fill.notional == pytest.approx(3_240_000)
    assert fill.commission == pytest.approx(4_860)
    assert fill.tax == 0
    assert ledger.cash == pytest.approx(496_755_140)

    marks = _latest_marks(
        pd.DataFrame({"CTG": [32.4], "VNINDEX": [1_650.0]}),
        symbols=["CTG"],
    )
    assert marks["CTG"] == pytest.approx(32_400)
    assert "VNINDEX" not in marks
    snapshot = ledger.snapshot(marks)
    assert snapshot["market_value"] == pytest.approx(3_240_000)
    assert snapshot["unrealized_pnl"] == pytest.approx(-4_860)

    sell = _paper_fill_from_board_price(
        symbol="CTG",
        timestamp=timestamp + timedelta(minutes=1),
        side="SELL",
        quantity=100,
        board_price=32.4,
    )
    ledger.record_fill(sell)
    assert sell.commission == pytest.approx(4_860)
    assert sell.tax == pytest.approx(3_240)
    assert ledger.realized_pnl == pytest.approx(-12_960)
    assert ledger.cash == pytest.approx(499_987_040)

    payload = _ledger_payload(ledger)
    assert payload["money_unit"] == PAPER_LEDGER_MONEY_UNIT
    assert payload["price_unit"] == PAPER_LEDGER_PRICE_UNIT


@pytest.mark.parametrize(
    "side, expected_tax, expected_cash_flow",
    [
        ("BUY", 0.0, -3_244_860.0),
        ("SELL", 3_240.0, 3_231_900.0),
    ],
)
def test_default_paper_cost_model_is_exact_and_tax_is_sell_only(
    side, expected_tax, expected_cash_flow
):
    costs = _estimate_paper_trade_costs(
        side=side,
        quantity=100,
        board_price=32.4,
    )

    assert DEFAULT_PAPER_COMMISSION_BPS == 15.0
    assert DEFAULT_PAPER_SELL_TAX_BPS == 10.0
    assert costs == {
        "notional_vnd": 3_240_000.0,
        "commission_vnd": 4_860.0,
        "tax_vnd": expected_tax,
        "total_cost_vnd": 4_860.0 + expected_tax,
        "net_cash_flow_vnd": expected_cash_flow,
    }


@pytest.mark.parametrize(
    "mark_board, expected_status",
    [
        (33.0, "MONITORING"),
        (35.0, "TARGET_1"),
        (38.0, "FINAL_TARGET"),
        (29.5, "STOP_BREACHED"),
    ],
)
def test_open_position_monitor_assigns_exact_ctg_price_statuses(
    mark_board, expected_status
):
    now = datetime(2026, 8, 14, 10, 0, tzinfo=VIETNAM_TZ)
    plan = _ctg_monitor_plan(now)

    table = _monitor_open_positions(
        _open_ctg_ledger(),
        {"CTG": mark_board * 1_000},
        {"CTG": plan.to_dict()},
        now=now,
    )

    assert len(table) == 1
    assert table.iloc[0]["Trạng thái"] == expected_status
    assert "Không cam kết lợi nhuận" in table.iloc[0]["Hành động có điều kiện"]
    assert "không tự đặt lệnh" in table.iloc[0]["Hành động có điều kiện"]


def test_open_position_monitor_preserves_units_and_exact_distances():
    now = datetime(2026, 8, 14, 10, 0, tzinfo=VIETNAM_TZ)
    plan = _ctg_monitor_plan(now)

    row = _monitor_open_positions(
        _open_ctg_ledger(),
        {"CTG": 33_000},
        {"CTG": plan.to_dict()},
        now=now,
    ).iloc[0]

    assert row["Giá vốn (nghìn VND/cp)"] == pytest.approx(32.4)
    assert row["Mark EOD/manual (nghìn VND/cp)"] == pytest.approx(33.0)
    assert row["P&L (%)"] == pytest.approx(33_000 / 32_400 - 1.0)
    assert row["Stop (nghìn VND/cp)"] == pytest.approx(30.0)
    assert row["Mục tiêu 1 (nghìn VND/cp)"] == pytest.approx(35.0)
    assert row["Mục tiêu cuối (nghìn VND/cp)"] == pytest.approx(38.0)
    assert row["Khoảng cách tới stop (%)"] == pytest.approx((33.0 - 30.0) / 33.0)
    assert row["Khoảng cách tới mục tiêu kế tiếp (%)"] == pytest.approx(
        (35.0 - 33.0) / 33.0
    )


def test_open_position_monitor_expires_before_price_alerts():
    now = datetime(2026, 8, 14, 10, 0, tzinfo=VIETNAM_TZ)
    expired_plan = _ctg_monitor_plan(now, expired=True)

    row = _monitor_open_positions(
        _open_ctg_ledger(),
        {"CTG": 29_000},
        {"CTG": expired_plan.to_dict()},
        now=now,
    ).iloc[0]

    assert row["Trạng thái"] == "PLAN_EXPIRED"
    assert np.isnan(row["Khoảng cách tới mục tiêu kế tiếp (%)"])


@pytest.mark.parametrize(
    "plans",
    [
        {},
        {"CTG": "malformed"},
        {"CTG": {"symbol": "CTG", "stop_price": "not-a-number"}},
    ],
)
def test_open_position_monitor_malformed_or_missing_plan_fails_closed(plans):
    now = datetime(2026, 8, 14, 10, 0, tzinfo=VIETNAM_TZ)

    row = _monitor_open_positions(
        _open_ctg_ledger(),
        {"CTG": 33_000},
        plans,
        now=now,
    ).iloc[0]

    assert row["Trạng thái"] == "NO_PLAN"
    assert np.isnan(row["Stop (nghìn VND/cp)"])


def test_paper_ledger_json_backup_round_trip_preserves_vnd_contract():
    ledger = PortfolioLedger(500_000_000)
    ledger.record_fill(
        _paper_fill_from_board_price(
            symbol="CTG",
            timestamp=pd.Timestamp("2026-08-14 09:15:00").to_pydatetime(),
            side="BUY",
            quantity=100,
            board_price=32.4,
            commission=4_860,
        )
    )

    restored = _ledger_from_backup_bytes(_ledger_backup_bytes(ledger))

    assert restored.initial_cash == pytest.approx(ledger.initial_cash)
    assert restored.cash == pytest.approx(ledger.cash)
    assert restored.fills == ledger.fills
    assert restored.position("CTG").average_cost == pytest.approx(
        ledger.position("CTG").average_cost
    )


@pytest.mark.parametrize(
    "bad_payload",
    [
        b"not-json",
        b"[]",
        b'{"schema_version":1,"initial_cash":500000000,"fills":[]}',
    ],
)
def test_paper_ledger_backup_rejects_invalid_or_unitless_payload(bad_payload):
    with pytest.raises(PortfolioValidationError, match="JSON|metadata"):
        _ledger_from_backup_bytes(bad_payload)


@pytest.mark.parametrize(
    "override",
    [
        {"allow_negative_cash": "false"},
        {"allow_negative_cash": True},
        {"schema_version": "abc"},
        {"fills": [None]},
    ],
)
def test_paper_ledger_backup_normalizes_malformed_payload_errors(override):
    payload = {
        "schema_version": 1,
        "initial_cash": 500_000_000,
        "allow_negative_cash": False,
        "fills": [],
        "money_unit": PAPER_LEDGER_MONEY_UNIT,
        "price_unit": PAPER_LEDGER_PRICE_UNIT,
    }
    payload.update(override)

    with pytest.raises(PortfolioValidationError, match="Backup|backup|Cấu trúc"):
        _ledger_from_backup_bytes(json.dumps(payload).encode("utf-8"))
