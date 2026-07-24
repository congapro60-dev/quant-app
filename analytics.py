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
    X = sm.add_constant(X) # Ensure X is correctly shaped
    
    # Run OLS
    model = sm.OLS(y, X)
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
    and maximum Sharpe ratio portfolio. Also generates an efficient frontier simulation.
    """
    num_assets = len(returns_df.columns)
    mean_returns = returns_df.mean() * 252 # Annualized
    cov_matrix = returns_df.cov() * 252
    risk_free_rate = 0.04
    
    def portfolio_annualised_performance(weights, mean_returns, cov_matrix):
        returns = np.sum(mean_returns * weights)
        std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return std, returns
        
    def minimize_volatility(weights, mean_returns, cov_matrix):
        return portfolio_annualised_performance(weights, mean_returns, cov_matrix)[0]
        
    def negative_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.04):
        p_vol, p_ret = portfolio_annualised_performance(weights, mean_returns, cov_matrix)
        # Prevent division by zero
        if p_vol == 0:
            return float('inf')
        return -(p_ret - risk_free_rate) / p_vol
        
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0, 1) for _ in range(num_assets))
    init_guess = num_assets * [1. / num_assets,]
    
    # Min Volatility Portfolio (Safest)
    min_vol = minimize(minimize_volatility, init_guess, args=(mean_returns, cov_matrix), method='SLSQP', bounds=bounds, constraints=constraints)
    
    # Max Sharpe Portfolio
    # If the maximum possible return is less than risk free rate, Max Sharpe will try to maximize volatility. 
    # In this case, we fallback to min_vol weights.
    if np.max(mean_returns) <= risk_free_rate:
        max_sharpe_weights = min_vol.x
        warning_msg = "Lợi suất kỳ vọng của tất cả tài sản đều thấp hơn lãi suất phi rủi ro (4%). Danh mục Max Sharpe được chuyển về Min Volatility."
    else:
        max_sharpe = minimize(negative_sharpe_ratio, init_guess, args=(mean_returns, cov_matrix), method='SLSQP', bounds=bounds, constraints=constraints)
        max_sharpe_weights = max_sharpe.x
        warning_msg = None
        
    # Simulate Efficient Frontier points for plotting
    num_portfolios = 500
    results = np.zeros((3, num_portfolios))
    weights_record = []
    
    for i in range(num_portfolios):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)
        p_vol, p_ret = portfolio_annualised_performance(weights, mean_returns, cov_matrix)
        results[0,i] = p_vol
        results[1,i] = p_ret
        results[2,i] = (p_ret - risk_free_rate) / p_vol if p_vol > 0 else 0
        weights_record.append(weights)
        
    return {
        'min_vol_weights': min_vol.x,
        'max_sharpe_weights': max_sharpe_weights,
        'assets': returns_df.columns.tolist(),
        'warning': warning_msg,
        'ef_vols': results[0,:],
        'ef_rets': results[1,:],
        'ef_sharpes': results[2,:]
    }

def call_llm(prompt, config):
    if not config or not config.get('api_key'):
        return None
        
    try:
        if config['provider'] == 'Anthropic (Claude)':
            import anthropic
            client = anthropic.Anthropic(api_key=config['api_key'])
            message = client.messages.create(
                model=config['model'],
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
            
        elif config['provider'] == 'Google (Gemini)':
            import google.generativeai as genai
            genai.configure(api_key=config['api_key'])
            model = genai.GenerativeModel(config['model'])
            response = model.generate_content(prompt)
            return response.text
    except Exception as e:
        return f"Lỗi gọi API: {str(e)}"
    
    return None

def generate_expert_advice(sim_results_list, opt_res, market_prices, ai_config=None):
    """
    Synthesize quantitative results into actionable expert advice.
    Optionally uses an LLM to generate more comprehensive advice.
    """
    # 1. Prepare data facts
    market_prices = market_prices.dropna()
    y = market_prices.values
    x = np.arange(len(y))
    x = sm.add_constant(x)
    trend_model = sm.OLS(y, x).fit()
    trend_coef = trend_model.params[1]
    
    market_trend = "TĂNG" if trend_coef > 0 else "GIẢM"
    
    high_beta = [res['Mã CP'] for res in sim_results_list if res['Beta (Độ nhạy)'] > 1]
    low_beta = [res['Mã CP'] for res in sim_results_list if res['Beta (Độ nhạy)'] < 1]
    
    assets = opt_res['assets']
    sharpe_weights = opt_res['max_sharpe_weights']
    weighted_assets = sorted(zip(assets, sharpe_weights), key=lambda x: x[1], reverse=True)
    top_picks = [f"{w[0]} ({w[1]*100:.1f}%)" for w in weighted_assets if w[1] > 0.05]
    
    # Try LLM generation if configured
    if ai_config and ai_config.get('api_key'):
        prompt = f"""
        Bạn là một chuyên gia phân tích định lượng tài chính cấp cao. Hãy đọc các số liệu định lượng sau và đưa ra một báo cáo khuyến nghị ngắn gọn, chuyên nghiệp bằng tiếng Việt.
        
        THÔNG TIN THỊ TRƯỜNG:
        - Xu hướng giá Index hiện tại: {market_trend}
        
        THÔNG TIN CỔ PHIẾU (Mô hình SIM):
        - Nhóm năng động (Beta > 1): {', '.join(high_beta) if high_beta else 'Không có'}
        - Nhóm phòng thủ (Beta < 1): {', '.join(low_beta) if low_beta else 'Không có'}
        
        TỐI ƯU HÓA DANH MỤC MARKOWITZ (Danh mục hiệu quả Max Sharpe):
        - Các mã nên phân bổ vốn nhiều nhất (tỷ trọng > 5%): {', '.join(top_picks) if top_picks else 'Nên giữ tiền mặt'}
        - Cảnh báo mô hình: {opt_res.get('warning') if opt_res.get('warning') else 'Không có'}
        
        YÊU CẦU:
        1. Mở đầu bằng một nhận định ngắn về xu hướng thị trường.
        2. Đánh giá rủi ro và chiến lược (dựa vào Beta).
        3. Đưa ra Khuyến nghị Hành động cụ thể dựa trên tỷ trọng Markowitz.
        4. Trình bày đẹp bằng Markdown, dùng emoji chuyên nghiệp. Đừng lặp lại nguyên văn số liệu, hãy biến nó thành lời khuyên.
        """
        
        llm_advice = call_llm(prompt, ai_config)
        if llm_advice and not llm_advice.startswith("Lỗi gọi API"):
            return llm_advice
        elif llm_advice:
            fallback_prefix = f"⚠️ **{llm_advice}**. Đang sử dụng khuyến nghị mặc định.\n\n"
        else:
            fallback_prefix = "⚠️ **Lỗi kết nối AI**. Đang sử dụng khuyến nghị mặc định.\n\n"
    else:
        fallback_prefix = ""
        
    # --- FALLBACK: Rules-based generation ---
    advice = []
    
    if trend_coef > 0:
        strategy = "Thị trường đang trong xu hướng tăng. Nên ưu tiên nắm giữ các cổ phiếu Năng động ($\\beta > 1$) để tối đa hóa lợi nhuận theo đà tăng của thị trường."
    else:
        strategy = "Thị trường đang trong xu hướng giảm hoặc đi ngang. Nên phòng thủ, ưu tiên các cổ phiếu Thụ động ($\\beta < 1$) hoặc chuyển sang tiền mặt."
        
    advice.append(f"### 📈 Xu hướng Thị trường: **{market_trend} (Bullish/Bearish)**")
    advice.append(strategy)
    
    if high_beta:
        advice.append(f"*   **Nhóm Tấn công ($\\beta > 1$):** `{', '.join(high_beta)}` - Phù hợp khi dự báo thị trường tiếp tục Tăng.")
    if low_beta:
        advice.append(f"*   **Nhóm Phòng thủ ($\\beta < 1$):** `{', '.join(low_beta)}` - Phù hợp khi dự báo thị trường Giảm hoặc Biến động mạnh.")

    if opt_res.get('warning'):
        advice.append(f"⚠️ **Cảnh báo:** {opt_res['warning']}")
        
    advice.append("### 💡 Khuyến nghị Hành động (Dành cho bạn)")
    if top_picks:
        advice.append(f"Để tối ưu hóa Tỷ suất Sinh lời / Rủi ro (theo tiêu chuẩn của các Quỹ đầu tư), bạn nên cân nhắc giải ngân phần lớn vốn vào: {', '.join(top_picks)}.")
    else:
        advice.append("Hiện tại các cổ phiếu trong danh mục có rủi ro cao, tỷ trọng tối ưu phân bổ khá đều hoặc rủi ro, cân nhắc giữ tiền mặt.")
        
    final_advice = "\n\n".join(advice)
    return fallback_prefix + final_advice

