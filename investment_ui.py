"""Streamlit renderers for research, walk-forward tests, and paper trading."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import markowitz_optimization
from backtesting import (
    BacktestConfig,
    BacktestValidationError,
    run_walk_forward,
)
from portfolio import (
    Fill,
    PortfolioLedger,
    PortfolioValidationError,
    Side,
    TradePlan,
    size_long_position_by_risk,
)


# vnstock equity prices are quoted in thousands of VND per share.  The
# portfolio engine deliberately remains unit-agnostic, so this UI module owns
# the conversion into actual VND at every monetary boundary.
BOARD_PRICE_TO_VND = 1_000.0
PAPER_LEDGER_MONEY_UNIT = "VND"
PAPER_LEDGER_PRICE_UNIT = "VND_PER_SHARE"
PAPER_LEDGER_BACKUP_MAX_BYTES = 1_000_000
PAPER_LEDGER_BACKUP_MAX_FILLS = 5_000
DEFAULT_PAPER_COMMISSION_BPS = 15.0
DEFAULT_PAPER_SELL_TAX_BPS = 10.0
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _board_price_to_vnd(price: float) -> float:
    """Convert a Vietnamese board quote (thousand VND/share) to VND/share."""

    return float(price) * BOARD_PRICE_TO_VND


def _vnd_price_to_board(price: float) -> float:
    """Convert VND/share back to the board-display unit."""

    return float(price) / BOARD_PRICE_TO_VND


def _ledger_payload(ledger: PortfolioLedger) -> dict:
    """Serialize a ledger with explicit monetary-unit metadata."""

    payload = ledger.to_session_state()
    payload["money_unit"] = PAPER_LEDGER_MONEY_UNIT
    payload["price_unit"] = PAPER_LEDGER_PRICE_UNIT
    return payload


def _ledger_backup_bytes(ledger: PortfolioLedger) -> bytes:
    """Create a portable, unit-tagged JSON backup for a paper ledger."""

    return json.dumps(
        _ledger_payload(ledger),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _ledger_from_backup_bytes(payload: bytes) -> PortfolioLedger:
    """Validate and restore a paper ledger from an untrusted JSON upload."""

    if not isinstance(payload, (bytes, bytearray)):
        raise PortfolioValidationError(
            "Bản sao lưu (backup) danh mục mô phỏng (paper portfolio) phải là tệp cấu trúc (JSON)."
        )
    if not payload or len(payload) > PAPER_LEDGER_BACKUP_MAX_BYTES:
        raise PortfolioValidationError(
            "Bản sao lưu (backup) danh mục mô phỏng (paper portfolio) trống hoặc vượt giới hạn 1 MB."
        )
    try:
        decoded = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PortfolioValidationError(
            "Bản sao lưu (backup) không phải tệp cấu trúc JSON mã hóa UTF-8 hợp lệ."
        ) from exc
    if not isinstance(decoded, dict):
        raise PortfolioValidationError(
            "Bản sao lưu (backup) phải là một đối tượng (object) JSON."
        )
    if (
        decoded.get("money_unit") != PAPER_LEDGER_MONEY_UNIT
        or decoded.get("price_unit") != PAPER_LEDGER_PRICE_UNIT
    ):
        raise PortfolioValidationError(
            "Bản sao lưu (backup) thiếu siêu dữ liệu (metadata) đơn vị VND an toàn; "
            "không thể tự suy đoán giá cũ."
        )
    fills = decoded.get("fills", [])
    if not isinstance(fills, list) or len(fills) > PAPER_LEDGER_BACKUP_MAX_FILLS:
        raise PortfolioValidationError(
            "Danh sách giao dịch trong bản sao lưu (backup) không hợp lệ hoặc quá lớn."
        )
    # This UI is deliberately cash-backed and long-only.  JSON booleans must
    # not be accepted through Python's truthiness (for example "false" -> True).
    if decoded.get("allow_negative_cash") is not False:
        raise PortfolioValidationError(
            "Bản sao lưu (backup) phải dùng khóa kỹ thuật allow_negative_cash=false dưới dạng "
            "giá trị logic (boolean) trong JSON."
        )
    try:
        ledger = PortfolioLedger.from_session_state(decoded)
    except (KeyError, TypeError, ValueError, PortfolioValidationError) as exc:
        raise PortfolioValidationError(
            "Cấu trúc hoặc giao dịch trong bản sao lưu (backup) danh mục mô phỏng "
            "(paper portfolio) không hợp lệ."
        ) from exc
    if ledger.allow_negative_cash or ledger.cash < -1e-9:
        raise PortfolioValidationError(
            "Backup vi phạm giới hạn tiền mặt; không thể khôi phục an toàn."
        )
    return ledger


def _size_plan_in_vnd(
    plan: TradePlan,
    *,
    capital: float,
    risk_fraction: float,
    max_position_fraction: float,
):
    """Size a board-unit trade plan against VND-denominated capital."""

    return size_long_position_by_risk(
        capital=capital,
        risk_fraction=risk_fraction,
        entry_price=_board_price_to_vnd(plan.conservative_entry),
        stop_price=_board_price_to_vnd(plan.stop_price),
        lot_size=100,
        max_position_fraction=max_position_fraction,
        estimated_entry_cost_bps=15,
        estimated_exit_cost_bps=25,
    )


def _estimate_paper_trade_costs(
    *,
    side: Side | str,
    quantity: float,
    board_price: float,
    commission_bps: float = DEFAULT_PAPER_COMMISSION_BPS,
    sell_tax_bps: float = DEFAULT_PAPER_SELL_TAX_BPS,
) -> dict[str, float]:
    """Estimate VND paper-trading costs from a board-unit execution price.

    Commission applies to both sides.  Securities transaction tax applies to
    SELL fills only.  Modelled costs are rounded to the nearest whole VND
    before they enter the ledger.
    """

    try:
        normalized_side = side if isinstance(side, Side) else Side(str(side).upper())
    except ValueError as exc:
        raise PortfolioValidationError(
            "Loại giao dịch (side) phải là mua (BUY) hoặc bán (SELL)."
        ) from exc
    try:
        quantity_value = float(quantity)
        board_price_value = float(board_price)
        commission_rate = float(commission_bps)
        sell_tax_rate = float(sell_tax_bps)
    except (TypeError, ValueError) as exc:
        raise PortfolioValidationError(
            "quantity, board_price and cost rates must be numeric."
        ) from exc
    if not np.isfinite(quantity_value) or quantity_value <= 0:
        raise PortfolioValidationError("quantity must be finite and positive.")
    if not np.isfinite(board_price_value) or board_price_value <= 0:
        raise PortfolioValidationError("board_price must be finite and positive.")
    if (
        not np.isfinite(commission_rate)
        or commission_rate < 0
        or not np.isfinite(sell_tax_rate)
        or sell_tax_rate < 0
    ):
        raise PortfolioValidationError("Cost rates must be finite and non-negative.")

    notional = quantity_value * _board_price_to_vnd(board_price_value)
    commission = float(round(notional * commission_rate / 10_000.0))
    tax = (
        float(round(notional * sell_tax_rate / 10_000.0))
        if normalized_side is Side.SELL
        else 0.0
    )
    total_cost = commission + tax
    net_cash_flow = (
        -(notional + total_cost)
        if normalized_side is Side.BUY
        else notional - total_cost
    )
    return {
        "notional_vnd": float(notional),
        "commission_vnd": commission,
        "tax_vnd": tax,
        "total_cost_vnd": total_cost,
        "net_cash_flow_vnd": float(net_cash_flow),
    }


def _paper_fill_from_board_price(
    *,
    symbol: str,
    timestamp: datetime,
    side: Side | str,
    quantity: float,
    board_price: float,
    commission: float | None = None,
    tax: float | None = None,
    commission_bps: float = DEFAULT_PAPER_COMMISSION_BPS,
    sell_tax_bps: float = DEFAULT_PAPER_SELL_TAX_BPS,
    note: str = "",
) -> Fill:
    """Build a VND-denominated ledger fill from a board-unit UI price."""

    estimated = _estimate_paper_trade_costs(
        side=side,
        quantity=quantity,
        board_price=board_price,
        commission_bps=commission_bps,
        sell_tax_bps=sell_tax_bps,
    )
    return Fill(
        symbol=symbol,
        timestamp=timestamp,
        side=side,
        quantity=quantity,
        price=_board_price_to_vnd(board_price),
        commission=(
            estimated["commission_vnd"] if commission is None else commission
        ),
        tax=estimated["tax_vnd"] if tax is None else tax,
        note=note,
    )


def _pct(value) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "N/A"


def _latest_marks(
    prices: pd.DataFrame,
    symbols: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, float]:
    """Return latest marks in VND/share for use by ``PortfolioLedger``."""

    marks: dict[str, float] = {}
    if not isinstance(prices, pd.DataFrame):
        return marks
    allowed = None if symbols is None else {str(symbol).strip().upper() for symbol in symbols}
    for col in prices.columns:
        symbol = str(col).strip().upper()
        if allowed is not None and symbol not in allowed:
            continue
        series = pd.to_numeric(prices[col], errors="coerce").dropna()
        if len(series) and np.isfinite(series.iloc[-1]) and series.iloc[-1] > 0:
            marks[symbol] = _board_price_to_vnd(series.iloc[-1])
    return marks


def _eligible_paper_marks(
    prices: pd.DataFrame,
    valid_assets: list[str] | tuple[str, ...] | set[str] | None,
) -> dict[str, float]:
    """Return tradable VND marks only for equities validated by analysis."""

    if not valid_assets:
        return {}
    return _latest_marks(prices, symbols=valid_assets)


_POSITION_MONITOR_ACTIONS = {
    "NO_PLAN": (
        "Chưa có kế hoạch hợp lệ: không tăng vị thế; tạo và xác nhận kế hoạch trước "
        "quyết định tiếp theo. Không cam kết lợi nhuận; không tự đặt lệnh."
    ),
    "PLAN_EXPIRED": (
        "Kế hoạch đã hết hạn: dừng dùng các mức cũ và đánh giá lại trước khi giữ, mua "
        "hoặc bán. Không cam kết lợi nhuận; không tự đặt lệnh."
    ),
    "STOP_BREACHED": (
        "Giá đánh dấu (mark) đã chạm hoặc thấp hơn mức dừng lỗ (stop): kiểm tra khoảng "
        "trống giá (gap)/thanh khoản và thực hiện kỷ luật "
        "thoát theo kế hoạch. Không cam kết lợi nhuận; không tự đặt lệnh."
    ),
    "TARGET_1": (
        "Đã chạm mục tiêu giá (target) 1: cân nhắc chốt một phần hoặc nâng mức dừng lỗ "
        "(stop) theo kế hoạch đã xác "
        "nhận. Không cam kết lợi nhuận; không tự đặt lệnh."
    ),
    "FINAL_TARGET": (
        "Đã chạm mục tiêu cuối: rà soát chốt phần còn lại theo kế hoạch, không đuổi theo "
        "dự báo. Không cam kết lợi nhuận; không tự đặt lệnh."
    ),
    "MONITORING": (
        "Tiếp tục theo dõi; chỉ giữ nguyên khi luận điểm và mức dừng lỗ (stop) còn hiệu lực. Không cam "
        "kết lợi nhuận; không tự đặt lệnh."
    ),
}


def _monitor_open_positions(
    ledger: PortfolioLedger,
    marks_vnd: Mapping[str, float],
    trade_plans: Mapping[str, object] | None,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Build a fail-closed monitoring table for open long-only positions.

    Ledger prices and marks are VND/share.  Trade-plan levels and table price
    columns use the Vietnamese board convention (thousand VND/share).
    """

    current = now or datetime.now(VIETNAM_TZ)
    normalized_marks = {
        str(symbol).strip().upper(): value for symbol, value in marks_vnd.items()
    }
    plan_payloads = (
        {str(symbol).strip().upper(): value for symbol, value in trade_plans.items()}
        if isinstance(trade_plans, Mapping)
        else {}
    )
    rows: list[dict[str, object]] = []
    for symbol, position in sorted(ledger.positions().items()):
        try:
            mark_vnd = float(normalized_marks[symbol])
            valid_mark = np.isfinite(mark_vnd) and mark_vnd > 0
        except (KeyError, TypeError, ValueError):
            mark_vnd = np.nan
            valid_mark = False
        average_cost_board = _vnd_price_to_board(position.average_cost)
        mark_board = _vnd_price_to_board(mark_vnd) if valid_mark else np.nan
        pnl_pct = (
            mark_vnd / position.average_cost - 1.0
            if valid_mark and position.average_cost > 0
            else np.nan
        )

        plan = None
        payload = plan_payloads.get(symbol)
        try:
            if isinstance(payload, TradePlan):
                candidate = payload
            elif isinstance(payload, Mapping):
                candidate = TradePlan.from_dict(payload)
            else:
                candidate = None
            if (
                candidate is not None
                and candidate.symbol == symbol
                and candidate.direction.value == "LONG"
            ):
                plan = candidate
        except (AttributeError, KeyError, OverflowError, TypeError, ValueError, PortfolioValidationError):
            plan = None

        stop = np.nan
        target_1 = np.nan
        final_target = np.nan
        distance_to_stop = np.nan
        distance_to_next_target = np.nan
        status = "NO_PLAN"

        if plan is not None and valid_mark:
            stop = float(plan.stop_price)
            target_1 = float(plan.targets[0])
            final_target = float(plan.targets[-1])
            distance_to_stop = (mark_board - stop) / mark_board
            try:
                comparison_now = current
                if plan.expires_at.tzinfo is None and comparison_now.tzinfo is not None:
                    comparison_now = comparison_now.astimezone(VIETNAM_TZ).replace(tzinfo=None)
                elif plan.expires_at.tzinfo is not None and comparison_now.tzinfo is None:
                    comparison_now = comparison_now.replace(tzinfo=VIETNAM_TZ).astimezone(
                        plan.expires_at.tzinfo
                    )
                elif plan.expires_at.tzinfo is not None:
                    comparison_now = comparison_now.astimezone(plan.expires_at.tzinfo)
                expired = plan.is_expired(comparison_now)
            except (AttributeError, TypeError, ValueError, PortfolioValidationError):
                expired = True

            if expired:
                status = "PLAN_EXPIRED"
            elif mark_board <= stop:
                status = "STOP_BREACHED"
            elif mark_board >= final_target:
                status = "FINAL_TARGET"
            elif mark_board >= target_1:
                status = "TARGET_1"
            else:
                status = "MONITORING"

            if not expired:
                next_targets = [target for target in plan.targets if target > mark_board]
                if next_targets:
                    distance_to_next_target = (float(next_targets[0]) - mark_board) / mark_board

        rows.append(
            {
                "Mã": symbol,
                "Khối lượng (cp)": float(position.quantity),
                "Giá vốn (nghìn VND/cp)": average_cost_board,
                "Mark EOD/manual (nghìn VND/cp)": mark_board,
                "P&L (%)": float(pnl_pct),
                "Stop (nghìn VND/cp)": stop,
                "Mục tiêu 1 (nghìn VND/cp)": target_1,
                "Mục tiêu cuối (nghìn VND/cp)": final_target,
                "Khoảng cách tới stop (%)": float(distance_to_stop),
                "Khoảng cách tới mục tiêu kế tiếp (%)": float(distance_to_next_target),
                "Trạng thái": status,
                "Hành động có điều kiện": _POSITION_MONITOR_ACTIONS[status],
            }
        )
    return pd.DataFrame(rows)


def _screen_assets(prices: pd.DataFrame, assets: list[str], sim_rows: list[dict]) -> pd.DataFrame:
    betas = {str(row.get("Mã CP")): row.get("Beta (Độ nhạy)") for row in sim_rows}
    rows = []
    for asset in assets:
        series = pd.to_numeric(prices[asset], errors="coerce").dropna()
        returns = series.pct_change(fill_method=None).dropna()
        if len(series) < 60 or len(returns) < 20:
            continue
        current = float(series.iloc[-1])
        momentum_20 = current / float(series.iloc[-21]) - 1.0
        momentum_60 = current / float(series.iloc[-60]) - 1.0
        volatility = float(returns.tail(60).std(ddof=1) * np.sqrt(252))
        rolling_peak = series.tail(60).cummax()
        drawdown_60 = float((series.tail(60) / rolling_peak - 1.0).min())
        if momentum_20 > 0 and momentum_60 > 0:
            state = "Xu hướng dương"
        elif momentum_20 < 0 and momentum_60 < 0:
            state = "Xu hướng âm"
        else:
            state = "Chưa đồng thuận"
        rows.append(
            {
                "Mã": asset,
                "Giá EOD": current,
                "Động lượng 20 phiên": momentum_20,
                "Động lượng 60 phiên": momentum_60,
                "Biến động năm hóa": volatility,
                "Drawdown 60 phiên": drawdown_60,
                "Beta": betas.get(asset),
                "Trạng thái mẫu": state,
            }
        )
    return pd.DataFrame(rows)


def _scenario_from_prices(symbol: str, series: pd.Series) -> TradePlan:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    returns = clean.pct_change(fill_method=None).dropna()
    if len(clean) < 60 or len(returns) < 20:
        raise PortfolioValidationError("Cần ít nhất 60 phiên giá để tạo kịch bản.")
    current = float(clean.iloc[-1])
    daily_vol = float(returns.tail(20).std(ddof=1))
    if not np.isfinite(daily_vol) or daily_vol <= 0:
        raise PortfolioValidationError("Không ước lượng được biến động ngắn hạn.")

    entry_discount = float(np.clip(0.75 * daily_vol, 0.01, 0.05))
    stop_gap = float(np.clip(2.0 * daily_vol, 0.04, 0.15))
    entry_high = current
    entry_low = current * (1.0 - entry_discount)
    stop = entry_low * (1.0 - stop_gap)
    risk = entry_high - stop
    targets = (entry_high + 2.0 * risk, entry_high + 3.0 * risk)

    momentum_20 = current / float(clean.iloc[-21]) - 1.0
    momentum_60 = current / float(clean.iloc[-60]) - 1.0
    confidence = 0.40 + (0.12 if momentum_20 > 0 else -0.08) + (0.12 if momentum_60 > 0 else -0.08)
    confidence -= 0.08 if daily_vol > 0.03 else 0.0
    confidence = float(np.clip(confidence, 0.15, 0.75))
    now = datetime.now(VIETNAM_TZ)
    return TradePlan(
        plan_id=uuid4().hex,
        symbol=symbol,
        direction="LONG",
        created_at=now,
        expires_at=now + timedelta(days=10),
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        trigger="Chỉ dùng lệnh giới hạn (LO) khi giá nằm trong vùng vào và không có khoảng trống giá (gap) vượt vùng; xác nhận lại thanh khoản.",
        stop_price=stop,
        targets=targets,
        confidence=confidence,
        thesis="Kịch bản kỹ thuật từ động lượng 20/60 phiên và biến động 20 phiên; chưa dùng tin tức/cơ bản.",
        invalidation="Hủy kế hoạch khi hết hạn, dữ liệu đã cũ (stale) hoặc giá đóng cửa dưới điểm dừng.",
    )


def render_investment_desk(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    assets: list[str],
    market: str,
    sim_rows: list[dict],
) -> None:
    st.subheader("Bàn nghiên cứu đầu tư")
    st.caption("Sàng lọc và lập kịch bản có điều kiện. Không phải danh sách cổ phiếu chắc chắn sinh lời.")
    if prices.empty or not assets:
        st.caption("Chưa có dữ liệu — xem hướng dẫn bắt đầu ở đầu trang.")
        return

    screen = _screen_assets(prices, assets, sim_rows)
    if screen.empty:
        st.warning("Chưa đủ 60 phiên cho bảng sàng lọc.")
        return

    positive = int((screen["Trạng thái mẫu"] == "Xu hướng dương").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mã đạt dữ liệu", len(screen))
    c2.metric("Xu hướng dương", positive)
    c3.metric("Biến động thấp nhất", str(screen.loc[screen["Biến động năm hóa"].idxmin(), "Mã"]))
    c4.metric("Phiên dữ liệu", pd.Timestamp(prices.index.max()).strftime("%d/%m/%Y"))

    screen_display = screen.rename(
        columns={
            "Giá EOD": "Giá cuối ngày (EOD, nghìn VND/cp)",
            "Drawdown 60 phiên": "Mức sụt giảm (drawdown) 60 phiên",
            "Beta": "Beta (độ nhạy)",
        }
    )
    formatted = screen_display.style.format(
        {
            "Giá cuối ngày (EOD, nghìn VND/cp)": "{:,.2f}",
            "Động lượng 20 phiên": "{:.2%}",
            "Động lượng 60 phiên": "{:.2%}",
            "Biến động năm hóa": "{:.2%}",
            "Mức sụt giảm (drawdown) 60 phiên": "{:.2%}",
            "Beta (độ nhạy)": "{:.3f}",
        },
        na_rep="Không áp dụng (N/A)",
    )
    st.dataframe(formatted, width="stretch", hide_index=True)

    st.markdown("#### Kịch bản vào lệnh có điều kiện")
    symbol = st.selectbox("Mã nghiên cứu", screen["Mã"].tolist(), key="scenario_symbol")
    if st.button("Tạo kịch bản định lượng", width="stretch", key="create_trade_scenario"):
        try:
            plan = _scenario_from_prices(symbol, prices[symbol])
            st.session_state.setdefault("trade_plans", {})[symbol] = plan.to_dict()
        except PortfolioValidationError as exc:
            st.error(str(exc))

    plan_payload = st.session_state.get("trade_plans", {}).get(symbol)
    if plan_payload:
        plan = TradePlan.from_dict(plan_payload)
        plan_table = pd.DataFrame(
            [
                {
                    "Mã": plan.symbol,
                    "Vùng vào thấp (nghìn VND/cp)": plan.entry_zone_low,
                    "Vùng vào cao (nghìn VND/cp)": plan.entry_zone_high,
                    "Dừng lỗ (nghìn VND/cp)": plan.stop_price,
                    "Mục tiêu 1 (nghìn VND/cp)": plan.targets[0],
                    "Mục tiêu 2 (nghìn VND/cp)": plan.targets[1] if len(plan.targets) > 1 else np.nan,
                    "Lợi nhuận/rủi ro (R:R) mục tiêu 1": plan.risk_reward_ratios[0],
                    "Hết hiệu lực": plan.expires_at.strftime("%d/%m/%Y %H:%M"),
                    "Điểm tin cậy theo quy tắc kinh nghiệm (heuristic)": plan.confidence,
                }
            ]
        )
        st.dataframe(
            plan_table.style.format(
                {
                    "Vùng vào thấp (nghìn VND/cp)": "{:,.2f}",
                    "Vùng vào cao (nghìn VND/cp)": "{:,.2f}",
                    "Dừng lỗ (nghìn VND/cp)": "{:,.2f}",
                    "Mục tiêu 1 (nghìn VND/cp)": "{:,.2f}",
                    "Mục tiêu 2 (nghìn VND/cp)": "{:,.2f}",
                    "Lợi nhuận/rủi ro (R:R) mục tiêu 1": "{:.2f}",
                    "Điểm tin cậy theo quy tắc kinh nghiệm (heuristic)": "{:.0%}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.write(f"**Điều kiện:** {plan.trigger}")
        st.write(f"**Vô hiệu:** {plan.invalidation}")

        s1, s2, s3 = st.columns(3)
        capital = s1.number_input("Tổng vốn (VND)", min_value=1_000_000.0, value=500_000_000.0, step=10_000_000.0)
        risk_pct = s2.number_input("Rủi ro tối đa/kịch bản (%)", min_value=0.1, max_value=3.0, value=0.75, step=0.05)
        max_position_pct = s3.number_input("Tỷ trọng tối đa/mã (%)", min_value=5.0, max_value=40.0, value=20.0, step=1.0)
        sizing = _size_plan_in_vnd(
            plan,
            capital=capital,
            risk_fraction=risk_pct / 100.0,
            max_position_fraction=max_position_pct / 100.0,
        )
        z1, z2, z3 = st.columns(3)
        z1.metric("Khối lượng tối đa", f"{sizing.quantity:,} cp")
        z2.metric("Vốn dự kiến (VND)", f"{sizing.capital_required:,.0f}")
        z3.metric("Lỗ ước tính tại mức dừng lỗ (stop, VND)", f"{sizing.estimated_loss_at_stop:,.0f}")
        st.warning(sizing.warning)


def _restore_ledger() -> PortfolioLedger | None:
    payload = st.session_state.get("paper_ledger")
    if not payload:
        return None
    if (
        payload.get("money_unit") != PAPER_LEDGER_MONEY_UNIT
        or payload.get("price_unit") != PAPER_LEDGER_PRICE_UNIT
    ):
        st.session_state.paper_ledger = None
        st.warning(
            "Danh mục mô phỏng (paper portfolio) cũ không có siêu dữ liệu (metadata) đơn vị tiền và có thể sai 1.000 lần. "
            "Vui lòng khởi tạo lại để dùng chuẩn VND an toàn."
        )
        return None
    try:
        return PortfolioLedger.from_session_state(payload)
    except PortfolioValidationError:
        st.session_state.paper_ledger = None
        return None


def render_paper_portfolio(prices: pd.DataFrame) -> None:
    st.subheader("Danh mục mô phỏng (paper portfolio)")
    st.caption(
        "Giá cổ phiếu nhập theo nghìn VND/cp; vốn, phí, thuế và lãi/lỗ (P&L) dùng VND. "
        "Dữ liệu chỉ nằm trong phiên Streamlit; hãy tải bản sao lưu (backup) — tệp cấu trúc "
        "(JSON) — trước khi "
        "đóng hoặc triển khai lại (redeploy). "
        "Không gửi lệnh tới công ty chứng khoán."
    )
    ledger = _restore_ledger()
    if ledger is None:
        backup_file = st.file_uploader(
            "Khôi phục danh mục mô phỏng (paper portfolio) từ bản sao lưu (backup) — tệp cấu trúc (JSON)",
            type=["json"],
            key="paper_ledger_restore_file",
            help="Chỉ nhận bản sao lưu (backup) dạng tệp cấu trúc (JSON) do chính Quant App xuất, tối đa 1 MB.",
        )
        if backup_file is not None and st.button(
            "Khôi phục bản sao lưu (backup)", width="stretch", key="restore_paper_ledger"
        ):
            try:
                ledger = _ledger_from_backup_bytes(backup_file.getvalue())
                st.session_state.paper_ledger = _ledger_payload(ledger)
                st.success("Đã khôi phục danh mục mô phỏng (paper portfolio) và kiểm tra lại toàn bộ giao dịch.")
                st.rerun()
            except PortfolioValidationError as exc:
                st.error(str(exc))
        initial_cash = st.number_input(
            "Vốn mô phỏng ban đầu (VND)", min_value=1_000_000.0, value=500_000_000.0, step=10_000_000.0
        )
        if st.button("Khởi tạo danh mục mô phỏng (paper portfolio)", width="stretch", key="init_ledger"):
            ledger = PortfolioLedger(initial_cash)
            st.session_state.paper_ledger = _ledger_payload(ledger)
            st.rerun()
        return

    # ``prices`` also contains the market index.  Only validated equities have
    # a VND/share monetary meaning and are eligible for paper trading.
    equity_symbols = st.session_state.get("valid_assets", [])
    marks = _eligible_paper_marks(prices, equity_symbols)
    symbols = sorted(marks)
    if not symbols:
        st.warning(
            "Chưa có mã cổ phiếu với giá hợp lệ để ghi giao dịch. "
            "Hãy thêm mã ở thanh bên và chạy Phân tích lại."
        )
    else:
        st.markdown("#### Ghi nhận giao dịch mô phỏng")
        c1, c2, c3 = st.columns(3)
        symbol = c1.selectbox("Mã", symbols, key="paper_fill_symbol")
        side = c2.selectbox(
            "Giao dịch",
            [Side.BUY.value, Side.SELL.value],
            format_func=lambda value: "Mua (BUY)" if value == Side.BUY.value else "Bán (SELL)",
            key="paper_fill_side",
        )
        quantity = c3.number_input(
            "Khối lượng", min_value=100, value=100, step=100, key="paper_fill_quantity"
        )
        price = st.number_input(
            "Giá khớp (nghìn VND/cp)",
            min_value=0.01,
            value=_vnd_price_to_board(marks[symbol]),
            step=0.05,
            format="%.2f",
            key=f"paper_fill_price_{symbol}",
        )
        model_costs = _estimate_paper_trade_costs(
            side=side,
            quantity=quantity,
            board_price=price,
        )
        commission = model_costs["commission_vnd"]
        tax = model_costs["tax_vnd"]
        st.caption(
            f"Mặc định: phí {DEFAULT_PAPER_COMMISSION_BPS:g} điểm cơ bản (bps) cho mua/bán "
            f"(BUY/SELL); thuế bán {DEFAULT_PAPER_SELL_TAX_BPS:g} điểm cơ bản (bps) chỉ áp dụng bán (SELL)."
        )
        with st.expander("⚙️ Nâng cao (Advanced) — ghi đè chi phí mô hình"):
            manual_override = st.checkbox(
                "Nhập phí/thuế thực tế thay cho mức mặc định",
                key="paper_manual_cost_override",
            )
            if manual_override:
                commission = st.number_input(
                    "Phí thực tế (VND)",
                    min_value=0.0,
                    value=float(model_costs["commission_vnd"]),
                    step=100.0,
                    key=f"paper_manual_commission_{side}_{symbol}",
                )
                if side == Side.SELL.value:
                    tax = st.number_input(
                        "Thuế bán thực tế (VND)",
                        min_value=0.0,
                        value=float(model_costs["tax_vnd"]),
                        step=100.0,
                        key=f"paper_manual_sell_tax_{symbol}",
                    )
                else:
                    tax = 0.0
                    st.caption(
                        "Lệnh mua (BUY) không áp dụng thuế bán; giá trị thuế được khóa ở 0 VND."
                    )

        total_cost = float(commission + tax)
        notional = model_costs["notional_vnd"]
        net_cash_flow = (
            -(notional + total_cost)
            if side == Side.BUY.value
            else notional - total_cost
        )
        flow_label = "Tiền chi" if net_cash_flow < 0 else "Tiền thu ròng"
        cost_source = "ghi đè thủ công" if manual_override else "mô hình mặc định"
        st.info(
            f"Ước tính trước khi ghi sổ ({cost_source}): Giá trị lệnh {notional:,.0f} VND · "
            f"Phí {commission:,.0f} VND · Thuế {tax:,.0f} VND · "
            f"{flow_label} {abs(net_cash_flow):,.0f} VND."
        )
        note = st.text_input("Ghi chú", key="paper_fill_note")
        submitted = st.button(
            "Ghi nhận giao dịch", width="stretch", key="record_paper_fill"
        )
        if submitted:
            try:
                ledger.record_fill(
                    _paper_fill_from_board_price(
                        symbol=symbol,
                        timestamp=datetime.now(VIETNAM_TZ),
                        side=side,
                        quantity=quantity,
                        board_price=price,
                        commission=commission,
                        tax=tax,
                        note=note,
                    )
                )
                st.session_state.paper_ledger = _ledger_payload(ledger)
                st.rerun()
            except PortfolioValidationError as exc:
                st.error(str(exc))

    open_positions = ledger.positions()
    missing_marks = [symbol for symbol in open_positions if symbol not in marks]
    for symbol in missing_marks:
        position = open_positions[symbol]
        board_mark = st.number_input(
            f"Giá đánh dấu {symbol} (nghìn VND/cp)", min_value=0.01,
            value=max(_vnd_price_to_board(position.average_cost), 0.01),
            step=0.05, format="%.2f", key=f"mark_{symbol}"
        )
        marks[symbol] = _board_price_to_vnd(board_mark)
    try:
        snapshot = ledger.snapshot(marks)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tổng tài sản (VND)", f"{snapshot['equity']:,.0f}")
        m2.metric("Tiền mặt (VND)", f"{snapshot['cash']:,.0f}")
        m3.metric("Lãi/lỗ chưa chốt (P&L, VND)", f"{snapshot['unrealized_pnl']:,.0f}")
        m4.metric("Lãi/lỗ đã chốt (P&L, VND)", f"{snapshot['realized_pnl']:,.0f}")
        if snapshot["positions"]:
            positions = pd.DataFrame(snapshot["positions"])
            positions["average_cost"] /= BOARD_PRICE_TO_VND
            positions["mark_price"] /= BOARD_PRICE_TO_VND
            positions = positions.rename(
                columns={
                    "symbol": "Mã",
                    "quantity": "Khối lượng (cp)",
                    "average_cost": "Giá vốn (nghìn VND/cp)",
                    "mark_price": "Giá hiện tại (nghìn VND/cp)",
                    "market_value": "Giá trị thị trường (VND)",
                    "unrealized_pnl": "Lãi/lỗ chưa chốt (P&L, VND)",
                    "realized_pnl": "Lãi/lỗ đã chốt (P&L, VND)",
                }
            )
            st.dataframe(positions, width="stretch", hide_index=True)
            monitoring = _monitor_open_positions(
                ledger,
                marks,
                st.session_state.get("trade_plans", {}),
                now=datetime.now(VIETNAM_TZ),
            )
            if not monitoring.empty:
                st.markdown("#### Giám sát vị thế đang mở")
                st.caption(
                    "Giá đánh dấu (mark) lấy từ dữ liệu cuối ngày (EOD) hoặc giá bạn nhập thủ công "
                    "(manual), không phải thời gian thực (realtime). "
                    "Các hành động chỉ là kịch bản có điều kiện, không cam kết lợi nhuận và "
                    "Quant App không tự đặt lệnh."
                )
                monitoring_display = monitoring.rename(
                    columns={
                        "Mark EOD/manual (nghìn VND/cp)": "Giá đánh dấu cuối ngày/thủ công (mark EOD/manual, nghìn VND/cp)",
                        "P&L (%)": "Lãi/lỗ (P&L, %)",
                        "Stop (nghìn VND/cp)": "Dừng lỗ (stop, nghìn VND/cp)",
                        "Khoảng cách tới stop (%)": "Khoảng cách tới dừng lỗ (stop, %)",
                    }
                )
                monitoring_display["Trạng thái"] = monitoring_display["Trạng thái"].replace(
                    {
                        "NO_PLAN": "Chưa có kế hoạch (NO_PLAN)",
                        "PLAN_EXPIRED": "Kế hoạch hết hạn (PLAN_EXPIRED)",
                        "STOP_BREACHED": "Chạm dừng lỗ (STOP_BREACHED)",
                        "TARGET_1": "Chạm mục tiêu 1 (TARGET_1)",
                        "FINAL_TARGET": "Chạm mục tiêu cuối (FINAL_TARGET)",
                        "MONITORING": "Đang theo dõi (MONITORING)",
                    }
                )
                st.dataframe(
                    monitoring_display.style.format(
                        {
                            "Khối lượng (cp)": "{:,.0f}",
                            "Giá vốn (nghìn VND/cp)": "{:,.2f}",
                            "Giá đánh dấu cuối ngày/thủ công (mark EOD/manual, nghìn VND/cp)": "{:,.2f}",
                            "Lãi/lỗ (P&L, %)": "{:.2%}",
                            "Dừng lỗ (stop, nghìn VND/cp)": "{:,.2f}",
                            "Mục tiêu 1 (nghìn VND/cp)": "{:,.2f}",
                            "Mục tiêu cuối (nghìn VND/cp)": "{:,.2f}",
                            "Khoảng cách tới dừng lỗ (stop, %)": "{:.2%}",
                            "Khoảng cách tới mục tiêu kế tiếp (%)": "{:.2%}",
                        },
                        na_rep="—",
                    ),
                    width="stretch",
                    hide_index=True,
                )
    except PortfolioValidationError as exc:
        st.warning(str(exc))

    if ledger.fills:
        fills = pd.DataFrame([fill.to_dict() for fill in ledger.fills])
        fills["price"] /= BOARD_PRICE_TO_VND
        fills = fills.rename(
            columns={
                "symbol": "Mã",
                "timestamp": "Thời gian",
                "side": "Giao dịch",
                "quantity": "Khối lượng (cp)",
                "price": "Giá khớp (nghìn VND/cp)",
                "commission": "Phí (VND)",
                "tax": "Thuế (VND)",
                "note": "Ghi chú",
                "fill_id": "Mã giao dịch",
            }
        )
        fills["Giao dịch"] = fills["Giao dịch"].replace(
            {Side.BUY.value: "Mua (BUY)", Side.SELL.value: "Bán (SELL)"}
        )
        st.markdown("#### Nhật ký khớp lệnh")
        st.dataframe(fills, width="stretch", hide_index=True)
        st.download_button(
            "Tải nhật ký — tệp bảng (CSV)", fills.to_csv(index=False).encode("utf-8-sig"),
            file_name="paper_trades.csv", mime="text/csv", width="stretch",
        )

    st.download_button(
        "💾 Tải bản sao lưu (backup) danh mục mô phỏng (paper portfolio) — tệp cấu trúc (JSON)",
        data=_ledger_backup_bytes(ledger),
        file_name=(
            f"quant_app_paper_{datetime.now(VIETNAM_TZ).strftime('%Y%m%d_%H%M%S')}.json"
        ),
        mime="application/json",
        width="stretch",
        help="Bản sao lưu (backup) gồm vốn ban đầu, siêu dữ liệu (metadata) đơn vị và toàn bộ giao dịch để có thể khôi phục sau khi triển khai lại (redeploy).",
    )

    confirm_reset = st.checkbox("Tôi xác nhận xóa danh mục mô phỏng (paper portfolio) hiện tại", key="confirm_reset_ledger")
    if st.button("Xóa danh mục mô phỏng (paper portfolio)", disabled=not confirm_reset, key="reset_ledger"):
        st.session_state.paper_ledger = None
        st.rerun()


def _cap_long_weights(raw: pd.Series, cap: float) -> pd.Series:
    weights = pd.to_numeric(raw, errors="coerce").fillna(0.0).clip(lower=0.0)
    if float(weights.sum()) <= 0:
        return weights * 0.0
    weights /= float(weights.sum())
    target = min(1.0, cap * len(weights))
    result = pd.Series(0.0, index=weights.index)
    active = list(weights.index)
    remaining = target
    while active and remaining > 1e-12:
        base = weights.loc[active]
        allocation = base / float(base.sum()) * remaining if float(base.sum()) > 0 else remaining / len(active)
        hit = [asset for asset in active if allocation.loc[asset] > cap]
        if not hit:
            result.loc[active] = allocation
            break
        for asset in hit:
            result.loc[asset] = cap
            remaining -= cap
            active.remove(asset)
    return result


def _backtest_research_gate(
    metrics: dict,
    comparison: dict,
) -> tuple[bool, pd.DataFrame]:
    """Return a transparent preliminary gate for promotion to paper trading."""

    def finite_value(mapping: dict, key: str, default: float) -> float:
        try:
            value = float(mapping.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if np.isfinite(value) else default

    observations = max(0, int(finite_value(metrics, "observations", 0.0)))
    rebalances = max(0, int(finite_value(metrics, "rebalance_count", 0.0)))
    excess_return = finite_value(comparison, "total_return_excess", -np.inf)
    sharpe = finite_value(metrics, "sharpe", -np.inf)
    max_drawdown = finite_value(metrics, "max_drawdown", -np.inf)
    checks = [
        (
            "Lợi suất vượt danh mục tham chiếu (benchmark) sau chi phí",
            excess_return > 0,
            "> 0%",
        ),
        (
            "Chỉ số Sharpe ngoài mẫu (OOS)",
            sharpe >= 0.50,
            ">= 0,50",
        ),
        (
            "Mức sụt giảm cực đại (max drawdown)",
            -0.25 < max_drawdown <= 0.0,
            "> -25%",
        ),
        ("Độ dài ngoài mẫu (OOS)", observations >= 126, ">= 126 phiên"),
        ("Số lần tái cân bằng", rebalances >= 6, ">= 6 lần"),
    ]
    table = pd.DataFrame(
        {
            "Kiểm định": [name for name, _, _ in checks],
            "Ngưỡng": [threshold for _, _, threshold in checks],
            "Trạng thái": ["ĐẠT" if passed else "CHƯA ĐẠT" for _, passed, _ in checks],
        }
    )
    return all(passed for _, passed, _ in checks), table


def render_backtest(prices: pd.DataFrame, assets: list[str], market: str) -> None:
    st.subheader("Kiểm thử cuốn chiếu (walk-forward backtest)")
    st.caption(
        "Mỗi quyết định chỉ nhìn dữ liệu đã có tại giá đóng cửa. Mặc định: quyết định "
        "ở T → thực thi ở T+1 → lợi suất đầu tiên kết thúc ở T+2. Kết quả đã trừ chi phí."
    )
    if prices.empty or not assets or market not in prices.columns:
        st.caption("Chưa có dữ liệu — xem hướng dẫn bắt đầu ở đầu trang.")
        return

    with st.form("backtest_form"):
        strategy_name = st.selectbox(
            "Chiến lược",
            [
                "Markowitz — chỉ số Sharpe tối đa ngoài mẫu (Max Sharpe OOS)",
                "Trọng số đều ngoài mẫu (OOS)",
            ],
        )
        c1, c2, c3 = st.columns(3)
        train_window = c1.number_input("Cửa sổ huấn luyện", min_value=80, max_value=756, value=126, step=21)
        rebalance = c2.number_input("Tái cân bằng mỗi phiên", min_value=5, max_value=126, value=21, step=1)
        max_weight = c3.number_input("Tỷ trọng tối đa/mã (%)", min_value=10.0, max_value=100.0, value=35.0, step=5.0)
        c4, c5, c6, c7 = st.columns(4)
        fee_bps = c4.number_input("Phí mỗi chiều — điểm cơ bản (bps)", min_value=0.0, value=15.0, step=1.0)
        slippage_bps = c5.number_input("Trượt giá (slippage) — điểm cơ bản (bps)", min_value=0.0, value=10.0, step=1.0)
        tax_bps = c6.number_input("Thuế chiều bán — điểm cơ bản (bps)", min_value=0.0, value=10.0, step=1.0)
        rf_pct = c7.number_input("Lãi suất phi rủi ro (%)", min_value=0.0, value=4.0, step=0.25)
        with st.expander("Giả định thực thi"):
            execution_lag = st.number_input(
                "Độ trễ từ quyết định đến khớp (phiên)",
                min_value=1,
                max_value=5,
                value=1,
                step=1,
                help=(
                    "Tối thiểu 1 phiên để không giả định có thể tính tín hiệu từ giá đóng cửa "
                    "và đồng thời khớp ngay chính mức giá đó."
                ),
            )
        run_test = st.form_submit_button("Chạy kiểm định ngoài mẫu", width="stretch")

    if run_test:
        cap = max_weight / 100.0

        def strategy(training_returns, context):
            del context
            if strategy_name.startswith("Trọng số"):
                raw = pd.Series(1.0, index=training_returns.columns)
            else:
                optimized = markowitz_optimization(
                    training_returns,
                    risk_free_rate=rf_pct / 100.0,
                    min_observations=int(train_window),
                    num_portfolios=200,
                )
                raw = pd.Series(optimized["max_sharpe_weights"], index=training_returns.columns)
            return _cap_long_weights(raw, cap)

        try:
            aligned = prices[assets + [market]].dropna()
            cfg = BacktestConfig(
                min_train_size=int(train_window), min_test_size=20, train_window=int(train_window),
                rebalance_every=int(rebalance), risk_free_rate_annual=rf_pct / 100.0,
                fee_bps=fee_bps, slippage_bps=slippage_bps, sell_tax_bps=tax_bps,
                max_weight=cap, max_gross_leverage=1.0, allow_short=False,
                execution_lag_periods=int(execution_lag),
            )
            st.session_state.backtest_result = run_walk_forward(
                aligned[assets], aligned[market], strategy, cfg
            )
        except (BacktestValidationError, ValueError) as exc:
            st.session_state.backtest_result = None
            st.error(str(exc))

    result = st.session_state.get("backtest_result")
    if result is None:
        return
    metrics = result.metrics
    benchmark = result.benchmark_metrics
    comparison = result.comparison
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tăng trưởng kép năm ngoài mẫu (CAGR OOS)", _pct(metrics.get("cagr")), _pct(comparison.get("cagr_excess")))
    k2.metric("Chỉ số Sharpe ngoài mẫu (OOS)", f"{metrics.get('sharpe', np.nan):.2f}")
    k3.metric("Mức sụt giảm cực đại (max drawdown)", _pct(metrics.get("max_drawdown")))
    k4.metric("Chi phí mô phỏng (VND)", f"{metrics.get('total_transaction_cost', 0):,.0f}")

    chart = result.equity_curve.rename(
        columns={"portfolio": "Chiến lược", "benchmark": "Danh mục tham chiếu (benchmark)"}
    )
    fig = px.line(chart, x=chart.index, y=chart.columns, labels={"value": "Giá trị", "index": "Ngày"})
    st.plotly_chart(fig, width="stretch")
    comparison_table = pd.DataFrame(
        {
            "Chỉ số": [
                "Tổng lợi suất",
                "Tăng trưởng kép năm (CAGR)",
                "Biến động (volatility)",
                "Chỉ số Sharpe",
                "Chỉ số Sortino",
                "Mức sụt giảm cực đại (max drawdown)",
                "Tỷ lệ phiên có lãi (hit rate)",
            ],
            "Chiến lược": [metrics.get(k) for k in ("total_return", "cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "hit_rate")],
            "Danh mục tham chiếu (benchmark)": [benchmark.get(k) for k in ("total_return", "cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "hit_rate")],
        }
    )
    st.dataframe(comparison_table, width="stretch", hide_index=True)

    research_pass, gate_table = _backtest_research_gate(metrics, comparison)
    st.markdown("#### Cổng tiêu chí (gate) chuyển sang giao dịch mô phỏng (paper trading)")
    st.dataframe(gate_table, width="stretch", hide_index=True)
    if research_pass:
        st.success(
            "Đạt cổng tiêu chí (gate) nghiên cứu ban đầu: có thể chuyển sang giao dịch mô phỏng "
            "(paper trading); chưa đạt cổng tiêu chí dùng vốn thật."
        )
    else:
        st.warning("Chưa đạt cổng tiêu chí (gate) nghiên cứu: không dùng chiến lược này cho vốn thật.")
    st.caption(
        "Cổng tiêu chí (gate) này chưa loại bỏ thiên lệch do thử nhiều chiến lược, thay đổi tham số sau khi xem "
        "kết quả, thanh khoản thực tế hoặc thay đổi chế độ thị trường."
    )
    with st.expander("Nhật ký tái cân bằng và trọng số ngoài mẫu (OOS)"):
        rebalance_display = result.rebalances.rename(
            columns={
                "rebalance_number": "Lần tái cân bằng (rebalance)",
                "decision_time": "Thời điểm quyết định (decision time)",
                "execution_time": "Thời điểm thực thi (execution time)",
                "first_return_time": "Thời điểm lợi suất đầu tiên (first return time)",
                "execution_lag_periods": "Độ trễ thực thi (execution lag, phiên)",
                "train_start": "Bắt đầu tập huấn luyện (train start)",
                "train_end": "Kết thúc tập huấn luyện (train end)",
                "training_observations": "Số quan sát huấn luyện (training observations)",
                "buy_turnover": "Vòng quay mua (buy turnover)",
                "sell_turnover": "Vòng quay bán (sell turnover)",
                "turnover": "Tổng vòng quay (turnover)",
                "cost_rate": "Tỷ lệ chi phí (cost rate)",
                "cost_amount": "Giá trị chi phí (cost amount)",
                **{
                    column: f"Tỷ trọng {column.removeprefix('weight_')} (weight)"
                    for column in result.rebalances.columns
                    if str(column).startswith("weight_")
                },
            }
        )
        st.dataframe(rebalance_display, width="stretch", hide_index=True)
        st.caption("Bảng dưới: mỗi cột mã cổ phiếu là tỷ trọng (weight) của mã đó.")
        st.dataframe(result.weights.tail(100), width="stretch")
