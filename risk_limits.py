"""Hạn mức rủi ro và cổng xác nhận hai bước.

ROADMAP yêu cầu: hạn mức vốn, tỷ trọng mỗi mã và mỗi ngành, mức lỗ ngày/tháng,
thời gian chờ trước lệnh, và xác nhận hai bước với kế hoạch vượt ngưỡng.

Phân biệt hai mức vi phạm:

- **CHẶN** — không có đường đi tiếp. Dùng cho ràng buộc theo tuổi, thứ mà người
  học không được tự nới.
- **CẦN XÁC NHẬN HAI BƯỚC** — kế hoạch vượt ngưỡng mềm; người học phải xác nhận
  riêng một lần nữa, có ghi nhật ký.

Mọi hàm ở đây là logic thuần, không phụ thuộc Streamlit, để kiểm thử được.
Ứng dụng vẫn không đặt lệnh; các hạn mức này áp lên *kế hoạch* và danh mục
mô phỏng.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import readiness_gate as rg

SEVERITY_BLOCK = "chan"
SEVERITY_CONFIRM = "can_xac_nhan"

# Trần cứng theo nhóm tuổi. Người học không thể nới quá các giá trị này.
HARD_CEILINGS: dict[str, dict[str, float]] = {
    rg.AGE_UNDER_15: {
        "capital_cap_vnd": 0.0,
        "max_position_fraction": 0.0,
        "max_sector_fraction": 0.0,
    },
    rg.AGE_15_17: {
        "capital_cap_vnd": 20_000_000.0,
        "max_position_fraction": 0.20,
        "max_sector_fraction": 0.40,
    },
    rg.AGE_18_PLUS: {
        "capital_cap_vnd": float("inf"),
        "max_position_fraction": 0.35,
        "max_sector_fraction": 0.60,
    },
}

# Thời gian chờ tối thiểu giữa lúc lập kế hoạch và lúc thực hiện.
MIN_COOLDOWN_MINUTES = {
    rg.AGE_UNDER_15: 0,        # không dùng vốn thật nên không áp dụng
    rg.AGE_15_17: 60,
    rg.AGE_18_PLUS: 15,
}


@dataclass(frozen=True)
class RiskLimits:
    capital_cap_vnd: float = 10_000_000.0
    max_position_fraction: float = 0.20
    max_sector_fraction: float = 0.40
    max_daily_loss_fraction: float = 0.02
    max_monthly_loss_fraction: float = 0.06
    cooldown_minutes: int = 60

    def as_dict(self) -> dict[str, Any]:
        return {
            "capital_cap_vnd": self.capital_cap_vnd,
            "max_position_fraction": self.max_position_fraction,
            "max_sector_fraction": self.max_sector_fraction,
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_monthly_loss_fraction": self.max_monthly_loss_fraction,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass(frozen=True)
class Breach:
    code: str
    severity: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.severity == SEVERITY_BLOCK


def default_limits_for(age_band: Any) -> RiskLimits:
    """Hạn mức khởi tạo, chặt hơn với người chưa đủ 18 tuổi."""

    band = rg.normalise_age_band(age_band)
    if band == rg.AGE_UNDER_15:
        return RiskLimits(
            capital_cap_vnd=0.0, max_position_fraction=0.0,
            max_sector_fraction=0.0, max_daily_loss_fraction=0.0,
            max_monthly_loss_fraction=0.0, cooldown_minutes=0,
        )
    if band == rg.AGE_15_17:
        return RiskLimits(
            capital_cap_vnd=5_000_000.0, max_position_fraction=0.15,
            max_sector_fraction=0.30, max_daily_loss_fraction=0.01,
            max_monthly_loss_fraction=0.03, cooldown_minutes=60,
        )
    if band == rg.AGE_18_PLUS:
        # Thời gian chờ ngắn hơn nhóm 15–18: người trưởng thành tự chịu trách
        # nhiệm, nhưng vẫn giữ một khoảng dừng để tách quyết định khỏi cảm xúc.
        return RiskLimits(cooldown_minutes=MIN_COOLDOWN_MINUTES[rg.AGE_18_PLUS])
    # Chưa khai báo: khoá về 0 cho tới khi chọn nhóm tuổi.
    return RiskLimits(
        capital_cap_vnd=0.0, max_position_fraction=0.0,
        max_sector_fraction=0.0, max_daily_loss_fraction=0.0,
        max_monthly_loss_fraction=0.0, cooldown_minutes=0,
    )


def clamp_to_age(limits: RiskLimits, age_band: Any) -> RiskLimits:
    """Ép hạn mức người dùng nhập về trong trần cứng của nhóm tuổi.

    Người học có thể siết chặt hơn, nhưng không nới rộng quá trần.
    """

    band = rg.normalise_age_band(age_band)
    ceiling = HARD_CEILINGS.get(band)
    if ceiling is None:                       # chưa khai báo tuổi
        return default_limits_for(band)

    min_cooldown = MIN_COOLDOWN_MINUTES.get(band, 60)
    return replace(
        limits,
        capital_cap_vnd=min(max(0.0, limits.capital_cap_vnd), ceiling["capital_cap_vnd"]),
        max_position_fraction=min(
            max(0.0, limits.max_position_fraction), ceiling["max_position_fraction"]
        ),
        max_sector_fraction=min(
            max(0.0, limits.max_sector_fraction), ceiling["max_sector_fraction"]
        ),
        max_daily_loss_fraction=max(0.0, min(limits.max_daily_loss_fraction, 0.10)),
        max_monthly_loss_fraction=max(0.0, min(limits.max_monthly_loss_fraction, 0.25)),
        cooldown_minutes=max(int(limits.cooldown_minutes), min_cooldown),
    )


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return number


def check_plan(
    plan: Mapping[str, Any] | None,
    limits: RiskLimits,
    *,
    age_band: Any = None,
    state: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> list[Breach]:
    """Soát một kế hoạch mua với bộ hạn mức đang áp dụng.

    ``plan`` cần: ``amount_vnd``, ``portfolio_vnd``, ``sector``,
    ``sector_exposure_vnd``, ``planned_at`` (ISO 8601).
    ``state`` cần: ``loss_today_fraction``, ``loss_month_fraction``.
    """

    plan = plan if isinstance(plan, Mapping) else {}
    state = state if isinstance(state, Mapping) else {}
    band = rg.normalise_age_band(age_band)
    breaches: list[Breach] = []

    # 1. Nhóm tuổi chưa được phép dùng vốn thật
    if band in (rg.AGE_UNKNOWN, rg.AGE_UNDER_15):
        breaches.append(Breach(
            "tuoi_chua_du_dieu_kien", SEVERITY_BLOCK,
            "Nhóm tuổi này chỉ dùng giao dịch mô phỏng trong ứng dụng.",
        ))

    amount = _as_float(plan.get("amount_vnd"))
    portfolio = _as_float(plan.get("portfolio_vnd"))

    # 2. Hạn mức vốn
    if amount > limits.capital_cap_vnd:
        breaches.append(Breach(
            "vuot_han_muc_von", SEVERITY_CONFIRM,
            f"Số tiền {amount:,.0f} VND vượt hạn mức vốn "
            f"{limits.capital_cap_vnd:,.0f} VND.",
        ))

    # 3. Tỷ trọng mỗi mã
    if portfolio > 0:
        position_fraction = amount / portfolio
        if position_fraction > limits.max_position_fraction:
            breaches.append(Breach(
                "vuot_ty_trong_ma", SEVERITY_CONFIRM,
                f"Tỷ trọng mã này {position_fraction:.1%} vượt mức tối đa "
                f"{limits.max_position_fraction:.1%}.",
            ))

        # 4. Tỷ trọng mỗi ngành
        sector_after = _as_float(plan.get("sector_exposure_vnd")) + amount
        sector_fraction = sector_after / portfolio
        if sector_fraction > limits.max_sector_fraction:
            sector = str(plan.get("sector") or "chưa phân loại")
            breaches.append(Breach(
                "vuot_ty_trong_nganh", SEVERITY_CONFIRM,
                f"Tỷ trọng ngành “{sector}” sau lệnh là {sector_fraction:.1%}, "
                f"vượt mức tối đa {limits.max_sector_fraction:.1%}.",
            ))

    # 5. Mức lỗ ngày và tháng
    loss_today = abs(_as_float(state.get("loss_today_fraction")))
    if loss_today >= limits.max_daily_loss_fraction > 0:
        breaches.append(Breach(
            "cham_muc_lo_ngay", SEVERITY_BLOCK,
            f"Đã lỗ {loss_today:.1%} trong ngày, chạm giới hạn "
            f"{limits.max_daily_loss_fraction:.1%}. Dừng giao dịch hôm nay.",
        ))
    loss_month = abs(_as_float(state.get("loss_month_fraction")))
    if loss_month >= limits.max_monthly_loss_fraction > 0:
        breaches.append(Breach(
            "cham_muc_lo_thang", SEVERITY_BLOCK,
            f"Đã lỗ {loss_month:.1%} trong tháng, chạm giới hạn "
            f"{limits.max_monthly_loss_fraction:.1%}.",
        ))

    # 6. Thời gian chờ trước lệnh
    remaining = cooldown_remaining(plan.get("planned_at"), limits, now=now)
    if remaining > timedelta(0):
        minutes = remaining.total_seconds() / 60
        breaches.append(Breach(
            "chua_het_thoi_gian_cho", SEVERITY_BLOCK,
            f"Còn {minutes:.0f} phút chờ trước khi được thực hiện kế hoạch này.",
        ))

    return breaches


def cooldown_remaining(
    planned_at: Any, limits: RiskLimits, *, now: datetime | None = None
) -> timedelta:
    """Thời gian còn phải chờ. Thiếu/hỏng mốc thời gian thì coi như chờ đủ."""

    if limits.cooldown_minutes <= 0:
        return timedelta(0)
    if not planned_at:
        return timedelta(0)
    try:
        planned = datetime.fromisoformat(str(planned_at))
    except (TypeError, ValueError):
        return timedelta(0)

    current = now or datetime.now(timezone.utc).astimezone()
    if planned.tzinfo is None and current.tzinfo is not None:
        planned = planned.replace(tzinfo=current.tzinfo)
    if planned.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=planned.tzinfo)

    ready_at = planned + timedelta(minutes=int(limits.cooldown_minutes))
    remaining = ready_at - current
    return remaining if remaining > timedelta(0) else timedelta(0)


def requires_two_step(breaches: list[Breach]) -> bool:
    """Có ngưỡng mềm bị vượt và không có ràng buộc cứng nào chặn."""

    if any(b.blocking for b in breaches):
        return False
    return any(b.severity == SEVERITY_CONFIRM for b in breaches)


def is_blocked(breaches: list[Breach]) -> bool:
    return any(b.blocking for b in breaches)


def plan_allowed(breaches: list[Breach], second_confirmation: bool = False) -> bool:
    """Kế hoạch được phép thực hiện hay không.

    Bị chặn thì không xác nhận nào cứu được. Vượt ngưỡng mềm thì phải có xác
    nhận thứ hai, tách khỏi lần bấm đầu tiên.
    """

    if is_blocked(breaches):
        return False
    if requires_two_step(breaches):
        return bool(second_confirmation)
    return True
