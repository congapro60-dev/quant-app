"""Bán khống trong Markowitz chỉ bật khi người dùng yêu cầu.

Mặc định vẫn chỉ mua, tỷ trọng nằm trong [0, 1]. Khi bật, tổng tỷ trọng luôn bằng 1
và mỗi tỷ trọng nằm trong [-1, 1]. Phương sai danh mục tối thiểu khi có bán khống
không được cao hơn khi chỉ mua.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics import SHORT_WEIGHT_LIMIT, _sample_short_portfolios, markowitz_optimization
from data_loader import calculate_returns

FIXTURE = Path(__file__).parent / "fixtures" / "eviews_parity_150.csv"
TRADING_DAYS = 252


@pytest.fixture(scope="module")
def excel_returns():
    prices = pd.read_csv(FIXTURE)[["VIC", "REE", "STB"]]
    return calculate_returns(prices)


def _variance(weights, returns):
    cov = returns.cov().to_numpy() * TRADING_DAYS
    w = np.asarray(weights, dtype=float)
    return float(w @ cov @ w)


def test_default_is_still_long_only(excel_returns):
    opt = markowitz_optimization(excel_returns)
    assert opt["allow_short"] is False
    assert opt["weight_bounds"] == (0.0, 1.0)
    assert (np.asarray(opt["min_vol_weights"]) >= -1e-9).all()
    assert (np.asarray(opt["max_sharpe_weights"]) >= -1e-9).all()


def test_short_selling_keeps_budget_and_bounds(excel_returns):
    opt = markowitz_optimization(excel_returns, allow_short=True)
    assert opt["allow_short"] is True
    assert opt["weight_bounds"] == (-SHORT_WEIGHT_LIMIT, SHORT_WEIGHT_LIMIT)
    for key in ("min_vol_weights", "max_sharpe_weights"):
        w = np.asarray(opt[key])
        assert w.sum() == pytest.approx(1.0, abs=1e-9)
        assert (w >= -SHORT_WEIGHT_LIMIT - 1e-9).all()
        assert (w <= SHORT_WEIGHT_LIMIT + 1e-9).all()


def test_short_min_variance_is_never_worse_than_long_only(excel_returns):
    long_only = markowitz_optimization(excel_returns)
    short = markowitz_optimization(excel_returns, allow_short=True)
    assert _variance(short["min_vol_weights"], excel_returns) <= (
        _variance(long_only["min_vol_weights"], excel_returns) + 1e-12
    )


def test_short_max_sharpe_takes_a_negative_leg_on_course_data(excel_returns):
    short = markowitz_optimization(excel_returns, allow_short=True)
    assert np.min(short["max_sharpe_weights"]) < 0


def test_short_frontier_cloud_has_requested_size_and_is_finite(excel_returns):
    short = markowitz_optimization(excel_returns, allow_short=True, num_portfolios=200)
    assert len(short["ef_vols"]) == 200
    assert np.isfinite(short["ef_vols"]).all()


def test_short_sampler_respects_budget_and_bounds():
    rng = np.random.default_rng(11)
    w = _sample_short_portfolios(rng, 4, 300, -SHORT_WEIGHT_LIMIT, SHORT_WEIGHT_LIMIT)
    assert w.shape == (300, 4)
    assert np.allclose(w.sum(axis=1), 1.0)
    assert (w >= -SHORT_WEIGHT_LIMIT - 1e-9).all()
    assert (w <= SHORT_WEIGHT_LIMIT + 1e-9).all()


def _synthetic_returns(mu_annual, seed=0, days=300):
    rng = np.random.default_rng(seed)
    noise = rng.normal(size=(days, len(mu_annual))) * 0.01
    noise = noise - noise.mean(axis=0)
    daily = np.array(mu_annual, dtype=float) / TRADING_DAYS
    return pd.DataFrame(noise + daily, columns=["A" + str(i) for i in range(len(mu_annual))])


def test_short_selling_beats_cash_when_a_long_short_mix_clears_rf():
    # Cả ba tài sản dưới lãi suất phi rủi ro 4%, nhưng mua hai mã tốt nhất và bán khống mã xấu nhất cho lợi suất trên 4%.
    returns = _synthetic_returns([-0.0426, -0.0426, -0.1622])
    rf = 0.04
    long_only = markowitz_optimization(returns, risk_free_rate=rf)
    assert long_only["cash_weight"] == pytest.approx(1.0)
    short = markowitz_optimization(returns, risk_free_rate=rf, allow_short=True)
    mean_annual = returns.mean().to_numpy() * TRADING_DAYS
    weights = np.asarray(short["max_sharpe_weights"])
    assert short["cash_weight"] == pytest.approx(0.0)
    assert short["warning"] is None
    assert weights.sum() == pytest.approx(1.0, abs=1e-9)
    assert float(weights @ mean_annual) > rf
    assert (weights >= -SHORT_WEIGHT_LIMIT - 1e-9).all()
    assert (weights <= SHORT_WEIGHT_LIMIT + 1e-9).all()


def test_short_selling_keeps_cash_when_no_mix_clears_rf():
    returns = _synthetic_returns([-0.2, -0.2, -0.2])
    short = markowitz_optimization(returns, risk_free_rate=0.04, allow_short=True)
    assert short["cash_weight"] == pytest.approx(1.0)
    assert short["warning"] is not None


def test_two_assets_cannot_short_under_the_bounds_so_cash_still_applies():
    # Với hai tài sản và tổng tỷ trọng bằng 1, trần ±100% chỉ cho danh mục chỉ mua.
    returns = _synthetic_returns([-0.0426, -0.1622])
    short = markowitz_optimization(returns, risk_free_rate=0.04, allow_short=True)
    assert short["cash_weight"] == pytest.approx(1.0)
