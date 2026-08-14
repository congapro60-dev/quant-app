"""Kiểm thử hạn mức rủi ro và cổng xác nhận hai bước."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import readiness_gate as rg
import risk_limits as rl


NOW = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def _plan(**over):
    base = {
        "amount_vnd": 1_000_000.0,
        "portfolio_vnd": 100_000_000.0,
        "sector": "Ngân hàng",
        "sector_exposure_vnd": 0.0,
        "planned_at": (NOW - timedelta(days=1)).isoformat(),
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Mặc định theo tuổi
# ---------------------------------------------------------------------------

def test_defaults_are_tighter_for_minors():
    under15 = rl.default_limits_for(rg.AGE_UNDER_15)
    teen = rl.default_limits_for(rg.AGE_15_17)
    adult = rl.default_limits_for(rg.AGE_18_PLUS)

    assert under15.capital_cap_vnd == 0.0
    assert teen.capital_cap_vnd < adult.capital_cap_vnd
    assert teen.max_position_fraction < adult.max_position_fraction
    assert teen.max_sector_fraction < adult.max_sector_fraction
    assert teen.cooldown_minutes > adult.cooldown_minutes


def test_undeclared_age_gets_zero_limits():
    limits = rl.default_limits_for(None)
    assert limits.capital_cap_vnd == 0.0
    assert limits.max_position_fraction == 0.0


# ---------------------------------------------------------------------------
# Trần cứng: người học không nới quá được
# ---------------------------------------------------------------------------

def test_user_cannot_raise_limits_above_age_ceiling():
    greedy = rl.RiskLimits(
        capital_cap_vnd=9_000_000_000.0, max_position_fraction=0.99,
        max_sector_fraction=0.99, max_daily_loss_fraction=0.9,
        max_monthly_loss_fraction=0.9, cooldown_minutes=0,
    )
    clamped = rl.clamp_to_age(greedy, rg.AGE_15_17)

    ceiling = rl.HARD_CEILINGS[rg.AGE_15_17]
    assert clamped.capital_cap_vnd == ceiling["capital_cap_vnd"]
    assert clamped.max_position_fraction == ceiling["max_position_fraction"]
    assert clamped.max_sector_fraction == ceiling["max_sector_fraction"]
    assert clamped.cooldown_minutes >= rl.MIN_COOLDOWN_MINUTES[rg.AGE_15_17]


def test_user_may_tighten_below_ceiling():
    careful = rl.RiskLimits(
        capital_cap_vnd=1_000_000.0, max_position_fraction=0.05,
        max_sector_fraction=0.10, cooldown_minutes=240,
    )
    clamped = rl.clamp_to_age(careful, rg.AGE_18_PLUS)
    assert clamped.capital_cap_vnd == 1_000_000.0
    assert clamped.max_position_fraction == 0.05
    assert clamped.cooldown_minutes == 240


def test_cooldown_cannot_be_set_below_age_minimum():
    limits = rl.clamp_to_age(rl.RiskLimits(cooldown_minutes=0), rg.AGE_15_17)
    assert limits.cooldown_minutes == rl.MIN_COOLDOWN_MINUTES[rg.AGE_15_17]


def test_negative_values_are_floored_at_zero():
    weird = rl.RiskLimits(
        capital_cap_vnd=-5.0, max_position_fraction=-1.0, max_sector_fraction=-1.0,
    )
    clamped = rl.clamp_to_age(weird, rg.AGE_18_PLUS)
    assert clamped.capital_cap_vnd == 0.0
    assert clamped.max_position_fraction == 0.0


# ---------------------------------------------------------------------------
# Soát kế hoạch
# ---------------------------------------------------------------------------

def test_plan_within_all_limits_passes():
    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    breaches = rl.check_plan(_plan(), limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert breaches == []
    assert rl.plan_allowed(breaches) is True


def test_minor_is_blocked_regardless_of_amount():
    limits = rl.default_limits_for(rg.AGE_UNDER_15)
    breaches = rl.check_plan(
        _plan(amount_vnd=1.0), limits, age_band=rg.AGE_UNDER_15, now=NOW
    )
    assert rl.is_blocked(breaches) is True
    assert rl.plan_allowed(breaches, second_confirmation=True) is False


def test_capital_cap_breach_needs_second_confirmation():
    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    plan = _plan(amount_vnd=limits.capital_cap_vnd + 1_000_000)
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)

    assert any(b.code == "vuot_han_muc_von" for b in breaches)
    assert rl.requires_two_step(breaches) is True
    assert rl.plan_allowed(breaches, second_confirmation=False) is False
    assert rl.plan_allowed(breaches, second_confirmation=True) is True


def test_position_fraction_breach_detected():
    limits = rl.RiskLimits(capital_cap_vnd=1e12, max_position_fraction=0.10)
    plan = _plan(amount_vnd=30_000_000, portfolio_vnd=100_000_000)
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert any(b.code == "vuot_ty_trong_ma" for b in breaches)


def test_sector_fraction_counts_existing_exposure():
    """Tỷ trọng ngành tính cả phần đang nắm, không chỉ lệnh mới."""

    limits = rl.RiskLimits(
        capital_cap_vnd=1e12, max_position_fraction=0.99, max_sector_fraction=0.30
    )
    plan = _plan(
        amount_vnd=10_000_000, portfolio_vnd=100_000_000,
        sector_exposure_vnd=25_000_000,
    )
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert any(b.code == "vuot_ty_trong_nganh" for b in breaches)


def test_sector_within_limit_when_existing_exposure_small():
    limits = rl.RiskLimits(
        capital_cap_vnd=1e12, max_position_fraction=0.99, max_sector_fraction=0.30
    )
    plan = _plan(
        amount_vnd=5_000_000, portfolio_vnd=100_000_000,
        sector_exposure_vnd=10_000_000,
    )
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert not any(b.code == "vuot_ty_trong_nganh" for b in breaches)


def test_daily_loss_limit_blocks_further_trading():
    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    breaches = rl.check_plan(
        _plan(), limits, age_band=rg.AGE_18_PLUS,
        state={"loss_today_fraction": -0.05}, now=NOW,
    )
    codes = [b.code for b in breaches]
    assert "cham_muc_lo_ngay" in codes
    assert rl.is_blocked(breaches) is True


def test_monthly_loss_limit_blocks_further_trading():
    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    breaches = rl.check_plan(
        _plan(), limits, age_band=rg.AGE_18_PLUS,
        state={"loss_month_fraction": -0.20}, now=NOW,
    )
    assert any(b.code == "cham_muc_lo_thang" for b in breaches)
    assert rl.is_blocked(breaches) is True


def test_loss_limits_use_absolute_value_of_sign():
    """Lỗ ghi âm hay dương đều phải nhận ra."""

    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    for value in (-0.05, 0.05):
        breaches = rl.check_plan(
            _plan(), limits, age_band=rg.AGE_18_PLUS,
            state={"loss_today_fraction": value}, now=NOW,
        )
        assert any(b.code == "cham_muc_lo_ngay" for b in breaches)


# ---------------------------------------------------------------------------
# Thời gian chờ trước lệnh
# ---------------------------------------------------------------------------

def test_plan_made_just_now_must_wait():
    limits = rl.RiskLimits(cooldown_minutes=60)
    plan = _plan(planned_at=(NOW - timedelta(minutes=5)).isoformat())
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert any(b.code == "chua_het_thoi_gian_cho" for b in breaches)
    assert rl.is_blocked(breaches) is True


def test_plan_past_cooldown_is_allowed():
    limits = rl.RiskLimits(cooldown_minutes=60)
    plan = _plan(planned_at=(NOW - timedelta(minutes=61)).isoformat())
    breaches = rl.check_plan(plan, limits, age_band=rg.AGE_18_PLUS, now=NOW)
    assert not any(b.code == "chua_het_thoi_gian_cho" for b in breaches)


def test_cooldown_remaining_handles_bad_timestamps():
    limits = rl.RiskLimits(cooldown_minutes=60)
    for bad in (None, "", "hom qua", 12345, {}):
        assert rl.cooldown_remaining(bad, limits, now=NOW) == timedelta(0)


def test_zero_cooldown_never_waits():
    limits = rl.RiskLimits(cooldown_minutes=0)
    assert rl.cooldown_remaining(NOW.isoformat(), limits, now=NOW) == timedelta(0)


# ---------------------------------------------------------------------------
# Xác nhận hai bước
# ---------------------------------------------------------------------------

def test_hard_block_cannot_be_confirmed_away():
    breaches = [rl.Breach("x", rl.SEVERITY_BLOCK, "chan")]
    assert rl.requires_two_step(breaches) is False
    assert rl.plan_allowed(breaches, second_confirmation=True) is False


def test_block_wins_when_mixed_with_soft_breach():
    breaches = [
        rl.Breach("mem", rl.SEVERITY_CONFIRM, "vuot nguong"),
        rl.Breach("cung", rl.SEVERITY_BLOCK, "chan"),
    ]
    assert rl.plan_allowed(breaches, second_confirmation=True) is False


def test_clean_plan_needs_no_confirmation():
    assert rl.requires_two_step([]) is False
    assert rl.plan_allowed([]) is True


def test_malformed_plan_does_not_crash():
    limits = rl.default_limits_for(rg.AGE_18_PLUS)
    for bad in (None, {}, {"amount_vnd": "nhieu", "portfolio_vnd": None}):
        breaches = rl.check_plan(bad, limits, age_band=rg.AGE_18_PLUS, now=NOW)
        assert isinstance(breaches, list)
