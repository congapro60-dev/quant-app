import pandas as pd
import statsmodels.api as sm
import numpy as np

def parse_and_execute_command(command, data_df):
    """
    Parses an Eviews-like command (e.g., 'LS Y C X1 X2') and executes it on the given DataFrame.
    Returns a dictionary with the results or an error message.
    """
    command = command.strip()
    if not command:
        return {"error": "Lệnh trống."}
        
    parts = command.split()
    cmd_type = parts[0].upper()
    
    # Create a mapping for case-insensitive column lookup
    # e.g., 'y': 'Y', 'vnindex': 'VNINDEX'
    col_map = {c.upper(): c for c in data_df.columns}
    
    if cmd_type in ['LS', 'OLS']:
        if len(parts) < 3:
            return {"error": "Lệnh LS cần ít nhất 1 biến phụ thuộc và 1 biến độc lập. Ví dụ: LS Y C X"}
            
        dependent_var_input = parts[1].upper()
        independent_vars_input = [v.upper() for v in parts[2:]]
        
        # Verify columns exist
        if dependent_var_input not in col_map:
            return {"error": f"Không tìm thấy biến phụ thuộc '{parts[1]}' trong dữ liệu."}
            
        dependent_var = col_map[dependent_var_input]
        
        if dependent_var_input in independent_vars_input:
            return {"error": f"Biến phụ thuộc '{parts[1]}' không được xuất hiện trong danh sách biến độc lập."}
            
        X_data = pd.DataFrame(index=data_df.index)
        for var_input, orig_input in zip(independent_vars_input, parts[2:]):
            if var_input == 'C':
                X_data['C'] = 1.0 # Constant
            elif var_input in col_map:
                X_data[col_map[var_input]] = data_df[col_map[var_input]]
            else:
                return {"error": f"Không tìm thấy biến độc lập '{orig_input}' trong dữ liệu."}
                
        # Drop NaN values for regression
        temp_df = pd.concat([data_df[dependent_var], X_data], axis=1).dropna()
        y = temp_df[dependent_var]
        
        # Prevent issues with duplicate columns if user types something like LS Y C X X
        X = temp_df.loc[:, ~temp_df.columns.duplicated()]
        
        # Remove dependent variable from X to be absolutely sure, though we already checked
        X_vars_only = [c for c in X.columns if c != dependent_var]
        X = X[X_vars_only]
        
        # Convert C column name for statsmodels compatibility if it exists
        if 'C' in X.columns:
            X = X.rename(columns={'C': 'const'})
            
        try:
            model = sm.OLS(y, X)
            results = model.fit()
            return {"success": True, "results": results, "dep_var": dependent_var, "nobs": len(y)}
        except Exception as e:
            return {"error": f"Lỗi khi chạy hồi quy: {str(e)}"}
            
    elif cmd_type == 'GENR':
        # Simple implementation for GENR Z = X + Y
        try:
            expr = " ".join(parts[1:])
            var_name, formula = expr.split('=')
            var_name = var_name.strip()
            formula = formula.strip()
            
            # Use a copy to avoid in-place modification if eval fails
            new_df = data_df.copy()
            new_df[var_name] = new_df.eval(formula)
            return {"success": True, "message": f"Đã tạo/cập nhật biến '{var_name}' thành công.", "data": new_df}
        except Exception as e:
            return {"error": f"Lỗi khi tính toán biến mới: {str(e)}"}
            
    else:
        return {"error": f"Lệnh '{cmd_type}' chưa được hỗ trợ trong phiên bản này. Vui lòng thử 'LS' hoặc 'GENR'."}

def format_eviews_output(res_dict):
    """
    Formats the statsmodels results into an Eviews-like HTML/Markdown table in Vietnamese.
    """
    if "error" in res_dict:
        return f"<div style='color:red;'><b>Lỗi:</b> {res_dict['error']}</div>"
        
    if "message" in res_dict:
        return f"<div style='color:green;'><b>Thành công:</b> {res_dict['message']}</div>"
        
    results = res_dict["results"]
    dep_var = res_dict["dep_var"]
    nobs = res_dict["nobs"]
    
    # Extract metrics
    r_squared = results.rsquared
    adj_r_squared = results.rsquared_adj
    f_stat = results.fvalue
    f_pvalue = results.f_pvalue
    log_likelihood = results.llf
    aic = results.aic
    bic = results.bic
    
    # Calculate some metrics manually if statsmodels doesn't provide them directly as properties
    ssr = results.ssr # Sum squared resid
    se_regression = np.sqrt(ssr / results.df_resid) if results.df_resid > 0 else np.nan
    mean_dep = results.model.endog.mean()
    sd_dep = results.model.endog.std(ddof=1) # Eviews uses ddof=1 (sample standard deviation)
    
    # Durbin-Watson
    from statsmodels.stats.stattools import durbin_watson
    dw_stat = durbin_watson(results.resid)
    
    # Construct coefficient table
    coef_df = pd.DataFrame({
        'Hệ số (Coefficient)': results.params,
        'Sai số chuẩn (Std. Error)': results.bse,
        'Thống kê t (t-Statistic)': results.tvalues,
        'Xác suất (Prob.)': results.pvalues
    })
    
    # Change 'const' back to 'C' for display
    if 'const' in coef_df.index:
        coef_df = coef_df.rename(index={'const': 'C'})
        
    # Build HTML string matching Eviews style
    html = f"""
    <div style="font-family: monospace; font-size: 14px; background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
        <p style="margin:2px 0;"><b>Biến phụ thuộc (Dependent Variable):</b> {dep_var}</p>
        <p style="margin:2px 0;"><b>Phương pháp (Method):</b> Bình phương nhỏ nhất (Least Squares)</p>
        <p style="margin:2px 0;"><b>Số quan sát (Included observations):</b> {nobs}</p>
        <hr style="border-top: 1px solid #bbb; margin: 10px 0;">
    """
    
    # Add coefficient table
    html += coef_df.to_html(float_format=lambda x: f"{x:.6f}", border=0, classes="table table-sm")
    
    # Add bottom statistics
    html += f"""
        <hr style="border-top: 1px solid #bbb; margin: 10px 0;">
        <table style="width: 100%; font-size: 14px;">
            <tr>
                <td style="width: 50%;"><b>R-bình phương (R-squared)</b></td><td style="width: 15%;">{r_squared:.6f}</td>
                <td style="width: 50%;"><b>TB biến phụ thuộc (Mean dependent var)</b></td><td>{mean_dep:.6f}</td>
            </tr>
            <tr>
                <td><b>R-bình phương hiệu chỉnh (Adjusted R-squared)</b></td><td>{adj_r_squared:.6f}</td>
                <td><b>Độ lệch chuẩn biến PT (S.D. dependent var)</b></td><td>{sd_dep:.6f}</td>
            </tr>
            <tr>
                <td><b>Sai số chuẩn hồi quy (S.E. of regression)</b></td><td>{se_regression:.6f}</td>
                <td><b>Tiêu chuẩn Akaike (Akaike info criterion)</b></td><td>{aic:.6f}</td>
            </tr>
            <tr>
                <td><b>Tổng bình phương phần dư (Sum squared resid)</b></td><td>{ssr:.6f}</td>
                <td><b>Tiêu chuẩn Schwarz (Schwarz criterion)</b></td><td>{bic:.6f}</td>
            </tr>
            <tr>
                <td><b>Log likelihood</b></td><td>{log_likelihood:.6f}</td>
                <td><b>Thống kê F (F-statistic)</b></td><td>{f_stat:.6f}</td>
            </tr>
            <tr>
                <td><b>Thống kê Durbin-Watson</b></td><td>{dw_stat:.6f}</td>
                <td><b>Xác suất (Prob(F-statistic))</b></td><td>{f_pvalue:.6f}</td>
            </tr>
        </table>
    </div>
    """
    return html
