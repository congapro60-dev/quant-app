"""Bias-aware walk-forward backtesting utilities.

The engine deliberately accepts only price data with a clean, shared calendar.
At every rebalance, a strategy receives returns ending before execution.  By
default, one complete close-to-close period separates the signal close from
the execution close, and performance starts with the following period.  This
conservative convention prevents a close-derived signal from earning an
overnight or one-bar move that occurred before it could be executed.

The module is independent from Streamlit.  ``BacktestResult`` contains pandas
objects and plain dictionaries, so it can be stored directly in
``st.session_state`` or rendered by another UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Protocol

import numpy as np
import pandas as pd


__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BacktestValidationError",
    "StrategyContext",
    "WalkForwardStrategy",
    "equal_weight_strategy",
    "fixed_weight_strategy",
    "performance_metrics",
    "run_walk_forward",
]


class BacktestValidationError(ValueError):
    """Raised when data or strategy output is unsafe for a backtest."""


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for a daily walk-forward backtest.

    Costs are expressed in basis points of risky-asset notional.  Fees and
    slippage apply to buys and sells; ``sell_tax_bps`` applies only to sells.
    Unallocated capital earns ``risk_free_rate_annual``.

    ``execution_lag_periods`` is the number of complete return periods between
    the signal/decision close and the execution close.  The safe default is
    one: a signal calculated at close T executes at close T+1 and first earns
    the return ending at T+2.  Set it to zero only to reproduce the optimistic
    convention that execution occurs at the same close used by the signal.
    """

    min_train_size: int = 126
    min_test_size: int = 20
    train_window: int | None = 252
    rebalance_every: int = 21
    annualization: int = 252
    risk_free_rate_annual: float = 0.0
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    sell_tax_bps: float = 0.0
    initial_capital: float = 1_000_000_000.0
    max_weight: float = 1.0
    max_gross_leverage: float = 1.0
    allow_short: bool = False
    max_abs_period_return: float | None = 1.0
    # Appended to preserve positional compatibility with earlier configs.
    execution_lag_periods: int = 1

    def __post_init__(self) -> None:
        if self.min_train_size < 2:
            raise BacktestValidationError(
                "Cỡ mẫu huấn luyện tối thiểu (min_train_size) phải từ 2 trở lên."
            )
        if self.min_test_size < 1:
            raise BacktestValidationError(
                "Cỡ mẫu kiểm định tối thiểu (min_test_size) phải lớn hơn 0."
            )
        if self.train_window is not None and self.train_window < self.min_train_size:
            raise BacktestValidationError(
                "Cửa sổ huấn luyện (train_window) không được nhỏ hơn cỡ mẫu "
                "huấn luyện tối thiểu (min_train_size)."
            )
        if self.rebalance_every < 1 or self.annualization < 1:
            raise BacktestValidationError(
                "Chu kỳ tái cân bằng (rebalance_every) và hệ số năm hóa "
                "(annualization) phải lớn hơn 0."
            )
        if (
            isinstance(self.execution_lag_periods, bool)
            or not isinstance(self.execution_lag_periods, (int, np.integer))
            or self.execution_lag_periods < 0
        ):
            raise BacktestValidationError(
                "Độ trễ thực thi theo kỳ (execution_lag_periods) phải là số nguyên không âm."
            )
        if self.risk_free_rate_annual <= -1:
            raise BacktestValidationError(
                "Lãi suất phi rủi ro hằng năm (risk_free_rate_annual) phải lớn hơn -1."
            )
        for name in ("fee_bps", "slippage_bps", "sell_tax_bps"):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise BacktestValidationError(
                    f"Tham số {name} phải là số hữu hạn và không âm."
                )
        if not np.isfinite(self.initial_capital) or self.initial_capital <= 0:
            raise BacktestValidationError(
                "Vốn ban đầu (initial_capital) phải là số hữu hạn và lớn hơn 0."
            )
        if not 0 < self.max_weight <= self.max_gross_leverage:
            raise BacktestValidationError(
                "Tỷ trọng tối đa (max_weight) phải lớn hơn 0 và không vượt đòn bẩy "
                "gộp tối đa (max_gross_leverage)."
            )
        if self.max_gross_leverage <= 0:
            raise BacktestValidationError(
                "Đòn bẩy gộp tối đa (max_gross_leverage) phải lớn hơn 0."
            )
        if self.max_abs_period_return is not None:
            if not np.isfinite(self.max_abs_period_return) or self.max_abs_period_return <= 0:
                raise BacktestValidationError(
                    "Mức lợi suất tuyệt đối tối đa theo kỳ (max_abs_period_return) "
                    "phải lớn hơn 0 hoặc để trống (None)."
                )


@dataclass(frozen=True)
class StrategyContext:
    """Information available to a strategy at a rebalance.

    ``decision_time`` is the final timestamp in ``training_returns``.
    ``execution_time`` is the close at which the target weights are assumed
    acquired, while ``first_return_time`` is the end of the first return period
    those weights may earn.  With the default lag, the timestamps are strictly
    ordered ``decision_time < execution_time < first_return_time``.
    ``previous_weights`` is the portfolio snapshot at ``decision_time`` and
    deliberately excludes drift during the execution lag.  Turnover and costs
    are instead calculated from the actual drifted weights at
    ``execution_time``.
    """

    rebalance_number: int
    decision_time: pd.Timestamp
    execution_time: pd.Timestamp
    previous_weights: pd.Series
    first_return_time: pd.Timestamp | None = None
    execution_lag_periods: int = 1


class WalkForwardStrategy(Protocol):
    def __call__(
        self, training_returns: pd.DataFrame, context: StrategyContext
    ) -> Mapping[str, float] | pd.Series:
        """Return target risky-asset weights; omitted weight remains cash."""


@dataclass
class BacktestResult:
    """Complete result and audit trail from ``run_walk_forward``."""

    equity_curve: pd.DataFrame
    returns: pd.DataFrame
    weights: pd.DataFrame
    rebalances: pd.DataFrame
    metrics: dict[str, float | int]
    benchmark_metrics: dict[str, float | int]
    comparison: dict[str, float]
    config: BacktestConfig

    def to_session_state(self) -> dict[str, object]:
        """Return a shallow-copy payload suitable for ``st.session_state``."""

        return {
            "equity_curve": self.equity_curve.copy(),
            "returns": self.returns.copy(),
            "weights": self.weights.copy(),
            "rebalances": self.rebalances.copy(),
            "metrics": dict(self.metrics),
            "benchmark_metrics": dict(self.benchmark_metrics),
            "comparison": dict(self.comparison),
            "config": asdict(self.config),
        }


Strategy = Callable[
    [pd.DataFrame, StrategyContext], Mapping[str, float] | pd.Series
]


def equal_weight_strategy(
    training_returns: pd.DataFrame, context: StrategyContext
) -> pd.Series:
    """A deterministic, fully-invested equal-weight baseline strategy."""

    del context
    if training_returns.shape[1] == 0:
        raise BacktestValidationError("Chiến lược (strategy) không nhận được tài sản nào.")
    return pd.Series(
        1.0 / training_returns.shape[1], index=training_returns.columns, dtype=float
    )


def fixed_weight_strategy(weights: Mapping[str, float]) -> Strategy:
    """Create a strategy returning the same explicit weights at each rebalance."""

    frozen = dict(weights)

    def strategy(
        training_returns: pd.DataFrame, context: StrategyContext
    ) -> Mapping[str, float]:
        del training_returns, context
        return dict(frozen)

    return strategy


def _validated_datetime_index(index: pd.Index, label: str) -> pd.DatetimeIndex:
    try:
        result = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    except Exception as exc:  # pragma: no cover - pandas error wording varies
        raise BacktestValidationError(
            f"Chỉ mục của {label} phải có dạng ngày giờ (datetime)."
        ) from exc
    if result.has_duplicates:
        raise BacktestValidationError(
            f"Chỉ mục của {label} chứa thời điểm (timestamp) bị trùng."
        )
    if not result.is_monotonic_increasing:
        raise BacktestValidationError(
            f"Chỉ mục của {label} phải được sắp xếp từ cũ đến mới."
        )
    return result


def _validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise BacktestValidationError(
            "Bảng giá (prices) phải là bảng dữ liệu pandas (DataFrame) không rỗng."
        )
    if prices.shape[1] == 0 or prices.columns.has_duplicates:
        raise BacktestValidationError(
            "Bảng giá (prices) phải có các cột tài sản không trùng nhau."
        )
    clean = prices.copy()
    clean.index = _validated_datetime_index(clean.index, "prices")
    try:
        clean = clean.apply(pd.to_numeric, errors="raise").astype(float)
    except Exception as exc:
        raise BacktestValidationError(
            "Bảng giá (prices) chỉ được chứa giá trị số."
        ) from exc
    values = clean.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise BacktestValidationError(
            "Bảng giá (prices) có giá trị thiếu hoặc không hữu hạn; hãy căn chỉnh hoặc "
            "sửa dữ liệu một cách tường minh."
        )
    if (values <= 0).any():
        raise BacktestValidationError("Mọi giá trong bảng giá (prices) phải lớn hơn 0.")
    return clean


def _validate_benchmark(
    benchmark_prices: pd.Series, expected_index: pd.DatetimeIndex
) -> pd.Series:
    if not isinstance(benchmark_prices, pd.Series) or benchmark_prices.empty:
        raise BacktestValidationError(
            "Chuỗi giá chuẩn đối chiếu (benchmark_prices) phải là chuỗi pandas "
            "(Series) không rỗng."
        )
    benchmark = benchmark_prices.copy()
    benchmark.index = _validated_datetime_index(benchmark.index, "benchmark_prices")
    if not benchmark.index.equals(expected_index):
        raise BacktestValidationError(
            "Chuỗi giá chuẩn đối chiếu (benchmark_prices) phải dùng đúng cùng các thời "
            "điểm với bảng giá (prices); không cho phép phép nối trong ngầm định "
            "(implicit inner join)."
        )
    benchmark = pd.to_numeric(benchmark, errors="coerce").astype(float)
    if not np.isfinite(benchmark.to_numpy()).all() or (benchmark <= 0).any():
        raise BacktestValidationError(
            "Chuỗi giá chuẩn đối chiếu (benchmark_prices) phải hữu hạn, không thiếu "
            "và lớn hơn 0."
        )
    return benchmark


def _validate_weights(
    raw_weights: Mapping[str, float] | pd.Series,
    assets: pd.Index,
    config: BacktestConfig,
) -> pd.Series:
    if not isinstance(raw_weights, (Mapping, pd.Series)):
        raise BacktestValidationError(
            "Chiến lược (strategy) phải trả về ánh xạ (mapping) hoặc chuỗi pandas "
            "(Series) chứa tỷ trọng tài sản."
        )
    weights = pd.Series(dict(raw_weights), dtype=float)
    unknown = weights.index.difference(assets)
    if len(unknown):
        raise BacktestValidationError(
            f"Chiến lược (strategy) trả về tài sản không xác định: "
            f"{', '.join(map(str, unknown))}."
        )
    weights = weights.reindex(assets, fill_value=0.0).astype(float)
    if not np.isfinite(weights.to_numpy()).all():
        raise BacktestValidationError("Tỷ trọng của chiến lược (strategy) phải hữu hạn.")
    tolerance = 1e-10
    if not config.allow_short and (weights < -tolerance).any():
        raise BacktestValidationError(
            "Tỷ trọng âm yêu cầu bật bán khống (allow_short=True)."
        )
    if (weights.abs() > config.max_weight + tolerance).any():
        raise BacktestValidationError(
            "Một tỷ trọng chiến lược vượt tỷ trọng tối đa (max_weight)."
        )
    gross = float(weights.abs().sum())
    if gross > config.max_gross_leverage + tolerance:
        raise BacktestValidationError(
            "Chiến lược vượt đòn bẩy gộp tối đa (max_gross_leverage)."
        )
    if not config.allow_short and float(weights.sum()) > 1.0 + tolerance:
        raise BacktestValidationError(
            "Tổng tỷ trọng tài sản rủi ro chỉ mua (long-only) không được vượt 100%; "
            "phần tỷ trọng còn lại được xem là tiền mặt."
        )
    weights[weights.abs() < tolerance] = 0.0
    return weights


def _years_covered(index: pd.Index, observations: int, annualization: int) -> float:
    if isinstance(index, pd.DatetimeIndex) and len(index) >= 2:
        elapsed_days = (index[-1] - index[0]).total_seconds() / 86_400
        if elapsed_days > 0:
            # Include one representative period because return timestamps mark
            # period ends rather than the initial capital timestamp.
            typical_days = elapsed_days / (len(index) - 1)
            return (elapsed_days + typical_days) / 365.25
    return observations / annualization


def performance_metrics(
    returns: pd.Series,
    *,
    annualization: int = 252,
    risk_free_rate_annual: float = 0.0,
    turnover: pd.Series | None = None,
) -> dict[str, float | int]:
    """Calculate standard OOS performance metrics from simple returns.

    ``hit_rate`` is the fraction of OOS periods with a positive net return.  It
    is deliberately not described as the probability of a profitable trade.
    """

    if not isinstance(returns, pd.Series) or returns.empty:
        raise BacktestValidationError(
            "Chuỗi lợi suất (returns) phải là chuỗi pandas (Series) không rỗng."
        )
    r = pd.to_numeric(returns, errors="coerce").astype(float)
    if not np.isfinite(r.to_numpy()).all():
        raise BacktestValidationError(
            "Chuỗi lợi suất (returns) chứa giá trị thiếu hoặc không hữu hạn."
        )
    if (r <= -1).any():
        raise BacktestValidationError(
            "Lợi suất đơn (simple returns) phải lớn hơn -100%."
        )
    if annualization < 1 or risk_free_rate_annual <= -1:
        raise BacktestValidationError(
            "Hệ số năm hóa (annualization) hoặc lãi suất phi rủi ro "
            "(risk-free rate) không hợp lệ."
        )

    growth = float((1.0 + r).prod())
    total_return = growth - 1.0
    years = _years_covered(r.index, len(r), annualization)
    cagr = growth ** (1.0 / years) - 1.0 if years > 0 else np.nan
    volatility = float(r.std(ddof=1) * np.sqrt(annualization)) if len(r) > 1 else np.nan
    rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / annualization) - 1.0
    excess = r - rf_period
    excess_std = float(excess.std(ddof=1)) if len(excess) > 1 else np.nan
    sharpe = (
        float(excess.mean() / excess_std * np.sqrt(annualization))
        if np.isfinite(excess_std) and excess_std > 0
        else np.nan
    )
    downside_deviation = float(np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)))
    sortino = (
        float(excess.mean() / downside_deviation * np.sqrt(annualization))
        if downside_deviation > 0
        else np.nan
    )
    equity = np.concatenate(([1.0], np.cumprod(1.0 + r.to_numpy())))
    drawdowns = equity / np.maximum.accumulate(equity) - 1.0
    max_drawdown = float(drawdowns.min())

    if turnover is None:
        total_turnover = 0.0
        annualized_turnover = 0.0
    else:
        t = pd.to_numeric(turnover, errors="coerce").astype(float)
        if not np.isfinite(t.to_numpy()).all() or (t < 0).any():
            raise BacktestValidationError(
                "Mức xoay vòng danh mục (turnover) phải hữu hạn và không âm."
            )
        total_turnover = float(t.sum())
        annualized_turnover = total_turnover / years if years > 0 else np.nan

    return {
        "observations": int(len(r)),
        "total_return": total_return,
        "cagr": float(cagr),
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "hit_rate": float((r > 0).mean()),
        "total_turnover": total_turnover,
        "annualized_turnover": float(annualized_turnover),
    }


def run_walk_forward(
    prices: pd.DataFrame,
    benchmark_prices: pd.Series,
    strategy: Strategy,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a no-look-ahead walk-forward backtest with explicit execution lag.

    With the default one-period lag, a target calculated using data through
    close T executes at close T+1 and can first earn the close-to-close return
    from T+1 to T+2.  Configurable costs are deducted at execution immediately
    before that first eligible return.  ``execution_lag_periods=0`` preserves
    the older, optimistic same-close execution convention for comparison only.
    This is a research convention, not a promise of executable market prices.
    """

    cfg = config or BacktestConfig()
    if not callable(strategy):
        raise BacktestValidationError(
            "Chiến lược (strategy) phải là đối tượng có thể gọi như hàm (callable)."
        )
    clean_prices = _validate_prices(prices)
    benchmark = _validate_benchmark(benchmark_prices, clean_prices.index)

    asset_returns = clean_prices.pct_change(fill_method=None).iloc[1:]
    benchmark_returns = benchmark.pct_change(fill_method=None).iloc[1:]
    if cfg.max_abs_period_return is not None:
        extreme = asset_returns.abs() > cfg.max_abs_period_return
        if extreme.any().any():
            timestamp, asset = extreme.stack().loc[lambda x: x].index[0]
            value = asset_returns.loc[timestamp, asset]
            raise BacktestValidationError(
                f"Lợi suất bất thường {value:.2%} của {asset} tại {timestamp}; hãy kiểm tra "
                "sự kiện doanh nghiệp (corporate actions), lịch sử niêm yết và đơn vị giá."
            )

    required = (
        cfg.min_train_size + cfg.execution_lag_periods + cfg.min_test_size
    )
    if len(asset_returns) < required:
        raise BacktestValidationError(
            f"Cần ít nhất {required} quan sát lợi suất ({cfg.min_train_size} huấn luyện "
            f"(train) + {cfg.execution_lag_periods} kỳ trễ thực thi (execution lag) + "
            f"{cfg.min_test_size} ngoài mẫu (OOS)); hiện có {len(asset_returns)}."
        )

    assets = asset_returns.columns
    current_weights = pd.Series(0.0, index=assets, dtype=float)
    equity = float(cfg.initial_capital)
    benchmark_equity = float(cfg.initial_capital)
    rf_period = (1.0 + cfg.risk_free_rate_annual) ** (1.0 / cfg.annualization) - 1.0

    return_rows: list[dict[str, float]] = []
    equity_rows: list[dict[str, float]] = []
    weight_rows: list[dict[str, float]] = []
    rebalance_rows: list[dict[str, object]] = []
    result_index: list[pd.Timestamp] = []
    turnover_by_period: list[float] = []
    total_cost_amount = 0.0
    rebalance_number = 0
    # Snapshot weights at each close so StrategyContext never reveals drift
    # that occurred after its decision_time but before delayed execution.
    weights_at_close: dict[pd.Timestamp, pd.Series] = {}

    first_oos_position = cfg.min_train_size + cfg.execution_lag_periods
    for i in range(first_oos_position, len(asset_returns)):
        first_return_time = pd.Timestamp(asset_returns.index[i])
        # Return i runs from clean_prices[i] to clean_prices[i + 1].  Target
        # weights are acquired at its start, after the configured number of
        # complete periods has elapsed since the signal close.
        execution_time = pd.Timestamp(clean_prices.index[i])
        period_asset_returns = asset_returns.iloc[i]
        did_rebalance = (i - first_oos_position) % cfg.rebalance_every == 0
        turnover = 0.0
        buy_turnover = 0.0
        sell_turnover = 0.0
        cost_rate = 0.0
        cost_amount = 0.0

        if did_rebalance:
            decision_end = i - cfg.execution_lag_periods
            train_start = (
                0
                if cfg.train_window is None
                else max(0, decision_end - cfg.train_window)
            )
            training_returns = asset_returns.iloc[train_start:decision_end].copy(
                deep=True
            )
            if len(training_returns) < cfg.min_train_size:
                raise BacktestValidationError(
                    "Lát dữ liệu huấn luyện (training slice) nhỏ hơn cỡ mẫu tối thiểu "
                    "(min_train_size)."
                )
            decision_time = pd.Timestamp(training_returns.index[-1])
            expected_order = (
                decision_time == execution_time
                if cfg.execution_lag_periods == 0
                else decision_time < execution_time
            )
            if not expected_order or not execution_time < first_return_time:
                raise RuntimeError(
                    "Cơ chế chống nhìn trước tương lai (look-ahead guard) thất bại: thứ tự "
                    "quyết định/thực thi/lợi suất không hợp lệ."
                )
            if decision_time == execution_time:
                previous_weights_at_decision = current_weights.copy()
            elif decision_end < first_oos_position:
                # Before the first execution the simulated portfolio is cash,
                # so no historical risky-weight snapshot exists by design.
                previous_weights_at_decision = pd.Series(
                    0.0, index=assets, dtype=float
                )
            else:
                try:
                    previous_weights_at_decision = weights_at_close[
                        decision_time
                    ].copy()
                except KeyError as exc:
                    raise RuntimeError(
                        "Bất biến ảnh chụp tỷ trọng (weight snapshot) thất bại tại thời điểm "
                        "quyết định (decision_time)."
                    ) from exc
            context = StrategyContext(
                rebalance_number=rebalance_number,
                decision_time=decision_time,
                execution_time=execution_time,
                previous_weights=previous_weights_at_decision,
                first_return_time=first_return_time,
                execution_lag_periods=cfg.execution_lag_periods,
            )
            target_weights = _validate_weights(
                strategy(training_returns, context), assets, cfg
            )
            delta = target_weights - current_weights
            buy_turnover = float(delta.clip(lower=0).sum())
            sell_turnover = float((-delta.clip(upper=0)).sum())
            old_cash = 1.0 - float(current_weights.sum())
            new_cash = 1.0 - float(target_weights.sum())
            turnover = 0.5 * (float(delta.abs().sum()) + abs(new_cash - old_cash))
            round_trip_bps = cfg.fee_bps + cfg.slippage_bps
            cost_rate = (
                buy_turnover * round_trip_bps
                + sell_turnover * (round_trip_bps + cfg.sell_tax_bps)
            ) / 10_000.0
            if cost_rate >= 1.0:
                raise BacktestValidationError(
                    "Chi phí giao dịch (transaction costs) làm cạn toàn bộ vốn."
                )
            cost_amount = equity * cost_rate
            total_cost_amount += cost_amount
            equity -= cost_amount
            current_weights = target_weights
            rebalance_row: dict[str, object] = {
                "rebalance_number": rebalance_number,
                "decision_time": decision_time,
                "execution_time": execution_time,
                "first_return_time": first_return_time,
                "execution_lag_periods": cfg.execution_lag_periods,
                "train_start": pd.Timestamp(training_returns.index[0]),
                "train_end": decision_time,
                "training_observations": int(len(training_returns)),
                "buy_turnover": buy_turnover,
                "sell_turnover": sell_turnover,
                "turnover": turnover,
                "cost_rate": cost_rate,
                "cost_amount": cost_amount,
            }
            rebalance_row.update(
                {f"weight_{asset}": float(target_weights[asset]) for asset in assets}
            )
            rebalance_rows.append(rebalance_row)
            rebalance_number += 1

        # Record post-trade weights at the execution close.  A future delayed
        # decision may legitimately see this snapshot, but never later drift.
        weights_at_close[execution_time] = current_weights.copy()

        # Preserve the exact start-of-period weights used for this return.  The
        # internal weights are drifted only after the period is booked.
        period_weights = current_weights.copy()
        equity_before_period = equity
        cash_weight = 1.0 - float(current_weights.sum())
        gross_return = float(current_weights @ period_asset_returns + cash_weight * rf_period)
        if gross_return <= -1.0 or not np.isfinite(gross_return):
            raise BacktestValidationError(
                f"Danh mục đã mất toàn bộ vốn hoặc có giá trị không hữu hạn tại "
                f"{first_return_time}."
            )
        equity *= 1.0 + gross_return
        net_return = equity / (equity_before_period + cost_amount) - 1.0

        benchmark_return = float(benchmark_returns.iloc[i])
        benchmark_equity *= 1.0 + benchmark_return
        end_values = current_weights * (1.0 + period_asset_returns)
        end_cash = cash_weight * (1.0 + rf_period)
        period_growth = float(end_values.sum() + end_cash)
        current_weights = end_values / period_growth

        result_index.append(first_return_time)
        return_rows.append(
            {
                "gross_return": gross_return,
                "net_return": net_return,
                "benchmark_return": benchmark_return,
                "cost_rate": cost_rate,
            }
        )
        equity_rows.append(
            {"portfolio": equity, "benchmark": benchmark_equity}
        )
        weight_rows.append({asset: float(period_weights[asset]) for asset in assets})
        turnover_by_period.append(turnover)

    result_returns = pd.DataFrame(return_rows, index=pd.DatetimeIndex(result_index))
    equity_curve = pd.DataFrame(equity_rows, index=result_returns.index)
    weights_frame = pd.DataFrame(weight_rows, index=result_returns.index)
    rebalances = pd.DataFrame(rebalance_rows)
    turnover_series = pd.Series(turnover_by_period, index=result_returns.index)
    metrics = performance_metrics(
        result_returns["net_return"],
        annualization=cfg.annualization,
        risk_free_rate_annual=cfg.risk_free_rate_annual,
        turnover=turnover_series,
    )
    metrics.update(
        {
            "rebalance_count": int(len(rebalances)),
            "total_transaction_cost": float(total_cost_amount),
            "ending_equity": float(equity),
        }
    )
    benchmark_metrics = performance_metrics(
        result_returns["benchmark_return"],
        annualization=cfg.annualization,
        risk_free_rate_annual=cfg.risk_free_rate_annual,
    )
    benchmark_metrics["ending_equity"] = float(benchmark_equity)
    comparison = {
        "total_return_excess": float(
            metrics["total_return"] - benchmark_metrics["total_return"]
        ),
        "cagr_excess": float(metrics["cagr"] - benchmark_metrics["cagr"]),
        "max_drawdown_difference": float(
            metrics["max_drawdown"] - benchmark_metrics["max_drawdown"]
        ),
    }
    return BacktestResult(
        equity_curve=equity_curve,
        returns=result_returns,
        weights=weights_frame,
        rebalances=rebalances,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        comparison=comparison,
        config=cfg,
    )
