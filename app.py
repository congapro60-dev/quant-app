import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from data_loader import fetch_data, calculate_returns
from analytics import run_sim, run_diagnostics, markowitz_optimization, generate_expert_advice, call_llm
from statsmodels.stats.stattools import durbin_watson
import data_cleaner as dc
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ==================== CẤU HÌNH TRANG ====================
st.set_page_config(page_title="Quant App - Phân tích Thị trường", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stMetric"] {
        background-color: #1A1F2B; border: 1px solid #2A3140;
        border-radius: 12px; padding: 14px 16px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1F2B; border-radius: 8px 8px 0 0; padding: 10px 16px;
    }
    .stTabs [aria-selected="true"] { background-color: #00A67E; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Phần mềm Phân tích Thị trường & Tối ưu Danh mục")
st.caption("Mô hình Chỉ số đơn (SIM) • Markowitz • Eviews tiếng Việt • Dữ liệu vnstock")

# ==================== KHỞI TẠO SESSION STATE ====================
for k, v in {
    'prices_df': pd.DataFrame(), 'opt_res': {}, 'sim_results_list': [],
    'returns_df': pd.DataFrame(), 'market_ticker': "", 'valid_assets': [],
    'tickers_val': "FPT, HPG, CTG, DPM", 'eviews_data': pd.DataFrame(),
    'last_query': None, 'last_update': None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("⚙️ Tham số đầu vào")

    st.caption("Chọn nhanh danh mục mẫu:")
    p1, p2 = st.columns(2)
    p3, p4 = st.columns(2)
    if p1.button("Ngân hàng", use_container_width=True):
        st.session_state.tickers_val = "CTG, VCB, BID, MBB"; st.rerun()
    if p2.button("VN30 lớn", use_container_width=True):
        st.session_state.tickers_val = "FPT, HPG, VNM, MWG"; st.rerun()
    if p3.button("Bất động sản", use_container_width=True):
        st.session_state.tickers_val = "VHM, VIC, NVL, PDR"; st.rerun()
    if p4.button("Bài thực tập", use_container_width=True):
        st.session_state.tickers_val = "BID, BVH, CTG"; st.rerun()

    with st.form("input_form"):
        tickers_input = st.text_input("Mã cổ phiếu (cách nhau bằng dấu phẩy):",
                                      key="tickers_val")
        index_input = st.text_input("Chỉ số thị trường:", "VNINDEX")
        c1, c2 = st.columns(2)
        end_date = datetime.today()
        start_date = end_date - timedelta(days=365)
        start_date_input = c1.date_input("Từ ngày:", start_date)
        end_date_input = c2.date_input("Đến ngày:", end_date)
        submitted = st.form_submit_button("🚀 Phân tích", use_container_width=True, type="primary")

    st.markdown("---")
    st.header("🔄 Real-time")
    live_mode = st.toggle("Tự động cập nhật dữ liệu", value=False,
                          help="Định kỳ tải lại dữ liệu từ vnstock và tính lại phân tích.")
    refresh_min = st.selectbox("Chu kỳ làm mới (phút):", [1, 5, 15], index=1, disabled=not live_mode)
    if live_mode and st_autorefresh is None:
        st.caption("⚠️ Thiếu gói streamlit-autorefresh nên chưa tự làm mới được.")

    st.markdown("---")
    st.header("🤖 Tích hợp AI (Tùy chọn)")
    ai_provider = st.selectbox("Nhà cung cấp AI:", ["Không dùng", "Anthropic (Claude)", "Google (Gemini)"])
    ai_config = None
    if ai_provider != "Không dùng":
        api_key = st.text_input("API Key:", type="password")
        if ai_provider == "Anthropic (Claude)":
            model_choice = st.selectbox("Model:", ["claude-sonnet-5", "claude-fable-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"])
        else:
            model_choice = st.selectbox("Model:", ["gemini-3.6-flash", "gemini-3.1-pro", "gemini-3.5-flash", "gemini-3.1-flash-lite"])
        ai_config = {'provider': ai_provider, 'model': model_choice, 'api_key': api_key}
        st.caption("🔒 API key chỉ lưu tạm trong phiên, không ghi vào code.")

# ==================== XỬ LÝ KHI BẤM PHÂN TÍCH ====================
def run_analysis(asset_tickers, market_ticker, start_str, end_str, show_msgs=True):
    asset_tickers = list(dict.fromkeys([t.strip().upper() for t in asset_tickers if t.strip()]))
    market_ticker = market_ticker.strip().upper()
    all_tickers = list(dict.fromkeys(asset_tickers + [market_ticker]))
    with st.spinner('Đang tải dữ liệu từ vnstock...'):
        prices_df = fetch_data(all_tickers, start_str, end_str)
    if prices_df.empty or market_ticker not in prices_df.columns:
        if show_msgs:
            st.error("❌ Không tải được dữ liệu chỉ số thị trường. Kiểm tra kết nối mạng hoặc mã chỉ số.")
        return
    valid_assets = [t for t in asset_tickers if t in prices_df.columns]
    failed_assets = [t for t in asset_tickers if t not in prices_df.columns]
    if failed_assets and show_msgs:
        st.warning(f"⚠️ Không tải được dữ liệu cho: {', '.join(failed_assets)}")
    if not valid_assets:
        if show_msgs:
            st.error("❌ Tất cả các mã cổ phiếu đều không tải được dữ liệu.")
        return
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
            'Tự tương quan (B-G)': diag_res['Autocorrelation'],
            'Dạng hàm (RESET)': diag_res.get('SpecificationError', 'N/A'),
            'Phân phối chuẩn (JB)': diag_res.get('Normality', 'N/A'),
        })
    opt_res = markowitz_optimization(asset_returns_df)
    st.session_state.prices_df = prices_df
    st.session_state.returns_df = returns_df
    st.session_state.sim_results_list = sim_results_list
    st.session_state.opt_res = opt_res
    st.session_state.market_ticker = market_ticker
    st.session_state.valid_assets = valid_assets
    st.session_state.last_query = (asset_tickers, market_ticker, start_str, end_str)
    st.session_state.last_update = datetime.now()


# Kích hoạt phân tích khi bấm nút
if submitted:
    run_analysis(tickers_input.split(','), index_input,
                 start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d'))

# Chế độ real-time: tự làm mới định kỳ và tính lại
st.session_state['_live_flag'] = bool(live_mode)
if live_mode and st_autorefresh is not None:
    st_autorefresh(interval=refresh_min * 60 * 1000, key="live_refresh")
    if st.session_state.get('last_query') and not submitted:
        run_analysis(*st.session_state['last_query'], show_msgs=False)

# ==================== CÁC TAB ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Rủi ro (SIM)", "🥧 Danh mục (Markowitz)", "🤖 Chuyên gia AI",
    "📈 Eviews tiếng Việt", "🎓 Ôn thi",
])

has_data = (not st.session_state.prices_df.empty) and bool(st.session_state.market_ticker)


def _download_df(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode('utf-8-sig'),
                       file_name=filename, mime="text/csv")


def render_live_prices():
    prices_df = st.session_state.prices_df
    tickers = st.session_state.valid_assets + [st.session_state.market_ticker]
    tickers = [t for t in tickers if t in prices_df.columns]
    lu = st.session_state.get('last_update')
    live_on = st.session_state.get('_live_flag', False)
    tag = "🟢 LIVE" if live_on else "🔵"
    if lu is not None:
        st.caption(f"{tag} Giá mới nhất — cập nhật lúc {lu.strftime('%H:%M:%S %d/%m/%Y')}")
    if not tickers:
        return
    cols = st.columns(len(tickers))
    for c, t in zip(cols, tickers):
        series = prices_df[t].dropna()
        if len(series) >= 2:
            cur, prev = series.iloc[-1], series.iloc[-2]
            pct = (cur / prev - 1) * 100 if prev else 0.0
            c.metric(t, f"{cur:,.2f}", f"{pct:+.2f}%")
        elif len(series) >= 1:
            c.metric(t, f"{series.iloc[-1]:,.2f}")


def interpret_regression_vn(res):
    m = res.get('results')
    if m is None:
        return None
    dep = res.get('dep_var', 'Y')
    r2 = float(getattr(m, 'rsquared', float('nan')))
    r2a = float(getattr(m, 'rsquared_adj', float('nan')))
    fp = getattr(m, 'f_pvalue', None)
    params, pvals = m.params, m.pvalues
    try:
        dw = float(durbin_watson(m.resid))
    except Exception:
        dw = None

    L = ["**1. Mức độ phù hợp của mô hình**"]
    L.append(f"- R² = **{r2:.4f}** → mô hình giải thích khoảng **{r2*100:.1f}%** biến động của **{dep}** "
             f"(R² hiệu chỉnh = {r2a:.4f}).")
    if fp is not None:
        if fp < 0.05:
            L.append(f"- Kiểm định F: p = {fp:.4g} < 0.05 → **mô hình có ý nghĩa tổng thể** (ít nhất một biến độc lập thực sự tác động).")
        else:
            L.append(f"- Kiểm định F: p = {fp:.4g} ≥ 0.05 → mô hình **chưa có ý nghĩa tổng thể**, nên cân nhắc đổi biến.")

    L.append("**2. Ý nghĩa các hệ số**")
    for name in params.index:
        coef, pv = float(params[name]), float(pvals[name])
        sig = "**có ý nghĩa** (p<0.05)" if pv < 0.05 else "không có ý nghĩa (p≥0.05)"
        if str(name).lower() in ('const', 'c'):
            L.append(f"- Hằng số (C): {coef:.4f}, p = {pv:.4g} → {sig}.")
        else:
            direction = "đồng biến" if coef > 0 else "nghịch biến"
            L.append(f"- **{name}**: hệ số = {coef:.4f} ({direction}), p = {pv:.4g} → {sig}. "
                     f"Khi {name} tăng 1 đơn vị, {dep} thay đổi {coef:+.4f} đơn vị (các yếu tố khác không đổi).")

    L.append("**3. Chẩn đoán mô hình**")
    if dw is not None:
        if dw < 1.5:
            dwt = "có dấu hiệu **tự tương quan dương** (phần dư liên hệ chuỗi)"
        elif dw > 2.5:
            dwt = "có dấu hiệu **tự tương quan âm**"
        else:
            dwt = "**không có tự tương quan** đáng kể"
        L.append(f"- Durbin-Watson = {dw:.3f} → {dwt}.")
    L.append("- Xem thêm Jarque-Bera (chuẩn tắc phần dư) và VIF (đa cộng tuyến) ở bảng kết quả phía trên.")

    nonconst = [n for n in params.index if str(n).lower() not in ('const', 'c')]
    if len(nonconst) == 1:
        b = float(params[nonconst[0]])
        if b > 1:
            cls = "**năng động** (β>1): biến động mạnh hơn thị trường — rủi ro & kỳ vọng cao."
        elif 0 < b < 1:
            cls = "**phòng thủ** (0<β<1): biến động yếu hơn thị trường — an toàn hơn."
        else:
            cls = "ngược chiều thị trường (β≤0): hiếm gặp, nên kiểm tra lại dữ liệu."
        L.append(f"**4. Góc nhìn SIM** — Beta = {b:.3f} → cổ phiếu thuộc nhóm {cls}")
    L.append("\n> ⚠️ Đây là diễn giải học thuật trên dữ liệu quá khứ, không phải khuyến nghị mua/bán.")
    return "\n".join(L)


# ---------- TAB 1: SIM ----------
with tab1:
    if not has_data:
        st.info("👈 Nhập mã cổ phiếu ở thanh bên trái rồi bấm **🚀 Phân tích** để bắt đầu.")
    else:
        returns_df = st.session_state.returns_df
        market_ticker = st.session_state.market_ticker
        sim_results_list = st.session_state.sim_results_list
        valid_assets = st.session_state.valid_assets
        sim_df = pd.DataFrame(sim_results_list)

        render_live_prices()
        st.subheader("Tổng quan Rủi ro")
        betas = sim_df['Beta (Độ nhạy)']
        top_beta_row = sim_df.loc[betas.idxmax()]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Số mã phân tích", len(sim_df))
        m2.metric("Beta trung bình", f"{betas.mean():.2f}")
        m3.metric("Mã năng động nhất", top_beta_row['Mã CP'], f"β = {top_beta_row['Beta (Độ nhạy)']:.2f}")
        m4.metric("R² trung bình", f"{sim_df['R^2'].mean():.2%}")

        st.subheader("Bảng chỉ số SIM")

        def _hl_beta(v):
            if v > 1:
                return 'color:#ff6b6b; font-weight:600'
            return 'color:#00c48c; font-weight:600'
        styled = sim_df.style.map(_hl_beta, subset=['Beta (Độ nhạy)']).format({
            'Beta (Độ nhạy)': '{:.3f}', 'Alpha': '{:.5f}', 'Rủi ro Hệ thống': '{:.5f}',
            'Rủi ro Phi hệ thống': '{:.5f}', 'Tổng Rủi ro': '{:.5f}', 'R^2': '{:.3f}',
        })
        st.dataframe(styled, use_container_width=True)
        _download_df(sim_df, "⬇️ Tải bảng SIM (CSV)", "sim_results.csv")

        with st.expander("📚 Giải thích ý nghĩa các chỉ số Kinh tế lượng"):
            st.markdown("""
*   **Beta ($\\beta$):** Đo mức biến động của cổ phiếu so với thị trường. $\\beta>1$: *năng động* (rủi ro & kỳ vọng cao); $\\beta<1$: *thụ động* (an toàn hơn).
*   **Alpha ($\\alpha$):** Lợi suất vượt trội do yếu tố riêng của cổ phiếu.
*   **Rủi ro Hệ thống:** Do biến động chung của thị trường (không thể đa dạng hoá để loại bỏ).
*   **Rủi ro Phi hệ thống:** Do đặc thù công ty (loại bỏ được bằng đa dạng hoá).
*   **R² :** Tỷ lệ biến động giá cổ phiếu được giải thích bởi VNINDEX.
*   **White Test:** 'Yes' = có phương sai sai số thay đổi (cần sai số chuẩn vững).
*   **Breusch-Godfrey:** 'Yes' = có tự tương quan chuỗi.\n*   **Dạng hàm (Ramsey RESET):** 'Có thể có' = mô hình có thể bị sai dạng hàm / bỏ sót biến (Chương 5).\n*   **Phân phối chuẩn (Jarque-Bera):** 'Không chuẩn' = phần dư không phân phối chuẩn, ảnh hưởng suy diễn thống kê mẫu nhỏ.
            """)

        st.subheader("Biểu đồ Hồi quy SIM")
        selected_ticker = st.selectbox("Chọn cổ phiếu để xem biểu đồ hồi quy:", valid_assets)
        if selected_ticker in returns_df.columns:
            fig = px.scatter(returns_df, x=market_ticker, y=selected_ticker, trendline="ols",
                             title=f"Hồi quy {selected_ticker} theo {market_ticker}",
                             labels={market_ticker: f"Lợi suất {market_ticker}", selected_ticker: f"Lợi suất {selected_ticker}"})
            fig.update_traces(marker=dict(color="#00A67E", opacity=0.5))
            st.plotly_chart(fig, use_container_width=True)


# ---------- TAB 2: MARKOWITZ ----------
with tab2:
    if not has_data:
        st.info("👈 Chạy **Phân tích** trước để xem tối ưu danh mục.")
    else:
        opt_res = st.session_state.opt_res
        returns_df = st.session_state.returns_df
        valid_assets = st.session_state.valid_assets

        if opt_res.get('warning'):
            st.warning(f"⚠️ {opt_res['warning']}")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🛡️ Danh mục An toàn nhất")
            st.caption("Min Volatility — rủi ro thấp nhất")
            min_vol_df = pd.DataFrame({'Tài sản': opt_res['assets'], 'Tỷ trọng': opt_res['min_vol_weights']})
            fig_mv = px.pie(min_vol_df, values='Tỷ trọng', names='Tài sản', hole=0.45,
                            color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig_mv, use_container_width=True)
        with c2:
            st.subheader("🚀 Danh mục Hiệu quả nhất")
            st.caption("Max Sharpe — lợi nhuận/rủi ro tốt nhất")
            max_sharpe_df = pd.DataFrame({'Tài sản': opt_res['assets'], 'Tỷ trọng': opt_res['max_sharpe_weights']})
            fig_ms = px.pie(max_sharpe_df, values='Tỷ trọng', names='Tài sản', hole=0.45,
                            color_discrete_sequence=px.colors.sequential.Agsunset)
            st.plotly_chart(fig_ms, use_container_width=True)

        w_table = pd.DataFrame({
            'Tài sản': opt_res['assets'],
            'Min Volatility (%)': (np.array(opt_res['min_vol_weights']) * 100).round(2),
            'Max Sharpe (%)': (np.array(opt_res['max_sharpe_weights']) * 100).round(2),
        })
        st.dataframe(w_table, use_container_width=True)
        _download_df(w_table, "⬇️ Tải tỷ trọng danh mục (CSV)", "portfolio_weights.csv")

        st.subheader("Đường Biên hiệu quả (Efficient Frontier)")
        # Toạ độ 2 danh mục tối ưu để đánh dấu sao
        mean_ret = returns_df[valid_assets].mean() * 252
        cov = returns_df[valid_assets].cov() * 252

        def _perf(w):
            w = np.array(w)
            return float(np.sqrt(w @ cov.values @ w)), float(mean_ret.values @ w)
        mv_std, mv_ret = _perf(opt_res['min_vol_weights'])
        ms_std, ms_ret = _perf(opt_res['max_sharpe_weights'])

        ef_fig = go.Figure()
        ef_fig.add_trace(go.Scatter(x=opt_res['ef_vols'], y=opt_res['ef_rets'], mode='markers',
                                    marker=dict(color=opt_res['ef_sharpes'], colorscale='Viridis',
                                                showscale=True, size=6, colorbar=dict(title="Sharpe")),
                                    name='Danh mục ngẫu nhiên'))
        ef_fig.add_trace(go.Scatter(x=[mv_std], y=[mv_ret], mode='markers',
                                    marker=dict(color='#4dd0e1', size=18, symbol='star',
                                                line=dict(color='white', width=1)),
                                    name='🛡️ Min Volatility'))
        ef_fig.add_trace(go.Scatter(x=[ms_std], y=[ms_ret], mode='markers',
                                    marker=dict(color='#ffd166', size=18, symbol='star',
                                                line=dict(color='white', width=1)),
                                    name='🚀 Max Sharpe'))
        ef_fig.update_layout(title='Mô phỏng 500 danh mục ngẫu nhiên',
                             xaxis_title='Rủi ro (Độ lệch chuẩn năm hoá)',
                             yaxis_title='Lợi suất kỳ vọng (năm hoá)',
                             legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(ef_fig, use_container_width=True)


# ---------- TAB 3: AI ----------
with tab3:
    if not has_data:
        st.info("👈 Chạy **Phân tích** trước để nhận khuyến nghị.")
    else:
        st.subheader("🤖 Chuyên gia Đầu tư Khuyến nghị")
        sim_results_list = st.session_state.sim_results_list
        opt_res = st.session_state.opt_res
        prices_df = st.session_state.prices_df
        market_ticker = st.session_state.market_ticker
        if ai_config and ai_config.get('api_key'):
            with st.spinner(f"Đang chờ {ai_provider} sinh phân tích..."):
                advice = generate_expert_advice(sim_results_list, opt_res, prices_df[market_ticker], ai_config)
        else:
            st.caption("💡 Chưa nhập API key — đang dùng khuyến nghị theo quy tắc. Nhập key ở sidebar để có phân tích AI chuyên sâu.")
            advice = generate_expert_advice(sim_results_list, opt_res, prices_df[market_ticker])
        st.markdown(advice)


# ---------- TAB 4: EVIEWS ----------
with tab4:
    st.subheader("📈 Eviews tiếng Việt (Giả lập)")
    st.markdown("Tải file số liệu, chọn sheet, rồi gõ lệnh y hệt Eviews (`LS Y C X`, `GENR Z = X + Y`).")
    from eviews_emulator import parse_and_execute_command, format_eviews_output

    col_ev1, col_ev2 = st.columns([1, 2])
    with col_ev1:
        st.markdown("#### 📂 Workfile (Dữ liệu)")
        uploaded_file = st.file_uploader("Tải lên file (CSV/Excel)", type=["csv", "xlsx", "xls"])

        if uploaded_file is not None:
            raw_bytes = uploaded_file.getvalue()
            fname = uploaded_file.name

            def _mkbuf():
                b = io.BytesIO(raw_bytes); b.name = fname; return b

            sheets = dc.list_sheets(_mkbuf())
            chosen_sheet = None
            if sheets:
                st.caption(f"📑 File có **{len(sheets)}** sheet.")
                chosen_sheet = st.selectbox("Chọn sheet để làm việc:", sheets)
            mode_label = st.radio("Cách đọc dữ liệu:",
                                  ["Tự động (thông minh)", "Thô (nguyên bản)"], horizontal=True)
            mode = 'auto' if mode_label.startswith("Tự") else 'raw'

            if st.button("📥 Nạp dữ liệu", use_container_width=True):
                try:
                    df, report = dc.smart_import(_mkbuf(), sheet=chosen_sheet, mode=mode)
                    st.session_state.eviews_data = df
                    st.success("Nạp dữ liệu thành công!")
                    st.info(report)
                except Exception as e:
                    st.error(f"Lỗi đọc file: {e}")

        if not st.session_state.eviews_data.empty:
            st.markdown("**Các biến trong bộ nhớ:**")
            st.write(", ".join(map(str, st.session_state.eviews_data.columns.tolist())))
            with st.expander("👁️ Xem trước dữ liệu"):
                st.dataframe(st.session_state.eviews_data.head(20), use_container_width=True)
        else:
            st.info("Chưa có dữ liệu. Hãy tải file và bấm **Nạp dữ liệu**.")

    with col_ev2:
        st.markdown("#### 🧮 Bảng lệnh")
        if st.session_state.eviews_data.empty:
            st.info("Hãy nạp dữ liệu ở cột bên trái trước khi chạy lệnh.")
        else:
            cols_list = list(map(str, st.session_state.eviews_data.columns))
            input_mode = st.radio("Cách nhập:",
                                  ["🖱️ Chọn nhanh (không cần gõ)", "⌨️ Gõ lệnh"], horizontal=True)

            command_to_run = None
            run_now = False

            if input_mode.startswith("🖱️"):
                op = st.selectbox("Bạn muốn làm gì?", [
                    "Hồi quy OLS / Ước lượng SIM (LS)",
                    "Tạo biến mới (GENR)",
                ])
                if op.startswith("Hồi quy"):
                    # Tự nhận diện cột chỉ số thị trường
                    def _is_mkt(c):
                        cl = str(c).lower()
                        return any(k in cl for k in ["vnindex", "index", "vn30", "market", "thitruong"])
                    mkt_candidates = [c for c in cols_list if _is_mkt(c)]
                    default_mkt = mkt_candidates[0] if mkt_candidates else cols_list[-1]
                    stock_opts = [c for c in cols_list if c != default_mkt] or cols_list
                    if mkt_candidates:
                        st.caption(f"💡 Đã tự nhận diện chỉ số thị trường: **{default_mkt}**. Bạn chỉ cần chọn cổ phiếu.")
                    else:
                        st.caption("⚠️ Không tự nhận ra chỉ số thị trường — hãy kiểm tra ô 'Chỉ số thị trường' bên dưới.")
                    y = st.selectbox("Cổ phiếu cần phân tích (Y):", stock_opts)
                    x_market = st.selectbox("Chỉ số thị trường (X) — điền sẵn, đổi nếu cần:",
                                            cols_list, index=cols_list.index(default_mkt))
                    extra = st.multiselect("(Tuỳ chọn) thêm biến độc lập khác:",
                                           [c for c in cols_list if c not in (y, x_market)])
                    xs = [x_market] + [e for e in extra if e != x_market]
                    command_to_run = f"LS {y} C {' '.join(xs)}"
                else:
                    st.caption("Tạo biến mới từ 2 biến sẵn có bằng một phép toán.")
                    newname = st.text_input("Tên biến mới:", "Z")
                    cc1, cc2, cc3 = st.columns(3)
                    v1 = cc1.selectbox("Biến 1:", cols_list, key="genr_v1")
                    opr = cc2.selectbox("Phép toán:", ["+", "-", "*", "/"], key="genr_op")
                    v2 = cc3.selectbox("Biến 2:", cols_list, key="genr_v2")
                    if newname.strip():
                        command_to_run = f"GENR {newname.strip()} = {v1} {opr} {v2}"

                if command_to_run:
                    st.caption("📋 Câu lệnh Eviews tương ứng (học thuộc để sau tự gõ tay):")
                    st.code(command_to_run, language="text")
                    run_now = st.button("▶️ Xem kết quả", use_container_width=True, type="primary")
            else:
                command_to_run = st.text_input(
                    "Nhập lệnh Eviews (VD: LS Y C X1 X2, GENR Z = X1 + X2):", key="eviews_cmd")
                run_now = st.button("▶️ Chạy lệnh", use_container_width=True)

            deep_ai = st.checkbox("🤖 Kèm phân tích chuyên sâu bằng AI (cần API key ở sidebar)")

            if run_now:
                if not command_to_run:
                    st.warning("Vui lòng chọn hoặc nhập lệnh trước.")
                else:
                    with st.spinner("Đang xử lý..."):
                        res = parse_and_execute_command(command_to_run, st.session_state.eviews_data)
                    if "data" in res:
                        st.session_state.eviews_data = res["data"]
                    if res.get("error"):
                        st.error(res["error"])
                    st.markdown("##### 📤 Output (Kết quả)")
                    html_output = format_eviews_output(res)
                    st.components.v1.html(html_output, height=450, scrolling=True)

                    narrative = interpret_regression_vn(res)
                    if narrative:
                        st.markdown("##### 🧠 Diễn giải kết quả (tự động)")
                        st.markdown(narrative)
                        if deep_ai:
                            if ai_config and ai_config.get('api_key'):
                                m = res['results']
                                summary = (f"Biến phụ thuộc: {res.get('dep_var')}. "
                                           f"R^2={float(m.rsquared):.4f}, R^2_adj={float(m.rsquared_adj):.4f}, "
                                           f"F p-value={m.f_pvalue:.4g}. Hệ số & p-value: " +
                                           "; ".join(f"{n}={float(m.params[n]):.4f}(p={float(m.pvalues[n]):.4g})"
                                                     for n in m.params.index))
                                prompt = ("Bạn là giảng viên Kinh tế lượng Tài chính. Dựa trên kết quả hồi quy OLS sau, "
                                          "hãy phân tích chuyên sâu bằng tiếng Việt: (1) đánh giá độ phù hợp và ý nghĩa "
                                          "thống kê, (2) diễn giải kinh tế của từng hệ số, (3) cảnh báo về khuyết tật mô "
                                          "hình nếu có, (4) gợi ý cải thiện. Trình bày gọn bằng Markdown, có emoji hợp lý. "
                                          "Nhấn mạnh đây là phân tích học thuật, không phải khuyến nghị đầu tư.\n\n"
                                          f"KẾT QUẢ: {summary}")
                                with st.spinner("AI đang phân tích chuyên sâu..."):
                                    out = call_llm(prompt, ai_config)
                                if out:
                                    st.markdown("##### 🤖 Phân tích chuyên sâu bằng AI")
                                    st.markdown(out)
                            else:
                                st.warning("Hãy nhập API key ở sidebar (mục Tích hợp AI) để dùng phân tích chuyên sâu.")


# ---------- TAB 5: ÔN THI ----------
with tab5:
    st.subheader("🎓 Công cụ Ôn thi Kinh tế lượng")
    st.markdown("Tính nhanh các đại lượng để làm bài kiểm tra thực hành. Dùng chung dữ liệu đã nạp ở tab **Eviews**.")
    from exam_calculator import (
        calc_return_formula, calc_returns_data,
        calc_sim_risks_formula, calc_sim_risks_data,
        calc_cov_matrix_formula, calc_cov_matrix_data,
        calc_markowitz_params_formula, calc_markowitz_params_data
    )

    if st.session_state.eviews_data.empty:
        st.info("Hãy nạp file số liệu ở tab **📈 Eviews tiếng Việt** để dùng công cụ tính nhanh.")
    else:
        exam_data = st.session_state.eviews_data
        with st.expander("👁️ Dữ liệu hiện tại"):
            st.dataframe(exam_data.head(20), use_container_width=True)

        st.caption("💡 Chọn **cột giá** (không phải cột r_...) làm Asset & Market — công cụ tự tính lợi suất.")
        c1, c2 = st.columns(2)
        selected_asset = c1.selectbox("Mã Cổ phiếu (Asset):", exam_data.columns)
        selected_market = c2.selectbox("Chỉ số Thị trường (Market):", exam_data.columns,
                                       index=min(1, len(exam_data.columns) - 1))

        st.markdown("##### Các lệnh tính nhanh")
        b1, b2 = st.columns(2)
        b3, b4 = st.columns(2)

        if b1.button("1️⃣ Tỷ suất Sinh lời", use_container_width=True):
            st.latex(calc_return_formula())
            try:
                ret = calc_returns_data(exam_data[selected_asset])
                st.write(f"Lợi suất của **{selected_asset}** (5 ngày đầu):")
                st.dataframe(ret.head())
            except Exception as e:
                st.error(f"Lỗi: {e}. Đảm bảo cột là dạng số hợp lệ.")

        if b2.button("2️⃣ Rủi ro HT / Phi HT (SIM)", use_container_width=True):
            st.latex(calc_sim_risks_formula())
            try:
                r_asset = calc_returns_data(exam_data[selected_asset])
                r_market = calc_returns_data(exam_data[selected_market])
                risks = calc_sim_risks_data(r_asset, r_market)
                st.write(f"Kết quả **{selected_asset}** so với **{selected_market}**:")
                st.json({k: float(v) for k, v in risks.items()})
            except Exception as e:
                st.error(f"Lỗi: {e}")

        if b3.button("3️⃣ Ma trận Hiệp phương sai (V)", use_container_width=True):
            st.latex(calc_cov_matrix_formula())
            try:
                numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
                returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
                st.dataframe(calc_cov_matrix_data(returns_all), use_container_width=True)
            except Exception as e:
                st.error(f"Lỗi: {e}")

        if b4.button("4️⃣ Đại lượng Markowitz (A,B,C,D)", use_container_width=True):
            st.latex(calc_markowitz_params_formula())
            try:
                numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
                returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
                params = calc_markowitz_params_data(returns_all)
                st.json({k: float(v) if not isinstance(v, str) else v for k, v in params.items()})
            except Exception as e:
                st.error(f"Lỗi: {e}")
