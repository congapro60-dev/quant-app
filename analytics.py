import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_white, acorr_breusch_godfrey
from scipy.optimize import minimize

def run_sim(asset_returns, market_returns):
    """
    Run Single Index Model (SIM): r_i = alpha + beta * r_m + e_i
    """
    # Align data
    df = pd.concat([asset_returns, market_returns], axis=1).dropna()
    df.columns = ['Asset', 'Market']
    
    y = df['Asset']
    X = df['Market']
    X = sm.add_add_constant(X) # Ensure X is correctly shaped, add_constant might be buggy, let's use sm.add_constant
    
    # Run OLS
    model = sm.OLS(y, sm.add_constant(df['Market']))
    results = model.fit()
    
    # Calculate risks
    beta = results.params['Market']
    alpha = results.params['const']
    
    market_var = df['Market'].var()
    residual_var = results.resid.var()
    
    sys_risk = (beta ** 2) * market_var
    unsys_risk = residual_var
    total_risk = df['Asset'].var()
    
    return {
        'alpha': alpha,
        'beta': beta,
        'systematic_risk': sys_risk,
        'unsystematic_risk': unsys_risk,
        'total_risk': total_risk,
        'r_squared': results.rsquared,
        'model': results,
        'X': sm.add_constant(df['Market'])
    }

def run_diagnostics(sim_results):
    """
    Run White test for heteroskedasticity and Breusch-Godfrey for autocorrelation.
    """
    model = sim_results['model']
    X = sim_results['X']
    
    diagnostics = {}
    
    # White Test
    try:
        white_test = het_white(model.resid, X)
        diagnostics['White_pvalue'] = white_test[1]
        diagnostics['Heteroskedasticity'] = "Yes" if white_test[1] < 0.05 else "No"
    except Exception as e:
        diagnostics['White_pvalue'] = None
        diagnostics['Heteroskedasticity'] = "Error"

    # Breusch-Godfrey Test
    try:
        bg_test = acorr_breusch_godfrey(model, nlags=1)
        diagnostics['BG_pvalue'] = bg_test[1]
        diagnostics['Autocorrelation'] = "Yes" if bg_test[1] < 0.05 else "No"
    except Exception as e:
        diagnostics['BG_pvalue'] = None
        diagnostics['Autocorrelation'] = "Error"
        
    return diagnostics

def markowitz_optimization(returns_df):
    """
    Perform Markowitz Portfolio Optimization to find the weights for minimum variance (safest) portfolio
    and maximum Sharpe ratio portfolio.
    """
    num_assets = len(returns_df.columns)
    mean_returns = returns_df.mean() * 252 # Annualized
    cov_matrix = returns_df.cov() * 252
    
    def portfolio_annualised_performance(weights, mean_returns, cov_matrix):
        returns = np.sum(mean_returns * weights)
        std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return std, returns
        
    def minimize_volatility(weights, mean_returns, cov_matrix):
        return portfolio_annualised_performance(weights, mean_returns, cov_matrix)[0]
        
    def negative_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.04):
        p_vol, p_ret = portfolio_annualised_performance(weights, mean_returns, cov_matrix)
        return -(p_ret - risk_free_rate) / p_vol
        
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0, 1) for _ in range(num_assets))
    init_guess = num_assets * [1. / num_assets,]
    
    # Min Volatility Portfolio (Safest)
    min_vol = minimize(minimize_volatility, init_guess, args=(mean_returns, cov_matrix), method='SLSQP', bounds=bounds, constraints=constraints)
    
    # Max Sharpe Portfolio
    max_sharpe = minimize(negative_sharpe_ratio, init_guess, args=(mean_returns, cov_matrix), method='SLSQP', bounds=bounds, constraints=constraints)
    
    return {
        'min_vol_weights': min_vol.x,
        'max_sharpe_weights': max_sharpe.x,
        'assets': returns_df.columns.tolist()
    }

def generate_expert_advice(sim_results_list, opt_res, market_prices):
    """
    Synthesize quantitative results into actionable expert advice.
    """
    advice = []
    
    # 1. Market Trend Analysis (Simple Linear Trend on Prices)
    y = market_prices.values
    x = np.arange(len(y))
    x = sm.add_constant(x)
    trend_model = sm.OLS(y, x).fit()
    trend_coef = trend_model.params[1]
    
    if trend_coef > 0:
        market_trend = "TĂNG (Bullish)"
        strategy = "Thị trường đang trong xu hướng tăng. Nên ưu tiên nắm giữ các cổ phiếu Năng động ($\\beta > 1$) để tối đa hóa lợi nhuận theo đà tăng của thị trường."
    else:
        market_trend = "GIẢM (Bearish)"
        strategy = "Thị trường đang trong xu hướng giảm hoặc đi ngang. Nên phòng thủ, ưu tiên các cổ phiếu Thụ động ($\\beta < 1$) hoặc chuyển sang tiền mặt."
        
    advice.append(f"### 📈 Xu hướng Thị trường: **{market_trend}**")
    advice.append(strategy)
    
    # 2. Stock Selection (based on SIM)
    high_beta = [res['Mã CP'] for res in sim_results_list if res['Beta (Độ nhạy)'] > 1]
    low_beta = [res['Mã CP'] for res in sim_results_list if res['Beta (Độ nhạy)'] < 1]
    
    if high_beta:
        advice.append(f"*   **Nhóm Tấn công ($\\beta > 1$):** `{', '.join(high_beta)}` - Phù hợp khi dự báo thị trường tiếp tục Tăng.")
    if low_beta:
        advice.append(f"*   **Nhóm Phòng thủ ($\\beta < 1$):** `{', '.join(low_beta)}` - Phù hợp khi dự báo thị trường Giảm hoặc Biến động mạnh.")

    # 3. Portfolio Allocation (based on Max Sharpe)
    assets = opt_res['assets']
    sharpe_weights = opt_res['max_sharpe_weights']
    
    # Get top 2-3 stocks with highest weight in Max Sharpe portfolio
    weighted_assets = sorted(zip(assets, sharpe_weights), key=lambda x: x[1], reverse=True)
    top_picks = [f"**{w[0]}** ({w[1]*100:.1f}%)" for w in weighted_assets if w[1] > 0.05] # Only suggest if weight > 5%
    
    advice.append("### 💡 Khuyến nghị Hành động (Dành cho bạn)")
    if top_picks:
        advice.append(f"Để tối ưu hóa Tỷ suất Sinh lời / Rủi ro (theo tiêu chuẩn của các Quỹ đầu tư), bạn nên cân nhắc giải ngân phần lớn vốn vào: {', '.join(top_picks)}.")
    else:
        advice.append("Hiện tại các cổ phiếu trong danh mục có rủi ro cao, tỷ trọng tối ưu phân bổ khá đều hoặc rủi ro, cân nhắc giữ tiền mặt.")
        
    return "\\n\\n".join(advice)

