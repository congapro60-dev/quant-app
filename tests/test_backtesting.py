from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting import (
    BacktestConfig,
    BacktestValidationError,
    equal_weight_strategy,
    fixed_weight_strategy,
    performance_metrics,
    run_walk_forward,
)


def make_prices(rows: int = 14) -> tuple[pd.DataFrame, pd.Series]:
    index = pd.bdate_range("2025-01-01", periods=rows)
    a_returns = np.resize(np.array([0.01, -0.005, 0.008, 0.002]), rows - 1)
    b_returns = np.resize(np.array([0.002, 0.004, -0.003, 0.006]), rows - 1)
    benchmark_returns = np.resize(np.array([0.003, -0.001, 0.004]), rows - 1)
    prices = pd.DataFrame(
        {
            "A": 100 * np.r_[1.0, np.cumprod(1.0 + a_returns)],
            "B": 100 * np.r_[1.0, np.cumprod(1.0 + b_returns)],
        },
        index=index,
    )
    benchmark = pd.Series(
        1_000 * np.r_[1.0, np.cumprod(1.0 + benchmark_returns)],
        index=index,
        name="BENCHMARK",
    )
    return prices, benchmark


def small_config(**overrides) -> BacktestConfig:
    values = {
        "min_train_size": 5,
        "min_test_size": 3,
        "train_window": 5,
        "rebalance_every": 2,
        "initial_capital": 1_000.0,
        "max_abs_period_return": None,
    }
    values.update(overrides)
    return BacktestConfig(**values)


def test_walk_forward_never_exposes_execution_return_to_strategy():
    prices, benchmark = make_prices()
    calls: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []

    def audited_strategy(training_returns, context):
        calls.append(
            (training_returns.index.max(), context.execution_time, len(training_returns))
        )
        assert training_returns.index.max() == context.decision_time
        assert training_returns.index.max() < context.execution_time
        assert context.execution_time not in training_returns.index
        return {"A": 1.0}

    result = run_walk_forward(prices, benchmark, audited_strategy, small_config())

    assert calls
    assert all(train_end < execution for train_end, execution, _ in calls)
    assert all(size == 5 for _, _, size in calls)
    assert (result.rebalances["train_end"] < result.rebalances["execution_time"]).all()
    assert result.returns.index.equals(prices.index[6:])
    assert result.returns["benchmark_return"].notna().all()
    assert result.metrics["observations"] == len(prices) - 1 - 5


def test_costs_slippage_tax_and_turnover_are_charged_on_each_leg():
    index = pd.bdate_range("2025-01-01", periods=8)
    prices = pd.DataFrame({"A": 100.0, "B": 100.0}, index=index)
    benchmark = pd.Series(1_000.0, index=index)

    def alternate(_training, context):
        return {"A": 1.0} if context.rebalance_number % 2 == 0 else {"B": 1.0}

    cfg = BacktestConfig(
        min_train_size=2,
        min_test_size=2,
        train_window=2,
        rebalance_every=1,
        fee_bps=10,
        slippage_bps=5,
        sell_tax_bps=10,
        initial_capital=1_000.0,
        max_abs_period_return=None,
    )
    result = run_walk_forward(prices, benchmark, alternate, cfg)

    # Initial cash->asset trade costs 15 bps.  Every A<->B switch has a
    # 15-bps buy leg plus a 25-bps sell leg.
    expected_rates = np.array([0.0015, 0.004, 0.004, 0.004, 0.004])
    np.testing.assert_allclose(result.returns["cost_rate"], expected_rates)
    np.testing.assert_allclose(result.returns["net_return"], -expected_rates)
    assert result.metrics["total_turnover"] == pytest.approx(5.0)
    assert result.metrics["ending_equity"] == pytest.approx(
        1_000 * np.prod(1.0 - expected_rates)
    )
    assert result.benchmark_metrics["total_return"] == pytest.approx(0.0)


def test_performance_metrics_have_documented_signs_and_hit_rate():
    index = pd.bdate_range("2025-01-01", periods=4)
    returns = pd.Series([0.10, -0.05, 0.02, -0.10], index=index)
    metrics = performance_metrics(returns, annualization=252)
    equity = np.r_[1.0, np.cumprod(1.0 + returns.to_numpy())]
    expected_drawdown = (equity / np.maximum.accumulate(equity) - 1).min()

    assert metrics["total_return"] == pytest.approx(float((1 + returns).prod() - 1))
    assert metrics["max_drawdown"] == pytest.approx(expected_drawdown)
    assert metrics["max_drawdown"] <= 0
    assert metrics["hit_rate"] == pytest.approx(0.5)
    assert np.isfinite(metrics["annualized_volatility"])
    assert np.isfinite(metrics["sharpe"])
    assert np.isfinite(metrics["sortino"])


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda p: p.iloc[::-1], "oldest to newest"),
        (lambda p: p.assign(A=lambda x: x["A"].mask(x.index == x.index[3])), "missing"),
    ],
)
def test_price_validation_rejects_unsorted_or_missing_data(mutator, message):
    prices, benchmark = make_prices()
    bad = mutator(prices)
    if bad.index.equals(benchmark.index):
        bad_benchmark = benchmark
    else:
        bad_benchmark = benchmark.iloc[::-1]
    with pytest.raises(BacktestValidationError, match=message):
        run_walk_forward(bad, bad_benchmark, equal_weight_strategy, small_config())


def test_benchmark_calendar_must_match_exactly():
    prices, benchmark = make_prices()
    with pytest.raises(BacktestValidationError, match="exactly the same timestamps"):
        run_walk_forward(
            prices, benchmark.iloc[1:], equal_weight_strategy, small_config()
        )


def test_minimum_sample_and_weight_limits_are_enforced():
    prices, benchmark = make_prices(rows=7)
    with pytest.raises(BacktestValidationError, match="Need at least"):
        run_walk_forward(prices, benchmark, equal_weight_strategy, small_config())

    prices, benchmark = make_prices()
    with pytest.raises(BacktestValidationError, match="exceeds max_weight"):
        run_walk_forward(
            prices,
            benchmark,
            fixed_weight_strategy({"A": 1.2}),
            small_config(),
        )


def test_implausible_period_return_is_rejected_for_data_review():
    prices, benchmark = make_prices()
    prices.loc[prices.index[8], "A"] *= 4
    cfg = small_config(max_abs_period_return=1.0)
    with pytest.raises(BacktestValidationError, match="corporate actions"):
        run_walk_forward(prices, benchmark, equal_weight_strategy, cfg)


def test_result_is_session_state_friendly_and_contains_benchmark_comparison():
    prices, benchmark = make_prices()
    result = run_walk_forward(
        prices, benchmark, fixed_weight_strategy({"A": 0.5, "B": 0.25}), small_config()
    )
    payload = result.to_session_state()

    assert set(payload) == {
        "equity_curve",
        "returns",
        "weights",
        "rebalances",
        "metrics",
        "benchmark_metrics",
        "comparison",
        "config",
    }
    assert {"total_return_excess", "cagr_excess", "max_drawdown_difference"} <= set(
        result.comparison
    )
    rebalance_dates = pd.DatetimeIndex(result.rebalances["execution_time"])
    assert np.allclose(result.weights.loc[rebalance_dates].sum(axis=1), 0.75)
    # Between rebalances the weights must be allowed to drift with prices.
    assert not np.allclose(result.weights.sum(axis=1), 0.75)
