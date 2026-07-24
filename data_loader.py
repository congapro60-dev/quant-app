import pandas as pd
from vnstock3 import Vnstock

def fetch_data(tickers, start_date, end_date):
    """
    Fetches historical adjusted close prices for given tickers using vnstock3.
    
    Args:
        tickers (list): List of ticker symbols (e.g. ['HPG', 'FPT', 'VNINDEX']).
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.
        
    Returns:
        pd.DataFrame: DataFrame containing adjusted close prices.
    """
    df_list = []
    
    # Initialize vnstock object
    stock = Vnstock()
    
    for ticker in tickers:
        try:
            # vnstock expects VNINDEX as 'VNINDEX'
            is_index = ticker.upper() in ['VNINDEX', 'VN30', 'HNX', 'UPCOM']
            
            # Fetch historical data
            df = stock.stock.quote.history(symbol=ticker, start=start_date, end=end_date)
            
            if not df.empty:
                # Use 'close' price
                df = df[['time', 'close']].rename(columns={'close': ticker})
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                df_list.append(df)
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
    Calculates daily returns from prices.
    
    Args:
        prices_df (pd.DataFrame): DataFrame of prices.
        
    Returns:
        pd.DataFrame: DataFrame of daily returns.
    """
    returns = prices_df.pct_change().dropna()
    return returns
