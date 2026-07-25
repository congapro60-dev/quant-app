import pandas as pd
import numpy as np
import statsmodels.api as sm

def calc_return_formula():
    return r"""
    \text{Lợi suất (Return) của tài sản tại thời điểm } t: \\
    r_t = \ln\left(\frac{S_t}{S_{t-1}}\right)
    """

def calc_returns_data(prices_series):
    # Log return formula as in the PDF: ln(St / St-1)
    safe = prices_series.copy().where(prices_series > 0)  # zero/negative -> NaN
    returns = np.log(safe / safe.shift(1)).dropna()
    return returns

def calc_sim_risks_formula():
    return r"""
    \text{Từ mô hình SIM: } r_i = \gamma_i + \beta_i r_I + \varepsilon_i \\
    \text{Rủi ro hệ thống: } \sigma_{sys}^2 = \beta_i^2 \sigma_I^2 \\
    \text{Rủi ro phi hệ thống: } \sigma_{unsys}^2 = \eta_i^2 = Var(\varepsilon_i) \\
    \text{Tổng rủi ro: } \sigma_i^2 = \beta_i^2 \sigma_I^2 + \eta_i^2
    """

def calc_sim_risks_data(asset_returns, market_returns):
    df = pd.concat([asset_returns, market_returns], axis=1).dropna()
    y = df.iloc[:, 0]
    X = df.iloc[:, 1]
    X_const = sm.add_constant(X)
    
    model = sm.OLS(y, X_const).fit()
    beta = model.params.iloc[1]
    
    market_var = X.var()
    sys_risk = (beta ** 2) * market_var
    unsys_risk = model.resid.var()
    total_risk = y.var()
    
    return {
        'Beta': beta,
        'Sys_Risk': sys_risk,
        'Unsys_Risk': unsys_risk,
        'Total_Risk': total_risk,
        'Market_Var': market_var
    }

def calc_cov_matrix_formula():
    return r"""
    \text{Ma trận Hiệp phương sai } V = [cov(r_i, r_j)] \\
    \text{Trong đó: } cov(r_i, r_j) = \frac{\sum (r_i - \bar{r}_i)(r_j - \bar{r}_j)}{n-1}
    """

def calc_cov_matrix_data(returns_df):
    return returns_df.cov()

def calc_markowitz_params_formula():
    return r"""
    \text{Các đại lượng trong cấu trúc ma trận của Markowitz (Biên duyên):} \\
    A = [1]^T V^{-1} [1] \\
    B = [\bar{r}]^T V^{-1} [\bar{r}] \\
    C = [\bar{r}]^T V^{-1} [1] \\
    D = A \cdot B - C^2 \\
    \text{Với } V^{-1} \text{ là ma trận nghịch đảo của ma trận hiệp phương sai, } [1] \text{ là vector cột các số 1, } [\bar{r}] \text{ là vector lợi suất kỳ vọng.}
    """

def calc_markowitz_params_data(returns_df):
    cov_matrix = returns_df.cov().values
    mean_returns = returns_df.mean().values
    num_assets = len(mean_returns)
    
    try:
        inv_cov_matrix = np.linalg.inv(cov_matrix)
    except np.linalg.LinAlgError:
        return {"error": "Ma trận hiệp phương sai bị suy biến (không thể tìm ma trận nghịch đảo)."}
        
    ones = np.ones(num_assets)
    
    # Calculate A, B, C, D based on the specific PDF formulas:
    # A = [1]' V^-1 [1]
    A = ones.T @ inv_cov_matrix @ ones
    
    # B = [r]' V^-1 [r]  -> where [r] is the expected return vector
    B = mean_returns.T @ inv_cov_matrix @ mean_returns
    
    # C = [\bar{r}] V^-1 [1]  -> Note in the PDF transcript: C = [\bar{r}] V^-1 [1] and B = [r]' V^-1 [r]. 
    # Actually wait. Standard math convention: A=1'V^-1 1, B=mu'V^-1 1, C=mu'V^-1 mu. 
    # Let's strictly follow the extracted text from PDF:
    # [1]'V^-1[1] = A
    # [r]'V^-1[r] = B
    # [\bar{r}]V^-1[1] = C
    C = mean_returns.T @ inv_cov_matrix @ ones
    
    # D = AC - B^2
    D = A * B - C**2 # Note: depending on the exact PDF text it was AC - B^2, but standard is AB - C^2. Wait, if B=r'V^-1 r and C=r'V^-1 1, then AC-B^2 is dimensionally wrong? No, A,B,C are scalars. 
    # Actually, standard is A=1'V^-1 1, B=\mu'V^-1 \mu, C=1'V^-1 \mu, D=AB-C^2. 
    # The PDF states: D = AC - B^2 (where B is the cross term). Let's provide the values of A, B, C, and the determinant-like variable D.
    # To be safe and avoid confusion, let's output the matrix multiplications explicitly.
    
    val_1_V_1 = ones.T @ inv_cov_matrix @ ones
    val_r_V_r = mean_returns.T @ inv_cov_matrix @ mean_returns
    val_r_V_1 = mean_returns.T @ inv_cov_matrix @ ones
    
    # Based on PDF: A = 1'V^-1 1, B = r'V^-1 r, C = r'V^-1 1, D = AC - B^2
    # But usually the denominator is D = (1'V^-1 1)(r'V^-1 r) - (1'V^-1 r)^2. 
    # So D = A(1'V^-1 1) * B(r'V^-1 r) - C(r'V^-1 1)^2.
    # We will output all combinations so the user has exactly what they need regardless of naming mix-ups in the PDF.
    
    return {
        '1^T * V^-1 * 1 (A hoặc C tùy tài liệu)': val_1_V_1,
        'r^T * V^-1 * r (B hoặc A tùy tài liệu)': val_r_V_r,
        'r^T * V^-1 * 1 (C hoặc B tùy tài liệu)': val_r_V_1,
        'Định thức D = (1^T V^-1 1)(r^T V^-1 r) - (r^T V^-1 1)^2': (val_1_V_1 * val_r_V_r) - (val_r_V_1 ** 2)
    }
