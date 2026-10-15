import pandas as pd

from analytics import markowitz_optimization, run_sim
from data_loader import calculate_returns
from sample_data import make_sample_prices


def test_sample_is_explicitly_synthetic_and_supports_core_models():
    prices = make_sample_prices()
    assert prices.attrs["data_kind"] == "synthetic_sample"
    assert prices.attrs["fetch_report"]["sample"] is True
    returns = calculate_returns(prices).dropna()
    sim = run_sim(returns["CTG"], returns["VNINDEX"])
    opt = markowitz_optimization(returns[["CTG", "HPG", "FPT"]], num_portfolios=20)
    assert len(returns) > 200
    assert pd.notna(sim["beta"])
    assert len(opt["min_vol_weights"]) == 3
