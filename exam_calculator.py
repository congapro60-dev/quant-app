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
    # Ký hiệu bám giáo trình môn học: A = [1]'V⁻¹[1], B là số hạng chéo
    # [r̄]'V⁻¹[1], C = [r̄]'V⁻¹[r̄], và D = A·C − B². Nhiều tài liệu khác hoán
    # đổi vai trò B và C; ở đây theo giáo trình vì sinh viên đối chiếu bài làm
    # với chính giáo trình đó. Giá trị số không đổi, chỉ tên gọi khác.
    return r"""
    \text{Các đại lượng trong cấu trúc ma trận của Markowitz (Biên duyên):} \\
    A = [1]^T V^{-1} [1] \\
    B = [\bar{r}]^T V^{-1} [1] \quad \text{(số hạng chéo)} \\
    C = [\bar{r}]^T V^{-1} [\bar{r}] \\
    D = A \cdot C - B^2 \\
    \text{Phương sai danh mục biên duyên: } \sigma_P^2(\bar{r}_P) = \frac{A\bar{r}_P^2 - 2B\bar{r}_P + C}{D} \\
    \text{Với } V^{-1} \text{ là ma trận nghịch đảo của ma trận hiệp phương sai, } [1] \text{ là vector cột các số 1, } [\bar{r}] \text{ là vector lợi suất kỳ vọng.} \\
    \text{Lưu ý: một số tài liệu khác đổi vai trò } B \text{ và } C; \text{ hãy bám ký hiệu của giáo trình đang dùng.}
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

    # Ba tích ma trận gốc. Đặt tên theo đúng phép tính chứ không theo chữ cái,
    # để không phụ thuộc quy ước đặt tên của bất kỳ tài liệu nào.
    val_1_V_1 = ones.T @ inv_cov_matrix @ ones            # [1]' V^-1 [1]
    val_r_V_1 = mean_returns.T @ inv_cov_matrix @ ones    # [r̄]' V^-1 [1]  (chéo)
    val_r_V_r = mean_returns.T @ inv_cov_matrix @ mean_returns  # [r̄]' V^-1 [r̄]

    # Ký hiệu theo giáo trình môn học:
    #   A = [1]'V^-1[1] ; B = [r̄]'V^-1[1] ; C = [r̄]'V^-1[r̄] ; D = A*C - B^2
    # Định thức D là cùng một số dù tài liệu gọi tên chữ cái thế nào, vì nó luôn
    # bằng (1'V^-1 1)(r̄'V^-1 r̄) trừ đi bình phương số hạng chéo.
    A = val_1_V_1
    B = val_r_V_1
    C = val_r_V_r
    D = A * C - B ** 2

    return {
        'A = [1]ᵀ V⁻¹ [1]': A,
        'B = [r̄]ᵀ V⁻¹ [1]  (số hạng chéo)': B,
        'C = [r̄]ᵀ V⁻¹ [r̄]': C,
        'D = A·C − B² (định thức)': D,
    }
