"""Streamlit renderers for research, walk-forward tests, and paper trading."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

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


def _pct(value) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "N/A"


def _latest_marks(prices: pd.DataFrame) -> dict[str, float]:
    marks: dict[str, float] = {}
    if not isinstance(prices, pd.DataFrame):
        return marks
    for col in prices.columns:
        series = pd.to_numeric(prices[col], errors="coerce").dropna()
        if len(series) and np.isfinite(series.iloc[-1]) and series.iloc[-1] > 0:
            marks[str(col).upper()] = float(series.iloc[-1])
    return marks


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
    now = datetime.now()
    return TradePlan(
        plan_id=uuid4().hex,
        symbol=symbol,
        direction="LONG",
        created_at=now,
        expires_at=now + timedelta(days=10),
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        trigger="Chỉ dùng lệnh LO khi giá nằm trong vùng vào và không gap vượt vùng; xác nhận lại thanh khoản.",
        stop_price=stop,
        targets=targets,
        confidence=confidence,
        thesis="Kịch bản kỹ thuật từ động lượng 20/60 phiên và biến động 20 phiên; chưa dùng tin tức/cơ bản.",
        invalidation="Hủy kế hoạch khi hết hạn, dữ liệu stale hoặc giá đóng cửa dưới điểm dừng.",
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
        st.info("Chạy Phân tích ở thanh bên để nạp dữ liệu trước.")
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

    formatted = screen.style.format(
        {
            "Giá EOD": "{:,.2f}",
            "Động lượng 20 phiên": "{:.2%}",
            "Động lượng 60 phiên": "{:.2%}",
            "Biến động năm hóa": "{:.2%}",
            "Drawdown 60 phiên": "{:.2%}",
            "Beta": "{:.3f}",
        },
        na_rep="N/A",
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
                    "Vùng vào thấp": plan.entry_zone_low,
                    "Vùng vào cao": plan.entry_zone_high,
                    "Dừng lỗ": plan.stop_price,
                    "Mục tiêu 1": plan.targets[0],
                    "Mục tiêu 2": plan.targets[1] if len(plan.targets) > 1 else np.nan,
                    "R:R mục tiêu 1": plan.risk_reward_ratios[0],
                    "Hết hiệu lực": plan.expires_at.strftime("%d/%m/%Y %H:%M"),
                    "Điểm tin cậy heuristic": plan.confidence,
                }
            ]
        )
        st.dataframe(
            plan_table.style.format(
                {
                    "Vùng vào thấp": "{:,.2f}", "Vùng vào cao": "{:,.2f}",
                    "Dừng lỗ": "{:,.2f}", "Mục tiêu 1": "{:,.2f}",
                    "Mục tiêu 2": "{:,.2f}", "R:R mục tiêu 1": "{:.2f}",
                    "Điểm tin cậy heuristic": "{:.0%}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.write(f"**Điều kiện:** {plan.trigger}")
        st.write(f"**Vô hiệu:** {plan.invalidation}")

        s1, s2, s3 = st.columns(3)
        capital = s1.number_input("Tổng vốn", min_value=1_000_000.0, value=500_000_000.0, step=10_000_000.0)
        risk_pct = s2.number_input("Rủi ro tối đa/kịch bản (%)", min_value=0.1, max_value=3.0, value=0.75, step=0.05)
        max_position_pct = s3.number_input("Tỷ trọng tối đa/mã (%)", min_value=5.0, max_value=40.0, value=20.0, step=1.0)
        sizing = size_long_position_by_risk(
            capital=capital,
            risk_fraction=risk_pct / 100.0,
            entry_price=plan.conservative_entry,
            stop_price=plan.stop_price,
            lot_size=100,
            max_position_fraction=max_position_pct / 100.0,
            estimated_entry_cost_bps=15,
            estimated_exit_cost_bps=25,
        )
        z1, z2, z3 = st.columns(3)
        z1.metric("Khối lượng tối đa", f"{sizing.quantity:,} cp")
        z2.metric("Vốn dự kiến", f"{sizing.capital_required:,.0f}")
        z3.metric("Lỗ ước tính tại stop", f"{sizing.estimated_loss_at_stop:,.0f}")
        st.warning(sizing.warning)


def _restore_ledger() -> PortfolioLedger | None:
    payload = st.session_state.get("paper_ledger")
    if not payload:
        return None
    try:
        return PortfolioLedger.from_session_state(payload)
    except PortfolioValidationError:
        st.session_state.paper_ledger = None
        return None


def render_paper_portfolio(prices: pd.DataFrame) -> None:
    st.subheader("Paper portfolio")
    st.caption("Ghi đúng giá đã khớp, phí và thuế. Không gửi lệnh tới công ty chứng khoán.")
    ledger = _restore_ledger()
    if ledger is None:
        initial_cash = st.number_input(
            "Vốn mô phỏng ban đầu", min_value=1_000_000.0, value=500_000_000.0, step=10_000_000.0
        )
        if st.button("Khởi tạo paper portfolio", width="stretch", key="init_ledger"):
            ledger = PortfolioLedger(initial_cash)
            st.session_state.paper_ledger = ledger.to_session_state()
            st.rerun()
        return

    marks = _latest_marks(prices)
    symbols = sorted(set(marks) | set(ledger.positions(include_closed=True)))
    with st.form("paper_fill_form"):
        c1, c2, c3 = st.columns(3)
        symbol = c1.selectbox("Mã", symbols or ["FPT"])
        side = c2.selectbox("Giao dịch", [Side.BUY.value, Side.SELL.value])
        quantity = c3.number_input("Khối lượng", min_value=100, value=100, step=100)
        d1, d2, d3 = st.columns(3)
        default_price = float(marks.get(symbol, 1.0))
        price = d1.number_input("Giá khớp", min_value=0.01, value=default_price, step=100.0)
        commission = d2.number_input("Phí", min_value=0.0, value=0.0, step=1_000.0)
        tax = d3.number_input("Thuế", min_value=0.0, value=0.0, step=1_000.0)
        note = st.text_input("Ghi chú")
        submitted = st.form_submit_button("Ghi nhận giao dịch", width="stretch")
    if submitted:
        try:
            ledger.record_fill(
                Fill(
                    symbol=symbol, timestamp=datetime.now(), side=side,
                    quantity=quantity, price=price, commission=commission, tax=tax, note=note,
                )
            )
            st.session_state.paper_ledger = ledger.to_session_state()
            st.rerun()
        except PortfolioValidationError as exc:
            st.error(str(exc))

    open_positions = ledger.positions()
    missing_marks = [symbol for symbol in open_positions if symbol not in marks]
    for symbol in missing_marks:
        position = open_positions[symbol]
        marks[symbol] = st.number_input(
            f"Giá đánh dấu {symbol}", min_value=0.01, value=max(position.average_cost, 0.01), key=f"mark_{symbol}"
        )
    try:
        snapshot = ledger.snapshot(marks)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tổng tài sản", f"{snapshot['equity']:,.0f}")
        m2.metric("Tiền mặt", f"{snapshot['cash']:,.0f}")
        m3.metric("P&L chưa chốt", f"{snapshot['unrealized_pnl']:,.0f}")
        m4.metric("P&L đã chốt", f"{snapshot['realized_pnl']:,.0f}")
        if snapshot["positions"]:
            st.dataframe(pd.DataFrame(snapshot["positions"]), width="stretch", hide_index=True)
    except PortfolioValidationError as exc:
        st.warning(str(exc))

    if ledger.fills:
        fills = pd.DataFrame([fill.to_dict() for fill in ledger.fills])
        st.markdown("#### Nhật ký khớp lệnh")
        st.dataframe(fills, width="stretch", hide_index=True)
        st.download_button(
            "Tải nhật ký CSV", fills.to_csv(index=False).encode("utf-8-sig"),
            file_name="paper_trades.csv", mime="text/csv", width="stretch",
        )

    confirm_reset = st.checkbox("Tôi xác nhận xóa paper portfolio hiện tại", key="confirm_reset_ledger")
    if st.button("Xóa paper portfolio", disabled=not confirm_reset, key="reset_ledger"):
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


def render_backtest(prices: pd.DataFrame, assets: list[str], market: str) -> None:
    st.subheader("Walk-forward backtest")
    st.caption("Mỗi quyết định chỉ nhìn dữ liệu trước ngày thực thi. Kết quả đã trừ chi phí do bạn cấu hình.")
    if prices.empty or not assets or market not in prices.columns:
        st.info("Chạy Phân tích trước để có dữ liệu backtest.")
        return

    with st.form("backtest_form"):
        strategy_name = st.selectbox("Chiến lược", ["Markowitz Max Sharpe OOS", "Trọng số đều OOS"])
        c1, c2, c3 = st.columns(3)
        train_window = c1.number_input("Cửa sổ huấn luyện", min_value=80, max_value=756, value=126, step=21)
        rebalance = c2.number_input("Tái cân bằng mỗi phiên", min_value=5, max_value=126, value=21, step=1)
        max_weight = c3.number_input("Tỷ trọng tối đa/mã (%)", min_value=10.0, max_value=100.0, value=35.0, step=5.0)
        c4, c5, c6, c7 = st.columns(4)
        fee_bps = c4.number_input("Phí mỗi chiều (bps)", min_value=0.0, value=15.0, step=1.0)
        slippage_bps = c5.number_input("Slippage (bps)", min_value=0.0, value=10.0, step=1.0)
        tax_bps = c6.number_input("Thuế chiều bán (bps)", min_value=0.0, value=10.0, step=1.0)
        rf_pct = c7.number_input("Lãi suất phi rủi ro (%)", min_value=0.0, value=4.0, step=0.25)
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
    k1.metric("CAGR OOS", _pct(metrics.get("cagr")), _pct(comparison.get("cagr_excess")))
    k2.metric("Sharpe OOS", f"{metrics.get('sharpe', np.nan):.2f}")
    k3.metric("Max drawdown", _pct(metrics.get("max_drawdown")))
    k4.metric("Chi phí", f"{metrics.get('total_transaction_cost', 0):,.0f}")

    chart = result.equity_curve.rename(columns={"portfolio": "Chiến lược", "benchmark": "Benchmark"})
    fig = px.line(chart, x=chart.index, y=chart.columns, labels={"value": "Giá trị", "index": "Ngày"})
    st.plotly_chart(fig, width="stretch")
    comparison_table = pd.DataFrame(
        {
            "Chỉ số": ["Tổng lợi suất", "CAGR", "Volatility", "Sharpe", "Sortino", "Max drawdown", "Hit rate"],
            "Chiến lược": [metrics.get(k) for k in ("total_return", "cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "hit_rate")],
            "Benchmark": [benchmark.get(k) for k in ("total_return", "cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "hit_rate")],
        }
    )
    st.dataframe(comparison_table, width="stretch", hide_index=True)

    research_pass = (
        float(comparison.get("total_return_excess", -np.inf)) > 0
        and float(metrics.get("sharpe", -np.inf)) > 0
        and float(metrics.get("max_drawdown", -1.0)) > -0.25
        and int(metrics.get("observations", 0)) >= 60
    )
    if research_pass:
        st.success("Đạt gate nghiên cứu ban đầu: có thể chuyển sang paper trading; chưa đạt gate vốn thật.")
    else:
        st.warning("Không đạt gate nghiên cứu: không dùng chiến lược này cho vốn thật.")
    with st.expander("Nhật ký tái cân bằng và trọng số OOS"):
        st.dataframe(result.rebalances, width="stretch", hide_index=True)
        st.dataframe(result.weights.tail(100), width="stretch")
