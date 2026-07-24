import pandas as pd
import numpy as np
from vnstock.api.quote import Quote

def fetch_data(tickers, start_date, end_date):
    """
    Fetches historical adjusted close prices for given tickers using vnstock v4.x.
    """
    df_list = []
    
    # Remove duplicates but preserve order
    all_tickers = list(dict.fromkeys(tickers))
    
    for ticker in all_tickers:
        try:
            # Fetch historical data using vnstock v4 Quote API
            df = Quote(symbol=ticker, source="VCI").history(start=start_date, end=end_date)
            
            if df is not None and not df.empty:
                # Use 'close' price
                df = df[['time', 'close']].rename(columns={'close': ticker})
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                df_list.append(df)
            else:
                print(f"Warning: Empty data returned for {ticker}")
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    # Merge all DataFrames on index (time)
    final_df = df_list[0]
    for i in range(1, len(df_list)):
        final_df = final_df.join(df_list[i], how='inner')
        
    return final_df

def calculate_returns(prices_df):
    """
    Calculates daily log returns from prices: ln(S_t / S_{t-1})
    Replaces zero or negative prices with NaN before calculating to prevent inf/-inf.
    """
    # Prevent taking log of zero or negative numbers
    safe_prices = prices_df.copy()
    safe_prices[safe_prices <= 0] = np.nan
    
    returns = np.log(safe_prices / safe_prices.shift(1)).dropna()
    return returns

