import pandas as pd
import numpy as np
from data_loader import fetch_data, calculate_returns
from analytics import run_sim

def test_data_pipeline():
    print("--- Test: vnstock Data Fetching ---")
    tickers = ["FPT", "VNINDEX"]
    # 1 month of data
    df = fetch_data(tickers, "2023-01-01", "2023-02-01")
    
    assert not df.empty, "Dataframe is empty. vnstock fetch failed."
    assert "FPT" in df.columns, "FPT column missing."
    assert "VNINDEX" in df.columns, "VNINDEX column missing."
    print("=> Data fetch SUCCESS.")
    
    print("--- Test: Return calculation (No Inf/NaN errors) ---")
    returns = calculate_returns(df)
    assert not returns.empty, "Returns dataframe is empty."
    print("=> Returns calculation SUCCESS.")
    
    print("--- Test: SIM Model ---")
    sim_res = run_sim(returns["FPT"], returns["VNINDEX"])
    assert "beta" in sim_res, "Beta missing in SIM result."
    print(f"=> SIM Model SUCCESS. FPT Beta: {sim_res['beta']:.4f}")
    
    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    test_data_pipeline()
