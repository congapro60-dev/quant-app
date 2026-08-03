from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from portfolio import (
    NO_PROFIT_GUARANTEE,
    Direction,
    Fill,
    PortfolioLedger,
    PortfolioValidationError,
    Side,
    TradePlan,
    size_long_position_by_risk,
)


T0 = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def test_average_cost_cash_realized_and_unrealized_pnl():
    ledger = PortfolioLedger(100_000)
    ledger.record_fill(
        Fill("FPT", T0, Side.BUY, 100, 100, commission=10, fill_id="b1")
    )
    ledger.record_fill(
        Fill("FPT", T0 + timedelta(minutes=1), "BUY", 100, 120, commission=10, fill_id="b2")
    )
    position = ledger.record_fill(
        Fill(
            "FPT",
            T0 + timedelta(minutes=2),
            Side.SELL,
            100,
            130,
            commission=10,
            tax=20,
            fill_id="s1",
        )
    )

    assert position.quantity == pytest.approx(100)
    assert position.average_cost == pytest.approx(110.10)
    assert position.realized_pnl == pytest.approx(1_960)
    assert ledger.cash == pytest.approx(90_950)
    snapshot = ledger.snapshot({"FPT": 140})
    assert snapshot["unrealized_pnl"] == pytest.approx(2_990)
    assert snapshot["total_pnl"] == pytest.approx(4_950)
    assert snapshot["equity"] == pytest.approx(104_950)
    assert snapshot["commission_paid"] == pytest.approx(30)
    assert snapshot["tax_paid"] == pytest.approx(20)


def test_ledger_rejects_oversell_insufficient_cash_and_duplicate_fill():
    ledger = PortfolioLedger(1_000)
    with pytest.raises(PortfolioValidationError, match="Insufficient cash"):
        ledger.record_fill(Fill("FPT", T0, "BUY", 100, 20, fill_id="too-big"))

    buy = Fill("FPT", T0, "BUY", 10, 20, fill_id="buy")
    ledger.record_fill(buy)
    with pytest.raises(PortfolioValidationError, match="Duplicate fill_id"):
        ledger.record_fill(buy)
    with pytest.raises(PortfolioValidationError, match="only 10"):
        ledger.record_fill(
            Fill("FPT", T0 + timedelta(minutes=1), "SELL", 11, 20, fill_id="sell")
        )


def test_fill_validation_rejects_impossible_costs_and_mixed_timezones():
    with pytest.raises(PortfolioValidationError, match="smaller than fill notional"):
        Fill("FPT", T0, "BUY", 1, 10, commission=10, fill_id="bad-cost")

    ledger = PortfolioLedger(1_000)
    ledger.record_fill(Fill("FPT", T0, "BUY", 1, 10, fill_id="aware"))
    with pytest.raises(PortfolioValidationError, match="timezone awareness"):
        ledger.record_fill(
            Fill("FPT", datetime(2026, 8, 3, 10), "BUY", 1, 10, fill_id="naive")
        )


def test_ledger_session_round_trip_replays_fills_not_stale_totals():
    ledger = PortfolioLedger(10_000)
    ledger.record_fill(Fill("HPG", T0, "BUY", 100, 25, commission=5, fill_id="1"))
    payload = ledger.to_session_state()
    restored = PortfolioLedger.from_session_state(payload)

    assert restored.to_session_state() == payload
    assert restored.cash == pytest.approx(ledger.cash)
    assert restored.position("HPG") == ledger.position("HPG")


def test_position_sizing_is_risk_budget_bound_and_round_lot():
    result = size_long_position_by_risk(
        capital=1_000_000_000,
        risk_fraction=0.01,
        entry_price=100_000,
        stop_price=90_000,
        lot_size=100,
        max_position_fraction=0.25,
    )
    assert result.quantity == 1_000
    assert result.binding_constraint == "risk_budget"
    assert result.estimated_loss_at_stop == pytest.approx(10_000_000)
    assert result.capital_required == pytest.approx(100_000_000)
    assert result.quantity % 100 == 0
    assert "không cam kết" in result.warning


def test_position_sizing_respects_cash_and_estimated_execution_costs():
    result = size_long_position_by_risk(
        capital=1_000_000,
        available_cash=205_000,
        risk_fraction=0.10,
        entry_price=10_000,
        stop_price=9_500,
        lot_size=10,
        max_position_fraction=1.0,
        estimated_entry_cost_bps=20,
        estimated_exit_cost_bps=30,
    )
    assert result.binding_constraint == "capital_limit"
    assert result.capital_required <= 205_000
    assert result.estimated_loss_at_stop <= result.risk_budget


def test_trade_plan_has_conservative_risk_reward_expiry_and_disclaimer():
    plan = TradePlan(
        plan_id="plan-fpt-1",
        symbol="fpt",
        direction="LONG",
        created_at=T0,
        expires_at=T0 + timedelta(days=5),
        entry_zone_low=100,
        entry_zone_high=102,
        trigger="Daily close above 102 with volume confirmation",
        stop_price=95,
        targets=(110, 116),
        confidence=0.65,
        thesis="Breakout scenario",
        invalidation="Close below 95",
    )

    assert plan.symbol == "FPT"
    assert plan.direction is Direction.LONG
    assert plan.conservative_entry == pytest.approx(102)
    assert plan.risk_reward_ratios == pytest.approx((8 / 7, 2.0))
    assert plan.is_price_in_entry_zone(101, T0 + timedelta(days=1))
    assert plan.is_expired(plan.expires_at)
    assert not plan.is_price_in_entry_zone(101, T0 + timedelta(days=6))
    payload = plan.to_dict()
    assert payload["disclaimer"] == NO_PROFIT_GUARANTEE
    assert "không cam kết" in payload["disclaimer"]
    assert "not a success probability" in payload["confidence_note"]
    assert TradePlan.from_dict(payload) == plan


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"stop_price": 101}, "below the entire entry zone"),
        ({"targets": (101, 110)}, "above the entire entry zone"),
        ({"confidence": 1.1}, "between 0 and 1"),
        ({"expires_at": T0}, "after created_at"),
    ],
)
def test_invalid_trade_plans_are_rejected(changes, message):
    values = {
        "plan_id": "p",
        "symbol": "FPT",
        "direction": "LONG",
        "created_at": T0,
        "expires_at": T0 + timedelta(days=1),
        "entry_zone_low": 100,
        "entry_zone_high": 102,
        "trigger": "Observable trigger",
        "stop_price": 95,
        "targets": (110,),
        "confidence": 0.5,
    }
    values.update(changes)
    with pytest.raises(PortfolioValidationError, match=message):
        TradePlan(**values)


def test_short_trade_plan_uses_conservative_entry_and_decreasing_targets():
    plan = TradePlan(
        plan_id="short-1",
        symbol="VN30F",
        direction="SHORT",
        created_at=T0,
        expires_at=T0 + timedelta(days=1),
        entry_zone_low=100,
        entry_zone_high=102,
        trigger="Break below support",
        stop_price=106,
        targets=(94, 90),
        confidence=0.4,
    )
    assert plan.conservative_entry == pytest.approx(100)
    assert plan.risk_reward_ratios == pytest.approx((1.0, 10 / 6))
