"""Deterministic offline market sample for lessons and classroom practice."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_sample_prices(*, periods: int = 260, seed: int = 42) -> pd.DataFrame:
    """Return clearly labelled synthetic prices; never presented as live data."""

    if periods < 80:
        raise ValueError("Cần ít nhất 80 phiên dữ liệu minh họa.")
    dates = pd.bdate_range("2024-01-02", periods=periods, tz=None)
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0003, 0.011, periods)
    shocks = rng.normal(0.0, 0.008, (periods, 3))
    returns = np.column_stack([
        market * 1.05 + shocks[:, 0],
        market * 0.85 + shocks[:, 1],
        market * 1.20 + shocks[:, 2],
        market,
    ])
    initial = np.array([35.0, 28.0, 100.0, 1200.0])
    prices = initial * np.exp(np.cumsum(returns, axis=0))
    frame = pd.DataFrame(prices, index=dates, columns=["CTG", "HPG", "FPT", "VNINDEX"])
    frame.attrs["fetch_report"] = {
        "source": "Dữ liệu minh họa offline (synthetic sample)",
        "sample": True,
    }
    frame.attrs["data_kind"] = "synthetic_sample"
    return frame
