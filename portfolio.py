"""Session-friendly portfolio ledger, risk sizing, and trade-plan contracts.

The objects in this module are deliberately independent from Streamlit and do
not fetch market data.  A fill price is the actual execution price (therefore
already reflects slippage); commission and tax are recorded separately.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from enum import Enum
import math
from typing import Any, Mapping
from uuid import uuid4


NO_PROFIT_GUARANTEE = (
    "Đây là kịch bản quản trị rủi ro, không cam kết hoặc đảm bảo lợi nhuận; "
    "giá thực tế có thể nhảy qua (gap) điểm dừng lỗ và làm khoản lỗ lớn hơn dự kiến."
)

__all__ = [
    "Direction",
    "Fill",
    "NO_PROFIT_GUARANTEE",
    "PortfolioLedger",
    "PortfolioValidationError",
    "Position",
    "PositionSizeResult",
    "Side",
    "TradePlan",
    "size_long_position_by_risk",
]


class PortfolioValidationError(ValueError):
    """Raised when a fill, position size, or trade plan is invalid."""


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


def _finite_positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioValidationError(f"Trường {name} phải là giá trị số.") from exc
    valid = number >= 0 if allow_zero else number > 0
    if not math.isfinite(number) or not valid:
        qualifier = "không âm" if allow_zero else "lớn hơn 0"
        raise PortfolioValidationError(f"Trường {name} phải hữu hạn và {qualifier}.")
    return number


def _datetime(value: datetime | str, name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise PortfolioValidationError(
                f"Trường {name} phải là ngày giờ theo chuẩn ISO-8601."
            ) from exc
    raise PortfolioValidationError(
        f"Trường {name} phải là đối tượng ngày giờ (datetime) hoặc chuỗi ISO-8601."
    )


@dataclass(frozen=True)
class Fill:
    """An immutable long-only execution record."""

    symbol: str
    timestamp: datetime
    side: Side | str
    quantity: float
    price: float
    commission: float = 0.0
    tax: float = 0.0
    note: str = ""
    fill_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        symbol = str(self.symbol).strip().upper()
        if not symbol:
            raise PortfolioValidationError("Bắt buộc có mã chứng khoán (symbol).")
        try:
            side = self.side if isinstance(self.side, Side) else Side(str(self.side).upper())
        except ValueError as exc:
            raise PortfolioValidationError(
                "Chiều giao dịch (side) phải là mua (BUY) hoặc bán (SELL)."
            ) from exc
        timestamp = _datetime(self.timestamp, "timestamp")
        quantity = _finite_positive(self.quantity, "quantity")
        price = _finite_positive(self.price, "price")
        commission = _finite_positive(self.commission, "commission", allow_zero=True)
        tax = _finite_positive(self.tax, "tax", allow_zero=True)
        fill_id = str(self.fill_id).strip()
        if not fill_id:
            raise PortfolioValidationError("Bắt buộc có mã khớp lệnh (fill_id).")
        if commission + tax >= quantity * price:
            raise PortfolioValidationError(
                "Tổng phí hoa hồng (commission) và thuế (tax) phải nhỏ hơn giá trị "
                "khớp lệnh (fill notional)."
            )
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "commission", commission)
        object.__setattr__(self, "tax", tax)
        object.__setattr__(self, "fill_id", fill_id)

    @property
    def notional(self) -> float:
        return self.quantity * self.price

    @property
    def transaction_cost(self) -> float:
        return self.commission + self.tax

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["side"] = self.side.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Fill":
        return cls(**dict(payload))


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    average_cost: float = 0.0
    realized_pnl: float = 0.0
    commission_paid: float = 0.0
    tax_paid: float = 0.0

    def copy(self) -> "Position":
        return replace(self)


class PortfolioLedger:
    """Average-cost, cash-backed, long-only fill ledger.

    The serialized representation stores the immutable fill stream and rebuilds
    all derived state on restore, preventing stale session-state totals.
    """

    SCHEMA_VERSION = 1

    def __init__(self, initial_cash: float, *, allow_negative_cash: bool = False):
        self.initial_cash = _finite_positive(initial_cash, "initial_cash")
        self.allow_negative_cash = bool(allow_negative_cash)
        self._cash = self.initial_cash
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []
        self._fill_ids: set[str] = set()

    @property
    def cash(self) -> float:
        return float(self._cash)

    @property
    def fills(self) -> tuple[Fill, ...]:
        return tuple(self._fills)

    @property
    def realized_pnl(self) -> float:
        return float(sum(position.realized_pnl for position in self._positions.values()))

    @property
    def commission_paid(self) -> float:
        return float(sum(position.commission_paid for position in self._positions.values()))

    @property
    def tax_paid(self) -> float:
        return float(sum(position.tax_paid for position in self._positions.values()))

    def position(self, symbol: str) -> Position:
        key = str(symbol).strip().upper()
        return self._positions.get(key, Position(key)).copy()

    def positions(self, *, include_closed: bool = False) -> dict[str, Position]:
        return {
            symbol: position.copy()
            for symbol, position in self._positions.items()
            if include_closed or position.quantity > 0
        }

    def record_fill(self, fill: Fill) -> Position:
        """Apply one fill atomically and return the resulting position copy."""

        if not isinstance(fill, Fill):
            raise PortfolioValidationError(
                "Hàm ghi khớp lệnh (record_fill) yêu cầu một bản ghi khớp lệnh (Fill)."
            )
        if fill.fill_id in self._fill_ids:
            raise PortfolioValidationError(
                f"Mã khớp lệnh (fill_id) bị trùng: {fill.fill_id}."
            )
        if self._fills:
            try:
                is_older = fill.timestamp < self._fills[-1].timestamp
            except TypeError as exc:
                raise PortfolioValidationError(
                    "Mọi thời điểm khớp lệnh (fill timestamp) phải có thông tin múi giờ "
                    "(timezone) tương thích."
                ) from exc
            if is_older:
                raise PortfolioValidationError(
                    "Các khớp lệnh (fills) phải được ghi theo thứ tự thời gian không giảm."
                )
        current = self._positions.get(fill.symbol, Position(fill.symbol)).copy()

        if fill.side is Side.BUY:
            cash_required = fill.notional + fill.transaction_cost
            if not self.allow_negative_cash and cash_required > self._cash + 1e-9:
                raise PortfolioValidationError(
                    f"Không đủ tiền mặt (insufficient cash) cho {fill.symbol}: cần "
                    f"{cash_required:.2f}, hiện có {self._cash:.2f}."
                )
            new_quantity = current.quantity + fill.quantity
            capitalized_cost = (
                current.quantity * current.average_cost
                + fill.notional
                + fill.transaction_cost
            )
            current.quantity = new_quantity
            current.average_cost = capitalized_cost / new_quantity
            self._cash -= cash_required
        else:
            if fill.quantity > current.quantity + 1e-9:
                raise PortfolioValidationError(
                    f"Không thể bán {fill.quantity:g} {fill.symbol}; chỉ có "
                    f"{current.quantity:g} cổ phiếu khả dụng."
                )
            proceeds = fill.notional - fill.transaction_cost
            cost_basis = current.average_cost * fill.quantity
            current.realized_pnl += proceeds - cost_basis
            current.quantity -= fill.quantity
            if abs(current.quantity) < 1e-9:
                current.quantity = 0.0
                current.average_cost = 0.0
            self._cash += proceeds

        current.commission_paid += fill.commission
        current.tax_paid += fill.tax
        self._positions[fill.symbol] = current
        self._fills.append(fill)
        self._fill_ids.add(fill.fill_id)
        return current.copy()

    def snapshot(self, mark_prices: Mapping[str, float]) -> dict[str, Any]:
        """Mark open positions and return JSON-friendly P&L state."""

        marks = {str(k).strip().upper(): v for k, v in mark_prices.items()}
        rows: list[dict[str, float | str]] = []
        market_value = 0.0
        unrealized_pnl = 0.0
        for symbol, position in self.positions().items():
            if symbol not in marks:
                raise PortfolioValidationError(
                    f"Thiếu giá đánh dấu theo thị trường (mark price) cho {symbol}."
                )
            mark = _finite_positive(marks[symbol], f"mark price for {symbol}")
            value = position.quantity * mark
            unrealized = position.quantity * (mark - position.average_cost)
            market_value += value
            unrealized_pnl += unrealized
            rows.append(
                {
                    "symbol": symbol,
                    "quantity": float(position.quantity),
                    "average_cost": float(position.average_cost),
                    "mark_price": mark,
                    "market_value": float(value),
                    "unrealized_pnl": float(unrealized),
                    "realized_pnl": float(position.realized_pnl),
                }
            )
        equity = self._cash + market_value
        return {
            "initial_cash": float(self.initial_cash),
            "cash": float(self._cash),
            "market_value": float(market_value),
            "equity": float(equity),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": float(unrealized_pnl),
            "total_pnl": float(equity - self.initial_cash),
            "commission_paid": self.commission_paid,
            "tax_paid": self.tax_paid,
            "positions": rows,
        }

    def to_session_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "initial_cash": float(self.initial_cash),
            "allow_negative_cash": self.allow_negative_cash,
            "fills": [fill.to_dict() for fill in self._fills],
        }

    @classmethod
    def from_session_state(cls, payload: Mapping[str, Any]) -> "PortfolioLedger":
        if int(payload.get("schema_version", -1)) != cls.SCHEMA_VERSION:
            raise PortfolioValidationError(
                "Phiên bản cấu trúc sổ giao dịch (schema_version) không được hỗ trợ."
            )
        ledger = cls(
            payload["initial_cash"],
            allow_negative_cash=bool(payload.get("allow_negative_cash", False)),
        )
        for item in payload.get("fills", []):
            ledger.record_fill(Fill.from_dict(item))
        return ledger


@dataclass(frozen=True)
class PositionSizeResult:
    quantity: int
    risk_budget: float
    estimated_loss_at_stop: float
    capital_required: float
    risk_per_share: float
    binding_constraint: str
    lot_size: int
    warning: str = NO_PROFIT_GUARANTEE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def size_long_position_by_risk(
    *,
    capital: float,
    risk_fraction: float,
    entry_price: float,
    stop_price: float,
    lot_size: int = 100,
    max_position_fraction: float = 0.25,
    available_cash: float | None = None,
    estimated_entry_cost_bps: float = 0.0,
    estimated_exit_cost_bps: float = 0.0,
) -> PositionSizeResult:
    """Size a long position from loss-at-stop and capital constraints.

    The loss estimate includes configurable entry/exit costs but cannot model a
    gap through the stop; callers must retain that tail-risk warning.
    """

    capital = _finite_positive(capital, "capital")
    entry_price = _finite_positive(entry_price, "entry_price")
    stop_price = _finite_positive(stop_price, "stop_price")
    if stop_price >= entry_price:
        raise PortfolioValidationError(
            "Điểm dừng lỗ của vị thế mua (long position) phải thấp hơn giá vào lệnh "
            "(entry_price)."
        )
    try:
        risk_fraction = float(risk_fraction)
        max_position_fraction = float(max_position_fraction)
    except (TypeError, ValueError) as exc:
        raise PortfolioValidationError(
            "Tỷ lệ rủi ro (risk_fraction) và tỷ lệ vị thế tối đa "
            "(max_position_fraction) phải là giá trị số."
        ) from exc
    if not math.isfinite(risk_fraction) or not 0 < risk_fraction < 1:
        raise PortfolioValidationError(
            "Tỷ lệ rủi ro (risk_fraction) phải nằm giữa 0 và 1."
        )
    if not math.isfinite(max_position_fraction) or not 0 < max_position_fraction <= 1:
        raise PortfolioValidationError(
            "Tỷ lệ vị thế tối đa (max_position_fraction) phải thuộc khoảng (0, 1]."
        )
    if not isinstance(lot_size, int) or lot_size <= 0:
        raise PortfolioValidationError(
            "Kích thước lô (lot_size) phải là số nguyên lớn hơn 0."
        )
    entry_cost_bps = _finite_positive(
        estimated_entry_cost_bps, "estimated_entry_cost_bps", allow_zero=True
    )
    exit_cost_bps = _finite_positive(
        estimated_exit_cost_bps, "estimated_exit_cost_bps", allow_zero=True
    )
    cash = capital if available_cash is None else _finite_positive(
        available_cash, "available_cash", allow_zero=True
    )

    risk_budget = capital * risk_fraction
    entry_cost_per_share = entry_price * entry_cost_bps / 10_000.0
    exit_cost_per_share = stop_price * exit_cost_bps / 10_000.0
    risk_per_share = entry_price - stop_price + entry_cost_per_share + exit_cost_per_share
    capital_per_share = entry_price + entry_cost_per_share
    max_capital = min(capital * max_position_fraction, cash)
    risk_quantity = math.floor((risk_budget / risk_per_share) / lot_size) * lot_size
    capital_quantity = math.floor((max_capital / capital_per_share) / lot_size) * lot_size
    quantity = max(0, min(risk_quantity, capital_quantity))
    binding = "risk_budget" if risk_quantity <= capital_quantity else "capital_limit"
    return PositionSizeResult(
        quantity=int(quantity),
        risk_budget=float(risk_budget),
        estimated_loss_at_stop=float(quantity * risk_per_share),
        capital_required=float(quantity * capital_per_share),
        risk_per_share=float(risk_per_share),
        binding_constraint=binding,
        lot_size=lot_size,
    )


@dataclass(frozen=True)
class TradePlan:
    """Validated scenario plan; confidence is heuristic, not a probability."""

    plan_id: str
    symbol: str
    direction: Direction | str
    created_at: datetime
    expires_at: datetime
    entry_zone_low: float
    entry_zone_high: float
    trigger: str
    stop_price: float
    targets: tuple[float, ...]
    confidence: float
    thesis: str = ""
    invalidation: str = ""

    def __post_init__(self) -> None:
        plan_id = str(self.plan_id).strip()
        symbol = str(self.symbol).strip().upper()
        if not plan_id or not symbol:
            raise PortfolioValidationError(
                "Bắt buộc có mã kế hoạch (plan_id) và mã chứng khoán (symbol)."
            )
        try:
            direction = (
                self.direction
                if isinstance(self.direction, Direction)
                else Direction(str(self.direction).upper())
            )
        except ValueError as exc:
            raise PortfolioValidationError(
                "Hướng vị thế (direction) phải là mua (LONG) hoặc bán khống (SHORT)."
            ) from exc
        created_at = _datetime(self.created_at, "created_at")
        expires_at = _datetime(self.expires_at, "expires_at")
        if (created_at.tzinfo is None) != (expires_at.tzinfo is None):
            raise PortfolioValidationError(
                "Thời điểm tạo (created_at) và hết hạn (expires_at) phải có thông tin "
                "múi giờ (timezone) tương thích."
            )
        if expires_at <= created_at:
            raise PortfolioValidationError(
                "Thời điểm hết hạn (expires_at) phải sau thời điểm tạo (created_at)."
            )
        low = _finite_positive(self.entry_zone_low, "entry_zone_low")
        high = _finite_positive(self.entry_zone_high, "entry_zone_high")
        if low > high:
            raise PortfolioValidationError(
                "Cận dưới vùng vào lệnh (entry_zone_low) không được vượt cận trên "
                "(entry_zone_high)."
            )
        stop = _finite_positive(self.stop_price, "stop_price")
        targets = tuple(_finite_positive(v, "target") for v in self.targets)
        if not targets:
            raise PortfolioValidationError("Cần ít nhất một giá mục tiêu (target).")
        trigger = str(self.trigger).strip()
        if not trigger:
            raise PortfolioValidationError(
                "Bắt buộc có điều kiện kích hoạt (trigger) và điều kiện này phải quan sát được."
            )
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise PortfolioValidationError(
                "Điểm tin cậy (confidence) phải nằm giữa 0 và 1."
            )

        if direction is Direction.LONG:
            if stop >= low:
                raise PortfolioValidationError(
                    "Giá dừng lỗ (stop_price) của vị thế mua (LONG) phải thấp hơn toàn "
                    "bộ vùng vào lệnh."
                )
            if any(target <= high for target in targets):
                raise PortfolioValidationError(
                    "Mọi giá mục tiêu (target) của vị thế mua (LONG) phải cao hơn toàn "
                    "bộ vùng vào lệnh."
                )
            if tuple(sorted(targets)) != targets:
                raise PortfolioValidationError(
                    "Các giá mục tiêu (targets) của vị thế mua (LONG) phải tăng dần."
                )
        else:
            if stop <= high:
                raise PortfolioValidationError(
                    "Giá dừng lỗ (stop_price) của vị thế bán khống (SHORT) phải cao hơn "
                    "toàn bộ vùng vào lệnh."
                )
            if any(target >= low for target in targets):
                raise PortfolioValidationError(
                    "Mọi giá mục tiêu (target) của vị thế bán khống (SHORT) phải thấp hơn "
                    "toàn bộ vùng vào lệnh."
                )
            if tuple(sorted(targets, reverse=True)) != targets:
                raise PortfolioValidationError(
                    "Các giá mục tiêu (targets) của vị thế bán khống (SHORT) phải giảm dần."
                )

        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "entry_zone_low", low)
        object.__setattr__(self, "entry_zone_high", high)
        object.__setattr__(self, "stop_price", stop)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "confidence", confidence)

    @property
    def conservative_entry(self) -> float:
        return (
            self.entry_zone_high
            if self.direction is Direction.LONG
            else self.entry_zone_low
        )

    @property
    def risk_per_share(self) -> float:
        return abs(self.conservative_entry - self.stop_price)

    @property
    def risk_reward_ratios(self) -> tuple[float, ...]:
        entry = self.conservative_entry
        return tuple(abs(target - entry) / self.risk_per_share for target in self.targets)

    def is_expired(self, now: datetime | str) -> bool:
        current = _datetime(now, "now")
        if (current.tzinfo is None) != (self.expires_at.tzinfo is None):
            raise PortfolioValidationError(
                "Thời điểm hiện tại (now) có thông tin múi giờ (timezone) không tương thích."
            )
        return current >= self.expires_at

    def is_price_in_entry_zone(self, price: float, now: datetime | str) -> bool:
        value = _finite_positive(price, "price")
        return not self.is_expired(now) and self.entry_zone_low <= value <= self.entry_zone_high

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "entry_zone_low": self.entry_zone_low,
            "entry_zone_high": self.entry_zone_high,
            "trigger": self.trigger,
            "stop_price": self.stop_price,
            "targets": list(self.targets),
            "confidence": self.confidence,
            "confidence_note": (
                "Chỉ là điểm kinh nghiệm (heuristic score), không phải xác suất thành công."
            ),
            "thesis": self.thesis,
            "invalidation": self.invalidation,
            "risk_reward_ratios": list(self.risk_reward_ratios),
            "disclaimer": NO_PROFIT_GUARANTEE,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradePlan":
        allowed = {
            "plan_id",
            "symbol",
            "direction",
            "created_at",
            "expires_at",
            "entry_zone_low",
            "entry_zone_high",
            "trigger",
            "stop_price",
            "targets",
            "confidence",
            "thesis",
            "invalidation",
        }
        values = {key: value for key, value in payload.items() if key in allowed}
        if "targets" in values:
            values["targets"] = tuple(values["targets"])
        return cls(**values)
