import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from data_loader import fetch_data, calculate_returns
from analytics import run_sim, run_diagnostics, markowitz_optimization, generate_expert_advice

# Set page config
st.set_page_config(page_title="Quantitative Trading App", layout="wide")

st.title("Phần mềm Phân tích Thị trường & Tối ưu Danh mục")
st.markdown("Dựa trên Mô hình Chỉ số đơn (SIM) và Markowitz - Dữ liệu vnstock")

# Initialize session state for main tabs if not exists
if 'prices_df' not in st.session_state:
    st.session_state.prices_df = pd.DataFrame()
if 'opt_res' not in st.session_state:
    st.session_state.opt_res = {}
if 'sim_results_list' not in st.session_state:
    st.session_state.sim_results_list = []
if 'returns_df' not in st.session_state:
    st.session_state.returns_df = pd.DataFrame()
if 'market_ticker' not in st.session_state:
    st.session_state.market_ticker = ""

# --- Sidebar Inputs ---
st.sidebar.header("Tham số đầu vào")
tickers_input = st.sidebar.text_input("Mã cổ phiếu (ngăn cách bằng dấu phẩy):", "FPT, HPG, CTG, DPM")
index_input = st.sidebar.text_input("Chỉ số thị trường:", "VNINDEX")

end_date = datetime.today()
start_date = end_date - timedelta(days=365)
start_date_input = st.sidebar.date_input("Từ ngày:", start_date)
end_date_input = st.sidebar.date_input("Đến ngày:", end_date)

st.sidebar.markdown("---")
st.sidebar.header("Tích hợp AI (Tùy chọn)")
ai_provider = st.sidebar.selectbox("Chọn nhà cung cấp AI:", ["Không dùng", "Anthropic (Claude)", "Google (Gemini)"])
ai_config = None

if ai_provider != "Không dùng":
    api_key = st.sidebar.text_input("API Key:", type="password")
    
    if ai_provider == "Anthropic (Claude)":
        model_choice = st.sidebar.selectbox("Chọn Model:", ["claude-sonnet-5", "claude-fable-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"])
    else:
        model_choice = st.sidebar.selectbox("Chọn Model:", ["gemini-3.6-flash", "gemini-3.1-pro", "gemini-3.5-flash", "gemini-3.1-flash-lite"])
        
    ai_config = {
        'provider': ai_provider,
        'model': model_choice,
        'api_key': api_key
    }

if st.sidebar.button("Phân tích"):
    # Parse inputs
    asset_tickers = [x.strip().upper() for x in tickers_input.split(',')]
    market_ticker = index_input.strip().upper()
    all_tickers = asset_tickers + [market_ticker]
    
    with st.spinner('Đang tải dữ liệu từ vnstock...'):
        prices_df = fetch_data(all_tickers, start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d'))
        
    if prices_df.empty or market_ticker not in prices_df.columns:
        st.error("Không thể tải dữ liệu chỉ số thị trường. Vui lòng kiểm tra lại kết nối mạng hoặc mã chỉ số.")
    else:
        # Check for failed tickers
        valid_assets = [t for t in asset_tickers if t in prices_df.columns]
        failed_assets = [t for t in asset_tickers if t not in prices_df.columns]
        
        if failed_assets:
            st.warning(f"Không thể tải dữ liệu cho các mã: {', '.join(failed_assets)}")
            
        if not valid_assets:
            st.error("Tất cả các mã cổ phiếu đều không tải được dữ liệu.")
        else:
            # Calculate returns
            returns_df = calculate_returns(prices_df)
            market_returns = returns_df[market_ticker]
            asset_returns_df = returns_df[valid_assets]
            
            sim_results_list = []
            for ticker in valid_assets:
                sim_res = run_sim(asset_returns_df[ticker], market_returns)
                diag_res = run_diagnostics(sim_res)
                
                sim_results_list.append({
                    'Mã CP': ticker,
                    'Beta (Độ nhạy)': round(sim_res['beta'], 4),
                    'Alpha': round(sim_res['alpha'], 6),
                    'Rủi ro Hệ thống': round(sim_res['systematic_risk'], 6),
                    'Rủi ro Phi hệ thống': round(sim_res['unsystematic_risk'], 6),
                    'Tổng Rủi ro': round(sim_res['total_risk'], 6),
                    'R^2': round(sim_res['r_squared'], 4),
                    'Phương sai SS thay đổi (White)': diag_res['Heteroskedasticity'],
                    'Tự tương quan (B-G)': diag_res['Autocorrelation']
                })
                
            opt_res = markowitz_optimization(asset_returns_df)
            
            # Save to session state
            st.session_state.prices_df = prices_df
            st.session_state.returns_df = returns_df
            st.session_state.sim_results_list = sim_results_list
            st.session_state.opt_res = opt_res
            st.session_state.market_ticker = market_ticker
            st.session_state.valid_assets = valid_assets

# --- RENDER UI FROM SESSION STATE ---
if not st.session_state.prices_df.empty and st.session_state.market_ticker:
    returns_df = st.session_state.returns_df
    market_ticker = st.session_state.market_ticker
    sim_results_list = st.session_state.sim_results_list
    opt_res = st.session_state.opt_res
    valid_assets = st.session_state.valid_assets
    prices_df = st.session_state.prices_df
    
    # --- TAB 1: Mô hình SIM & Rủi ro ---
    st.header("1. Phân tích Rủi ro theo Mô hình SIM")
    
    sim_df = pd.DataFrame(sim_results_list)
    st.dataframe(sim_df)
    
    # --- Giải thích các chỉ số ---
    st.info("""
    **📚 Giải thích ý nghĩa các chỉ số Kinh tế lượng:**
    *   **Beta (Độ nhạy - $\\beta$):** Đo lường mức độ biến động của cổ phiếu so với thị trường. 
        *   $\\beta > 1$: Cổ phiếu *năng động*, biến động mạnh hơn thị trường (Rủi ro cao, lợi nhuận kỳ vọng cao).
        *   $\\beta < 1$: Cổ phiếu *thụ động*, biến động ít hơn thị trường (An toàn hơn).
    *   **Alpha ($\\alpha$):** Lợi suất "vượt trội" do yếu tố riêng của cổ phiếu, không phụ thuộc vào thị trường.
    *   **Rủi ro Hệ thống:** Rủi ro do biến động chung của thị trường gây ra (không thể loại trừ bằng cách đa dạng hóa).
    *   **Rủi ro Phi hệ thống:** Rủi ro do đặc thù riêng của công ty gây ra (có thể loại bỏ bằng cách mua nhiều mã cổ phiếu khác nhau).
    *   **R-squared ($R^2$):** Hệ số xác định. Ví dụ $R^2 = 0.45$ nghĩa là 45% sự thay đổi giá của cổ phiếu được giải thích bởi sự thay đổi của VNINDEX.
    *   **Phương sai SS thay đổi (White Test):** Nếu 'Yes', mô hình có phương sai sai số thay đổi, các khoảng tin cậy và kiểm định có thể bị sai lệch. Cần khắc phục (ví dụ: dùng sai số chuẩn vững).
    *   **Tự tương quan (Breusch-Godfrey Test):** Nếu 'Yes', có sự phụ thuộc chuỗi (giá hôm nay phụ thuộc giá hôm qua quá nhiều), khiến ước lượng phương sai bị chệch.
    """)
    
    # Biểu đồ Scatter (SIM Regression)
    st.subheader("Biểu đồ Hồi quy SIM")
    selected_ticker = st.selectbox("Chọn cổ phiếu để xem biểu đồ hồi quy:", valid_assets)
    if selected_ticker in returns_df.columns:
        fig = px.scatter(returns_df, x=market_ticker, y=selected_ticker, trendline="ols", 
                         title=f"Hồi quy {selected_ticker} theo {market_ticker}",
                         labels={market_ticker: f"Lợi suất {market_ticker}", selected_ticker: f"Lợi suất {selected_ticker}"})
        st.plotly_chart(fig, use_container_width=True)

    # --- TAB 2: Tối ưu Danh mục Markowitz ---
    st.header("2. Tối ưu hóa Danh mục Đầu tư (Markowitz)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Danh mục An toàn nhất (Min Volatility)")
        min_vol_df = pd.DataFrame({'Tài sản': opt_res['assets'], 'Tỷ trọng': opt_res['min_vol_weights']})
        fig_min_vol = px.pie(min_vol_df, values='Tỷ trọng', names='Tài sản', title="Phân bổ Vốn - Rủi ro Thấp nhất")
        st.plotly_chart(fig_min_vol, use_container_width=True)
        
    with col2:
        st.subheader("Danh mục Hiệu quả nhất (Max Sharpe Ratio)")
        max_sharpe_df = pd.DataFrame({'Tài sản': opt_res['assets'], 'Tỷ trọng': opt_res['max_sharpe_weights']})
        fig_max_sharpe = px.pie(max_sharpe_df, values='Tỷ trọng', names='Tài sản', title="Phân bổ Vốn - Sharpe lớn nhất")
        st.plotly_chart(fig_max_sharpe, use_container_width=True)
        
    # Efficient Frontier Chart
    st.subheader("Biểu đồ Tập danh mục Biên duyên (Efficient Frontier)")
    ef_fig = go.Figure()
    ef_fig.add_trace(go.Scatter(x=opt_res['ef_vols'], y=opt_res['ef_rets'], mode='markers',
                                marker=dict(color=opt_res['ef_sharpes'], colorscale='Viridis', showscale=True, size=5),
                                name='Các danh mục ngẫu nhiên'))
    ef_fig.update_layout(title='Efficient Frontier (Mô phỏng 500 danh mục ngẫu nhiên)',
                         xaxis_title='Rủi ro (Độ lệch chuẩn - Annualized Volatility)',
                         yaxis_title='Lợi suất kỳ vọng (Annualized Return)')
    st.plotly_chart(ef_fig, use_container_width=True)
        
    # --- TAB 3: Chuyên gia Khuyến nghị ---
    st.header("3. 🤖 Chuyên gia Đầu tư Khuyến nghị")
    
    if ai_config and ai_config.get('api_key'):
        with st.spinner(f"Đang chờ {ai_provider} sinh phân tích..."):
            expert_advice = generate_expert_advice(sim_results_list, opt_res, prices_df[market_ticker], ai_config)
            st.success(expert_advice)
    else:
        expert_advice = generate_expert_advice(sim_results_list, opt_res, prices_df[market_ticker])
        st.success(expert_advice)
        
# --- TAB 4: Eviews Giả lập ---
st.markdown("---")
st.header("4. 📊 Eviews Tiếng Việt (Giả lập)")
st.markdown("Thực hành gõ lệnh Kinh tế lượng y hệt phần mềm Eviews nhưng bằng giao diện tiếng Việt.")

col_ev1, col_ev2 = st.columns([1, 2])

with col_ev1:
    st.subheader("Workfile (Dữ liệu)")
    uploaded_file = st.file_uploader("Tải lên file số liệu (CSV/Excel)", type=["csv", "xlsx", "xls"])
    
    # Initialize session state for Eviews data if not exists
    if 'eviews_data' not in st.session_state:
        st.session_state.eviews_data = pd.DataFrame()
        
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                st.session_state.eviews_data = pd.read_csv(uploaded_file)
            else:
                st.session_state.eviews_data = pd.read_excel(uploaded_file)
            st.success("Tải dữ liệu thành công!")
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")
            
    if not st.session_state.eviews_data.empty:
        st.write("Các biến trong bộ nhớ:")
        st.write(st.session_state.eviews_data.columns.tolist())
        with st.expander("Xem trước dữ liệu"):
            st.dataframe(st.session_state.eviews_data.head())
    else:
        st.info("Vui lòng tải lên file số liệu (ví dụ YWKM.xlsx) để bắt đầu.")

with col_ev2:
    st.subheader("Command Window (Cửa sổ Lệnh)")
    from eviews_emulator import parse_and_execute_command, format_eviews_output
    
    command_input = st.text_input("Nhập lệnh Eviews (VD: LS Y C X1 X2, GENR Z = X1 + X2):", key="eviews_cmd")
    
    if st.button("Chạy lệnh (Enter)"):
        if st.session_state.eviews_data.empty:
            st.warning("Vui lòng tải dữ liệu vào Workfile trước khi chạy lệnh.")
        elif not command_input:
            st.warning("Vui lòng nhập lệnh.")
        else:
            with st.spinner("Đang xử lý..."):
                res = parse_and_execute_command(command_input, st.session_state.eviews_data)
                
                if "data" in res:
                    st.session_state.eviews_data = res["data"] # Update memory (e.g. after GENR)
                
                # Output Window
                st.subheader("Output (Kết quả)")
                html_output = format_eviews_output(res)
                st.components.v1.html(html_output, height=450, scrolling=True)
# --- TAB 5: Công cụ Ôn thi (Exam Calculator) ---
st.markdown("---")
st.header("5. 🎓 Công cụ Ôn thi Kinh tế lượng")
st.markdown("Tính toán nhanh các đại lượng để phục vụ làm bài kiểm tra thực hành.")

from exam_calculator import (
    calc_return_formula, calc_returns_data,
    calc_sim_risks_formula, calc_sim_risks_data,
    calc_cov_matrix_formula, calc_cov_matrix_data,
    calc_markowitz_params_formula, calc_markowitz_params_data
)

if st.session_state.get('eviews_data') is None or st.session_state.eviews_data.empty:
    st.info("Vui lòng tải lên file số liệu ở Tab 4 (Eviews Giả lập) để sử dụng công cụ tính nhanh.")
else:
    exam_data = st.session_state.eviews_data
    st.write("Dữ liệu hiện tại:", exam_data.head())
    
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        selected_asset = st.selectbox("Chọn Mã Cổ phiếu (Asset):", exam_data.columns)
    with col_ex2:
        selected_market = st.selectbox("Chọn Chỉ số Thị trường (Market):", exam_data.columns, index=min(1, len(exam_data.columns)-1))

    st.subheader("Các lệnh tính nhanh")
    
    # 1. Tính Lợi suất
    if st.button("1. Tính Tỷ suất Sinh lời (Return)"):
        st.latex(calc_return_formula())
        try:
            ret = calc_returns_data(exam_data[selected_asset])
            st.write(f"Kết quả Lợi suất của **{selected_asset}** (5 ngày đầu):")
            st.dataframe(ret.head())
        except Exception as e:
            st.error(f"Lỗi: {e}. Vui lòng đảm bảo cột dữ liệu là dạng số hợp lệ.")
            
    # 2. Rủi ro Hệ thống / Phi hệ thống
    if st.button("2. Tính Rủi ro Hệ thống / Phi hệ thống (SIM)"):
        st.latex(calc_sim_risks_formula())
        try:
            # Need returns for SIM
            r_asset = calc_returns_data(exam_data[selected_asset])
            r_market = calc_returns_data(exam_data[selected_market])
            risks = calc_sim_risks_data(r_asset, r_market)
            
            st.write(f"Kết quả cho cổ phiếu **{selected_asset}** so với **{selected_market}**:")
            st.json({k: float(v) for k, v in risks.items()})
        except Exception as e:
            st.error(f"Lỗi: {e}")
            
    # 3. Ma trận Hiệp phương sai
    if st.button("3. Tính Ma trận Hiệp phương sai (V)"):
        st.latex(calc_cov_matrix_formula())
        try:
            # Select numeric columns only and calculate returns
            numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
            returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
            
            st.write("Kết quả (Ma trận Hiệp phương sai của tỷ suất sinh lời):")
            st.dataframe(calc_cov_matrix_data(returns_all))
        except Exception as e:
            st.error(f"Lỗi: {e}")
            
    # 4. Các đại lượng Markowitz (A, B, C, D)
    if st.button("4. Tính các đại lượng Markowitz (A, B, C, D)"):
        st.latex(calc_markowitz_params_formula())
        try:
            numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
            returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
            params = calc_markowitz_params_data(returns_all)
            st.write("Kết quả cấu trúc ma trận (dành cho toàn bộ các biến số liệu):")
            st.json({k: float(v) if not isinstance(v, str) else v for k, v in params.items()})
        except Exception as e:
            st.error(f"Lỗi: {e}")
