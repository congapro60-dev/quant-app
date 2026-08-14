import io
import hashlib
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import timedelta
from data_loader import (
    calculate_returns,
    fetch_data,
    fetch_intraday,
    intraday_query_signature,
    vietnam_now,
)
from analytics import run_sim, run_diagnostics, markowitz_optimization, generate_expert_advice, call_llm
from safe_ai_tools import (
    SafeAnalysisError,
    analyze_request,
    build_explanation_prompt,
    result_for_display,
)
from statsmodels.stats.stattools import durbin_watson
import data_cleaner as dc
from investment_ui import render_backtest, render_investment_desk, render_paper_portfolio
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ==================== CẤU HÌNH TRANG ====================
st.set_page_config(page_title="Quant App - Phân tích Thị trường", page_icon="📈", layout="wide")

st.markdown("""
<style>
    :root {
        --qa-primary: #1D4ED8;
        --qa-primary-soft: #172554;
        --qa-accent: #D97706;
        --qa-surface: #111827;
        --qa-border: #334155;
        --qa-text: #F8FAFC;
        --qa-muted: #CBD5E1;
        --qa-danger: #EF4444;
        --qa-success: #10B981;
    }
    .block-container { padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1480px; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #111827 0%, #172033 100%);
        border: 1px solid var(--qa-border); border-radius: 12px; padding: 14px 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,.16);
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--qa-surface); border: 1px solid var(--qa-border);
        border-radius: 8px 8px 0 0; padding: 10px 16px; min-height: 44px;
    }
    .stTabs [aria-selected="true"] { background-color: var(--qa-primary); color: white; }
    .stTabs [data-baseweb="tab"]:focus-visible,
    button:focus-visible, input:focus-visible, textarea:focus-visible {
        outline: 3px solid #F59E0B !important; outline-offset: 2px;
    }
    .qa-hero {
        padding: 18px 20px; border: 1px solid var(--qa-border); border-radius: 14px;
        background: linear-gradient(120deg, #111827 0%, #172554 100%); margin-bottom: 14px;
    }
    .qa-hero h1 { font-size: 2.35rem; line-height: 1.16; }
    .qa-hero strong { color: #BFDBFE; }
    .qa-safety {
        padding: 12px 14px; border-left: 4px solid var(--qa-accent);
        background: rgba(217,119,6,.10); border-radius: 8px; color: var(--qa-muted);
    }
    @media (max-width: 768px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .stTabs [data-baseweb="tab"] { padding: 8px 10px; }
        .qa-hero { padding: 14px 16px; }
        .qa-hero h1 { font-size: 1.75rem; line-height: 1.2; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="qa-hero">
  <h1 style="margin:0 0 6px 0">Quant App — Học thuật & Quyết định đầu tư</h1>
  <div><strong>Phân tích định lượng có kiểm định</strong> · Mô hình chỉ số đơn (SIM) · Danh mục Markowitz · Kiểm thử quá khứ (backtest) · Danh mục mô phỏng (paper portfolio) · EViews</div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div class='qa-safety'>Công cụ hỗ trợ quyết định, không cam kết lợi nhuận. Chỉ cân nhắc vốn thật sau khi chiến lược vượt kiểm định ngoài mẫu (OOS) và giao dịch mô phỏng (paper trading).</div>", unsafe_allow_html=True)

with st.expander("📘 Thuật ngữ nhanh — đọc tiếng Việt, làm quen tiếng Anh"):
    st.markdown("""
| Thuật ngữ trên ứng dụng | Nghĩa ngắn gọn |
|---|---|
| **Trí tuệ nhân tạo (AI)** · **Giao diện lập trình (API)** | AI diễn giải; API là cách ứng dụng kết nối dịch vụ AI. |
| **Dữ liệu cuối ngày (EOD)** · **thời gian thực (realtime)** | EOD chốt theo phiên; realtime cập nhật gần như tức thời. |
| **Mô hình chỉ số đơn (SIM)** · **Markowitz** | Hai mô hình học thuật để đo rủi ro và phân bổ danh mục. |
| **Kiểm thử quá khứ (backtest)** · **ngoài mẫu (OOS)** | Thử chiến lược trên lịch sử; OOS là phần dữ liệu không dùng để xây chiến lược. |
| **Danh mục/giao dịch mô phỏng (paper portfolio/paper trading)** | Ghi nhận mua bán giả lập, không gửi lệnh thật. |
| **Lãi/lỗ (P&L)** · **mức sụt giảm (drawdown)** | Kết quả lời/lỗ và mức giảm từ đỉnh xuống đáy. |
| **Dừng lỗ (stop)** · **mục tiêu giá (target)** | Mức thoát khi sai và mức dự kiến chốt lời. |
| **Trượt giá (slippage)** · **danh mục tham chiếu (benchmark)** | Chênh lệch giá dự kiến/khớp; chuẩn để so kết quả. |
| **Điểm cơ bản (bps)** | 100 bps = 1%; thường dùng cho phí, thuế và trượt giá. |
| **Tệp bảng (CSV)** · **tệp cấu trúc (JSON)** | CSV để xem dữ liệu; JSON để sao lưu và khôi phục trạng thái. |
| **Chọn tệp/Tải lên (Choose File/Upload)** · **Chọn ngày (Select a date)** | Nhãn hệ thống mặc định của Streamlit tương ứng với chọn tệp, tải lên và chọn ngày. |
| **Hiện/ẩn cột (Show/hide columns)** · **Tìm kiếm (Search)** · **Toàn màn hình (Fullscreen)** | Các nút hệ thống của bảng dữ liệu; **Download as CSV** là tải xuống dưới dạng CSV. |
| **Tạo bản sao (Fork)** · **Menu chính (Main menu)** | Điều khiển của nền tảng Streamlit Cloud, không phải lệnh giao dịch. |
""")

# ==================== KHỞI TẠO SESSION STATE ====================
for k, v in {
    'prices_df': pd.DataFrame(), 'opt_res': {}, 'sim_results_list': [],
    'returns_df': pd.DataFrame(), 'market_ticker': "", 'valid_assets': [],
    'tickers_val': "FPT, HPG, CTG, DPM", 'eviews_data': pd.DataFrame(),
    'last_query': None, 'last_update': None, 'ai_ok': None, 'ai_err': '',
    'ai_connection_signature': None, 'advice_cache': {},
    'data_status': 'idle', 'data_error': '', 'data_last_date': None,
    'live_refresh_counter': None, 'paper_trades': [], 'paper_ledger': None,
    'trade_plans': {}, 'backtest_result': None,
    'last_query_uses_today': False, 'intraday_result': None,
    'intraday_active_query_signature': '',
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("⚙️ Tham số đầu vào")

    st.caption("Chọn nhanh danh mục mẫu:")
    p1, p2 = st.columns(2)
    p3, p4 = st.columns(2)
    if p1.button("Ngân hàng", width="stretch"):
        st.session_state.tickers_val = "CTG, VCB, BID, MBB"; st.rerun()
    if p2.button("VN30 lớn", width="stretch"):
        st.session_state.tickers_val = "FPT, HPG, VNM, MWG"; st.rerun()
    if p3.button("Bất động sản", width="stretch"):
        st.session_state.tickers_val = "VHM, VIC, NVL, PDR"; st.rerun()
    if p4.button("Bài thực tập", width="stretch"):
        st.session_state.tickers_val = "BID, BVH, CTG"; st.rerun()

    with st.form("input_form"):
        tickers_input = st.text_input("Mã cổ phiếu (cách nhau bằng dấu phẩy):",
                                      key="tickers_val")
        index_input = st.text_input("Chỉ số thị trường:", "VNINDEX")
        c1, c2 = st.columns(2)
        end_date = vietnam_now().date()
        start_date = end_date - timedelta(days=365)
        start_date_input = c1.date_input("Từ ngày:", start_date)
        end_date_input = c2.date_input("Đến ngày:", end_date)
        submitted = st.form_submit_button("🚀 Phân tích", width="stretch", type="primary")

    st.markdown("---")
    st.header("Làm mới dữ liệu cuối ngày (EOD)")
    live_mode = st.toggle("Tự động làm mới dữ liệu lịch sử", value=False,
                          help="Đây là dữ liệu giá mở-cao-thấp-đóng và khối lượng (OHLCV) lịch sử/cuối ngày (EOD), không phải báo giá thời gian thực (realtime) hay sổ lệnh.")
    refresh_min = st.selectbox("Chu kỳ làm mới (phút):", [1, 5, 15], index=1, disabled=not live_mode)
    if live_mode and st_autorefresh is None:
        st.caption("⚠️ Thiếu gói tự làm mới `streamlit-autorefresh` nên chưa tự làm mới được.")

    st.markdown("---")
    st.header("Tích hợp trí tuệ nhân tạo (AI) — tùy chọn")
    ai_provider = st.radio("Nhà cung cấp (provider) AI:", ["Không dùng", "Anthropic (Claude)", "Google (Gemini)"], horizontal=True)
    ai_config = None
    if ai_provider != "Không dùng":
        api_key = st.text_input("Khóa giao diện lập trình (API key):", type="password", key="api_key_val")
        if ai_provider == "Anthropic (Claude)":
            model_choice = st.selectbox("Mô hình (model):", ["claude-sonnet-5", "claude-fable-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"])
        else:
            model_choice = st.selectbox("Mô hình (model):", ["gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.1-flash-lite"])
            if model_choice == "gemini-3.1-pro-preview":
                st.caption(
                    "ℹ️ Gemini 3.1 Pro Preview có thể không có hạn mức (quota) ở bậc miễn phí (Free Tier). "
                    "Nếu API trả QUOTA_OR_TIER, cần bật bậc trả phí (Paid Tier) cho đúng dự án Google Cloud "
                    "hoặc chọn Flash; đổi mã nguồn hay mã mô hình (model ID) không thể vượt giới hạn tài khoản."
                )
        ai_config = {'provider': ai_provider, 'model': model_choice, 'api_key': api_key}

        current_ai_signature = hashlib.sha256(
            f"{ai_provider}|{model_choice}|{api_key}".encode("utf-8")
        ).hexdigest() if api_key else None
        if current_ai_signature != st.session_state.get('ai_connection_signature'):
            st.session_state['ai_ok'] = None
            st.session_state['ai_err'] = ""

        if api_key:
            if st.button("🔌 Kích hoạt & kiểm tra kết nối", width="stretch"):
                with st.spinner("Đang kiểm tra khóa API..."):
                    test = call_llm("Trả lời đúng 1 từ: OK", ai_config)
                if test and not str(test).startswith("Lỗi"):
                    st.session_state['ai_ok'] = True
                    st.session_state['ai_err'] = ""
                    st.session_state['ai_connection_signature'] = current_ai_signature
                else:
                    st.session_state['ai_ok'] = False
                    st.session_state['ai_err'] = str(test) if test else "Không nhận được phản hồi."
                    st.session_state['ai_connection_signature'] = current_ai_signature
            if (st.session_state.get('ai_ok') is True and
                    st.session_state.get('ai_connection_signature') == current_ai_signature):
                st.success(f"🟢 Đã kết nối {ai_provider} — {model_choice}. Sẵn sàng dùng ở các thẻ (tab) AI.")
            elif st.session_state.get('ai_ok') is False:
                st.error(f"🔴 Khóa API chưa dùng được: {st.session_state.get('ai_err','')}")
            else:
                st.info("🔑 Đã nhận khóa API — có thể dùng ngay. Bấm nút trên để xác nhận khóa hợp lệ (khuyên dùng).")
        else:
            st.caption("Nhập khóa API để bật phân tích bằng trí tuệ nhân tạo (AI).")
        st.caption("🔒 Khóa API chỉ lưu tạm trong phiên, không ghi vào mã nguồn (code).")

# ==================== XỬ LÝ KHI BẤM PHÂN TÍCH ====================
def _clear_market_state(error_message=""):
    """Fail closed: never keep an old portfolio result after a failed refresh."""
    st.session_state.prices_df = pd.DataFrame()
    st.session_state.returns_df = pd.DataFrame()
    st.session_state.sim_results_list = []
    st.session_state.opt_res = {}
    st.session_state.market_ticker = ""
    st.session_state.valid_assets = []
    st.session_state.last_update = None
    st.session_state.data_last_date = None
    st.session_state.data_source = ""
    st.session_state.data_status = "error"
    st.session_state.data_error = str(error_message)


def run_analysis(asset_tickers, market_ticker, start_str, end_str, show_msgs=True):
    asset_tickers = list(dict.fromkeys([t.strip().upper() for t in asset_tickers if t.strip()]))
    market_ticker = market_ticker.strip().upper()
    if not asset_tickers or not market_ticker:
        _clear_market_state("Cần ít nhất một mã cổ phiếu và một chỉ số thị trường.")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    if len(asset_tickers) > 12:
        _clear_market_state("Giới hạn 12 mã mỗi lần để bảo vệ hạn mức (quota) và độ ổn định.")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    if pd.Timestamp(start_str) >= pd.Timestamp(end_str):
        _clear_market_state("Ngày bắt đầu phải trước ngày kết thúc.")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    all_tickers = list(dict.fromkeys(asset_tickers + [market_ticker]))
    try:
        with st.spinner('Đang tải và kiểm định dữ liệu từ vnstock...'):
            prices_df = fetch_data(all_tickers, start_str, end_str)
    except Exception as exc:
        _clear_market_state(f"Không tải được dữ liệu: {exc}")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    if prices_df.empty or market_ticker not in prices_df.columns:
        _clear_market_state("Không tải được dữ liệu chỉ số thị trường hoặc dữ liệu không đạt kiểm định.")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    valid_assets = [t for t in asset_tickers if t in prices_df.columns]
    failed_assets = [t for t in asset_tickers if t not in prices_df.columns]
    if failed_assets:
        _clear_market_state(
            "Không phân tích danh mục thiếu mã. Hãy kiểm tra hoặc bỏ các mã: " + ", ".join(failed_assets)
        )
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    if not valid_assets:
        _clear_market_state("Tất cả mã cổ phiếu đều không có dữ liệu hợp lệ.")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    try:
        returns_df = calculate_returns(prices_df)
        required = valid_assets + [market_ticker]
        returns_df = returns_df[required].replace([np.inf, -np.inf], np.nan).dropna()
        if len(returns_df) < 60:
            raise ValueError(f"Chỉ có {len(returns_df)} phiên đồng bộ; cần tối thiểu 60 phiên.")
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
                'Số quan sát': int(sim_res.get('n_observations', len(asset_returns_df))),
                'Phương sai SS thay đổi (White)': diag_res['Heteroskedasticity'],
                'White p-value': diag_res.get('White_pvalue'),
                'Tự tương quan (B-G)': diag_res['Autocorrelation'],
                'B-G p-value': diag_res.get('BG_pvalue'),
                'Dạng hàm (RESET)': diag_res.get('SpecificationError', 'N/A'),
                'RESET p-value': diag_res.get('RESET_pvalue'),
                'Phân phối chuẩn (JB)': diag_res.get('Normality', 'N/A'),
                'JB p-value': diag_res.get('JB_pvalue'),
                'Chẩn đoán': diag_res.get('status', 'unknown'),
            })
        opt_res = markowitz_optimization(asset_returns_df)
    except Exception as exc:
        _clear_market_state(f"Dữ liệu hoặc mô hình không đạt kiểm định: {exc}")
        if show_msgs:
            st.error(st.session_state.data_error)
        return False
    st.session_state.prices_df = prices_df
    st.session_state.returns_df = returns_df
    st.session_state.sim_results_list = sim_results_list
    st.session_state.opt_res = opt_res
    st.session_state.market_ticker = market_ticker
    st.session_state.valid_assets = valid_assets
    st.session_state.last_query = (asset_tickers, market_ticker, start_str, end_str)
    st.session_state.last_update = vietnam_now()
    st.session_state.data_last_date = pd.Timestamp(prices_df.index.max())
    fetch_report = prices_df.attrs.get("fetch_report", {})
    st.session_state.data_source = fetch_report.get("source", "")
    st.session_state.data_status = "ok"
    st.session_state.data_error = ""
    return True


# Kích hoạt phân tích khi bấm nút
if submitted:
    # A manual query replaces the previous research universe.  Invalidate all
    # dependent artifacts before attempting it so a failed CTG/FPT request can
    # never revive an older portfolio, backtest or trade plan on the next tick.
    st.session_state['last_query'] = None
    st.session_state['last_query_uses_today'] = False
    st.session_state['backtest_result'] = None
    st.session_state['trade_plans'] = {}
    st.session_state['advice_cache'] = {}
    submitted_uses_today = end_date_input == vietnam_now().date()
    submitted_ok = run_analysis(
        tickers_input.split(','), index_input,
        start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d')
    )
    if submitted_ok:
        st.session_state['last_query_uses_today'] = submitted_uses_today

# Chế độ real-time: tự làm mới định kỳ và tính lại
st.session_state['_live_flag'] = bool(live_mode)
if live_mode and st_autorefresh is not None:
    refresh_counter = st_autorefresh(interval=refresh_min * 60 * 1000, key="live_refresh")
    is_refresh_tick = refresh_counter != st.session_state.get('live_refresh_counter')
    st.session_state.live_refresh_counter = refresh_counter
    if is_refresh_tick and st.session_state.get('last_query') and not submitted:
        refresh_query = list(st.session_state['last_query'])
        if st.session_state.get('last_query_uses_today'):
            refresh_query[3] = vietnam_now().date().isoformat()
        run_analysis(*refresh_query, show_msgs=False)

# ==================== CÁC TAB ====================
(invest_tab, intraday_tab, paper_tab, backtest_tab,
 tab1, tab2, tab3, tab4, tab5) = st.tabs([
    "Bàn đầu tư", "Giá trong phiên", "Danh mục mô phỏng (paper portfolio)", "Kiểm thử ngoài mẫu (backtest OOS)",
    "Rủi ro chỉ số đơn (SIM)", "Danh mục trung bình–phương sai (Markowitz)", "Trợ lý quyết định",
    "EViews tiếng Việt", "Ôn thi",
])

has_data = (not st.session_state.prices_df.empty) and bool(st.session_state.market_ticker)

if st.session_state.get('data_status') == 'error' and st.session_state.get('data_error'):
    st.error(f"Dữ liệu hiện không hợp lệ: {st.session_state.data_error}")


def _download_df(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode('utf-8-sig'),
                       file_name=filename, mime="text/csv")


def render_live_prices():
    prices_df = st.session_state.prices_df
    tickers = st.session_state.valid_assets + [st.session_state.market_ticker]
    tickers = [t for t in tickers if t in prices_df.columns]
    lu = st.session_state.get('last_update')
    auto_refresh = st.session_state.get('_live_flag', False)
    tag = "TỰ LÀM MỚI" if auto_refresh else "DỮ LIỆU CUỐI NGÀY (EOD)"
    if lu is not None:
        try:
            lu = pd.Timestamp(lu)
            if lu.tzinfo is None:
                lu = lu.tz_localize("Asia/Ho_Chi_Minh")
            else:
                lu = lu.tz_convert("Asia/Ho_Chi_Minh")
        except (TypeError, ValueError):
            lu = None
        last_session = st.session_state.get('data_last_date')
        last_session_text = pd.Timestamp(last_session).strftime('%d/%m/%Y') if last_session is not None else "không rõ"
        data_source = st.session_state.get('data_source')
        source_text = f" · nguồn {data_source}" if data_source else ""
        if lu is not None:
            st.caption(
                f"{tag} · phiên gần nhất {last_session_text}{source_text} · "
                f"tải lúc {lu.strftime('%H:%M:%S %d/%m/%Y')} (giờ Việt Nam) · "
                "không phải báo giá thời gian thực (realtime)"
            )
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
    L.append("- Xem thêm Jarque-Bera (chuẩn tắc phần dư) và hệ số phóng đại phương sai (VIF, đa cộng tuyến) ở bảng kết quả phía trên.")

    nonconst = [n for n in params.index if str(n).lower() not in ('const', 'c')]
    if len(nonconst) == 1:
        b = float(params[nonconst[0]])
        if b > 1:
            cls = "**năng động** (β>1): biến động mạnh hơn thị trường — rủi ro & kỳ vọng cao."
        elif 0 < b < 1:
            cls = "**phòng thủ** (0<β<1): biến động yếu hơn thị trường — an toàn hơn."
        else:
            cls = "ngược chiều thị trường (β≤0): hiếm gặp, nên kiểm tra lại dữ liệu."
        L.append(
            f"**4. Góc nhìn mô hình chỉ số đơn (SIM)** — Beta (độ nhạy) = {b:.3f} "
            f"→ cổ phiếu thuộc nhóm {cls}"
        )
    L.append("\n> ⚠️ Đây là diễn giải học thuật trên dữ liệu quá khứ, không phải khuyến nghị mua/bán.")
    return "\n".join(L)


def render_eviews_plot(plot):
    kind = plot["kind"]
    data = plot["data"].dropna()
    cols = plot["cols"]
    if kind == "scatter":
        fig = px.scatter(data, x=cols[0], y=cols[1], trendline="ols",
                         title=f"Phân tán {cols[1]} theo {cols[0]}")
        fig.update_traces(marker=dict(color="#00A67E", opacity=0.5))
        st.plotly_chart(fig, width="stretch")
    elif kind == "hist":
        fig = px.histogram(data, x=cols[0], nbins=40, title=f"Phân phối {cols[0]}")
        fig.update_traces(marker_color="#00A67E")
        st.plotly_chart(fig, width="stretch")
    else:
        d = data.reset_index().rename(columns={"index": "Quan sát"})
        fig = px.line(d, x="Quan sát", y=cols, title="Đồ thị đường")
        st.plotly_chart(fig, width="stretch")


def _prep_returns(df, cols, nobs, reverse, is_returns):
    data = df[cols].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
    if nobs and int(nobs) > 1:
        data = data.head(int(nobs))
    if reverse:
        data = data.iloc[::-1]
    if is_returns:
        clean = data.dropna()
        if not np.isfinite(clean.to_numpy()).all():
            raise ValueError("Lợi suất chứa giá trị không hữu hạn.")
        return clean, len(data)
    if (data <= 0).any().any():
        raise ValueError("Giá phải dương để tính lợi suất logarit (log-return).")
    returns = np.log(data / data.shift(1)).replace([np.inf, -np.inf], np.nan).dropna()
    return returns, len(data)


def _validated_weights(assets, weights, normalize):
    if not assets:
        raise ValueError("Danh mục phải có ít nhất một tài sản.")
    w = np.asarray(weights, dtype=float)
    if len(w) != len(assets):
        raise ValueError("Số trọng số không khớp số tài sản.")
    if not np.isfinite(w).all() or (w < 0).any():
        raise ValueError("Trọng số phải hữu hạn và không âm.")
    total = float(w.sum())
    if total <= 0:
        raise ValueError("Tổng trọng số phải lớn hơn 0.")
    if normalize:
        return w / total
    if not np.isclose(total, 1.0, atol=1e-6):
        raise ValueError("Khi không tự chuẩn hóa, tổng trọng số phải bằng 1.")
    return w


def compute_portfolio(df, assets, weights, nobs=0, reverse=False, normalize=True,
                      is_returns=False, ddof=1):
    """Rủi ro danh mục theo phương pháp hiệp phương sai: σ²_P = W'VW."""
    w = _validated_weights(assets, weights, normalize)
    R, n_raw = _prep_returns(df, list(assets), nobs, reverse, is_returns)
    if len(R) < 20:
        raise ValueError(f"Cần ít nhất 20 lợi suất; hiện chỉ có {len(R)}.")
    rp = R.values @ w
    cov = pd.DataFrame(np.cov(R.values.T, ddof=ddof), index=list(assets), columns=list(assets))
    return {
        'weights': w, 'assets': list(assets), 'n_prices': n_raw, 'n_returns': len(R),
        'asset_means': R.mean(), 'mean': float(np.mean(rp)),
        'variance': float(np.var(rp, ddof=ddof)), 'std': float(np.std(rp, ddof=ddof)),
        'cov': cov, 'ddof': ddof,
    }


def compute_sim_portfolio_risk(df, assets, market, weights, nobs=0, reverse=False,
                               normalize=True, is_returns=False):
    """Rủi ro danh mục theo mô hình SIM: tách rủi ro hệ thống / phi hệ thống."""
    import statsmodels.api as sm
    w = _validated_weights(assets, weights, normalize)
    R, _ = _prep_returns(df, list(assets) + [market], nobs, reverse, is_returns)
    if len(R) < 20:
        raise ValueError(
            f"Mô hình chỉ số đơn (SIM) cần ít nhất 20 lợi suất; hiện chỉ có {len(R)}."
        )
    Rm = R[market]
    sig_m2 = float(Rm.var(ddof=1))
    X = sm.add_constant(Rm)
    betas, etas, per = [], [], []
    for a in assets:
        res = sm.OLS(R[a], X).fit()
        b = float(res.params[market])
        eta = float(res.mse_resid)          # η² = SSR/(n-2)
        sysr = b * b * sig_m2
        betas.append(b); etas.append(eta)
        per.append({'Mã': a, 'Beta': round(b, 6),
                    'Rủi ro hệ thống': round(sysr, 8),
                    'Rủi ro phi hệ thống (η²)': round(eta, 8),
                    'Tổng rủi ro': round(sysr + eta, 8)})
    betas = np.array(betas); etas = np.array(etas)
    beta_p = float(w @ betas)
    sysP = beta_p ** 2 * sig_m2
    unsysP = float(np.sum(w ** 2 * etas))
    return {'weights': w, 'assets': list(assets), 'market': market, 'n_returns': len(R),
            'sigma_market2': sig_m2, 'per_stock': per, 'beta_p': beta_p,
            'systematic': sysP, 'unsystematic': unsysP, 'total': sysP + unsysP,
            'total_std': float(np.sqrt(sysP + unsysP))}


def run_ai_analysis(df, request, ai_config, extra_context=""):
    """Run audited local calculations; optionally ask the LLM to explain them."""
    try:
        bundle = analyze_request(df, request)
    except SafeAnalysisError as exc:
        return {"error": str(exc), "code": None, "result": None}

    output = result_for_display(bundle)
    if ai_config and ai_config.get("api_key"):
        prompt = build_explanation_prompt(request, bundle)
        response = call_llm(prompt, ai_config)
        if response and not str(response).startswith("Lỗi"):
            output["narrative"] = f"{bundle.narrative}\n\n{response}"
        elif response:
            output["error"] = (
                "Phép tính cục bộ đã hoàn tất nhưng trí tuệ nhân tạo (AI) không diễn giải được: "
                f"{response}"
            )
    return output


# ---------- KHỐI NGHIÊN CỨU ĐẦU TƯ ----------
with invest_tab:
    render_investment_desk(
        st.session_state.prices_df,
        st.session_state.returns_df,
        st.session_state.valid_assets,
        st.session_state.market_ticker,
        st.session_state.sim_results_list,
    )

with paper_tab:
    render_paper_portfolio(st.session_state.prices_df)

with backtest_tab:
    render_backtest(
        st.session_state.prices_df,
        st.session_state.valid_assets,
        st.session_state.market_ticker,
    )


# ---------- TAB: GIÁ TRONG PHIÊN (INTRADAY) ----------
with intraday_tab:
    st.header("Giá khớp lệnh trong phiên")
    st.warning(
        "⚠️ **Đây là dữ liệu khớp lệnh có độ trễ, không phải bảng giá tức thời.** "
        "Độ trễ thay đổi theo nhà cung cấp (provider) và đường truyền; ứng dụng chỉ hiển thị dữ liệu "
        "đúng mã, đúng phiên hiện tại và chưa quá ngưỡng trễ an toàn. "
        "Khớp lệnh liên tục: **9:15–11:30** và **13:00–14:30**. "
        "Trước khi đặt lệnh, hãy đối chiếu bảng giá của công ty chứng khoán."
    )

    default_tickers = st.session_state.get('valid_assets') or []
    default_text = default_tickers[0] if default_tickers else "CTG"

    c1, c2 = st.columns([2, 1])
    intraday_ticker = c1.text_input(
        "Mã cổ phiếu cần xem:", value=default_text, key="intraday_ticker"
    ).strip().upper()
    n_ticks = c2.selectbox(
        "Số lệnh gần nhất:", [100, 300, 500, 1000], index=2,
        key="intraday_page_size",
    )
    current_intraday_signature = intraday_query_signature(intraday_ticker, n_ticks)
    cached_intraday = st.session_state.get('intraday_result')
    cached_signature = getattr(cached_intraday, 'query_signature', '')
    if cached_intraday is not None and cached_signature != current_intraday_signature:
        # A rerun caused by editing CTG -> FPT must never relabel CTG's cached ticks.
        st.session_state['intraday_result'] = None
        cached_intraday = None
    st.session_state['intraday_active_query_signature'] = current_intraday_signature

    a1, a2 = st.columns([1, 1])
    intraday_auto = a1.toggle(
        "🔁 Tự làm mới giá", value=False, key="intraday_auto",
        help="Tự tải lại giá khớp lệnh theo chu kỳ. Chỉ bật khi đang theo dõi, "
             "vì mỗi lần làm mới đều tốn băng thông và lượt gọi nhà cung cấp.",
    )
    intraday_every = a2.selectbox(
        "Chu kỳ (giây):", [15, 30, 60, 120], index=1,
        disabled=not intraday_auto, key="intraday_every",
    )

    auto_tick = False
    if intraday_auto:
        if st_autorefresh is None:
            st.warning("Thiếu gói tự làm mới `streamlit-autorefresh` nên chưa tự làm mới được.")
        else:
            counter = st_autorefresh(
                interval=int(intraday_every) * 1000, key="intraday_refresh"
            )
            # Only refetch on a genuine timer tick, not on every Streamlit rerun
            # (typing in a box or switching tabs also reruns the script).
            auto_tick = counter != st.session_state.get('intraday_refresh_counter')
            st.session_state['intraday_refresh_counter'] = counter

    manual_click = st.button("🔄 Lấy dữ liệu trong phiên", type="primary", key="btn_intraday")

    if manual_click or (auto_tick and intraday_ticker):
        with st.spinner(f"Đang lấy dữ liệu khớp lệnh của {intraday_ticker}..."):
            st.session_state['intraday_result'] = fetch_intraday(
                intraday_ticker, page_size=n_ticks
            )

    if intraday_auto and st_autorefresh is not None:
        refreshed = st.session_state.get('intraday_result')
        refreshed_at = getattr(refreshed, 'fetched_at', None)
        if refreshed_at is not None:
            refreshed_text = refreshed_at.strftime('%H:%M:%S')
        else:
            refreshed_text = "chưa có"
        st.caption(
            f"🔁 Đang tự làm mới mỗi **{intraday_every} giây** "
            f"(lần tải dữ liệu gần nhất: {refreshed_text}, giờ Việt Nam). "
            "Tắt công tắc khi không dùng để đỡ tốn băng thông."
        )

    intr = st.session_state.get('intraday_result')
    if intr is None:
        st.info("Nhập mã rồi bấm **Lấy dữ liệu trong phiên** (hoặc bật *Tự làm mới giá*).")
    elif not intr.ok:
        st.error(f"Không lấy được dữ liệu: {intr.error}")
        st.caption(
            "**Khi nào dữ liệu trống là bình thường (không phải lỗi phần mềm):**  \n"
            "• Ngoài giờ giao dịch → nhà cung cấp báo 'chuẩn bị phiên mới'.  \n"
            "• Trong phiên khớp lệnh định kỳ mở cửa (ATO, 9:00–9:15) và đóng cửa "
            "(ATC, 14:30–14:45) → chưa sinh lệnh khớp liên tục nên bảng lệnh còn trống.  \n"
            "• Nghỉ trưa 11:30–13:00, hoặc thứ Bảy/Chủ nhật/ngày lễ.  \n"
            "→ Khớp lệnh liên tục chạy **9:15–11:30** và **13:00–14:30**, thử lại lúc đó."
        )
    else:
        ticks = intr.data
        result_symbol = intr.symbol
        last_price = intr.last_price
        last_time = intr.last_tick_time
        first_price = float(ticks['price'].iloc[0])
        change = (last_price - first_price) if last_price is not None else None
        pct = (change / first_price * 100) if (change is not None and first_price) else None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá khớp gần nhất", f"{last_price:,.2f}" if last_price else "—",
                  f"{pct:+.2f}% trong mẫu" if pct is not None else None)
        m2.metric("Thời điểm khớp",
                  last_time.strftime("%H:%M:%S %d/%m/%Y") if last_time is not None else "—")
        m3.metric("Số lệnh lấy về", f"{len(ticks):,}")
        m4.metric("Nguồn dữ liệu", intr.source)

        if intr.fetched_at is not None and last_time is not None and intr.lag_seconds is not None:
            lag = intr.lag_seconds
            lag_text = f"{lag:.0f} giây" if lag < 90 else f"{lag/60:.1f} phút"
            st.caption(
                f"⏱️ **Khoảng cách tới lệnh mới nhất: {lag_text}** — {result_symbol} "
                f"khớp lúc {last_time.strftime('%H:%M:%S')}, ứng dụng nhận xong lúc "
                f"{intr.fetched_at.strftime('%H:%M:%S')} (giờ Việt Nam). "
                "Khoảng này gồm độ trễ nguồn dữ liệu, mạng và thời gian xử lý; "
                "không phải phép đo riêng của nhà cung cấp."
            )

        fig_intr = px.line(
            ticks, x="time", y="price",
            title=f"Diễn biến giá khớp lệnh trong phiên — {result_symbol}",
            labels={"time": "Thời gian", "price": "Giá khớp"},
        )
        fig_intr.update_traces(line_width=2)
        st.plotly_chart(fig_intr, use_container_width=True)

        if "volume" in ticks.columns:
            fig_vol = px.bar(
                ticks, x="time", y="volume",
                title="Khối lượng theo từng lệnh khớp",
                labels={"time": "Thời gian", "volume": "Khối lượng"},
            )
            st.plotly_chart(fig_vol, use_container_width=True)

        with st.expander("Xem bảng lệnh khớp chi tiết"):
            ticks_display = ticks.copy()
            if "side" in ticks_display.columns:
                def _side_label(value):
                    raw = str(value).strip()
                    upper = raw.upper()
                    if upper in {"BUY", "BU", "B"}:
                        return f"Mua ({raw})"
                    if upper in {"SELL", "SD", "S"}:
                        return f"Bán ({raw})"
                    return f"Loại khác ({raw})"

                ticks_display["side"] = ticks_display["side"].map(_side_label)
            ticks_display = ticks_display.rename(
                columns={
                    "time": "Thời gian (time)",
                    "price": "Giá khớp (price)",
                    "volume": "Khối lượng (volume)",
                    "side": "Bên giao dịch (side)",
                }
            )
            st.dataframe(ticks_display.tail(200), use_container_width=True)
            _download_df(ticks_display, "⬇️ Tải toàn bộ lệnh khớp — tệp bảng (CSV)",
                         f"intraday_{result_symbol}.csv")

        st.caption(
            "Số liệu này chỉ phục vụ quan sát và nghiên cứu. Công cụ không đặt lệnh "
            "và không đưa ra khuyến nghị mua/bán."
        )


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
        m2.metric("Beta (độ nhạy) trung bình", f"{betas.mean():.2f}")
        m3.metric("Mã năng động nhất", top_beta_row['Mã CP'], f"β = {top_beta_row['Beta (Độ nhạy)']:.2f}")
        m4.metric("R² trung bình", f"{sim_df['R^2'].mean():.2%}")

        st.subheader("Bảng mô hình chỉ số đơn (SIM)")

        def _hl_beta(v):
            if v > 1:
                return 'color:#ff6b6b; font-weight:600'
            return 'color:#00c48c; font-weight:600'
        sim_display = sim_df.rename(
            columns={
                "Alpha": "Alpha (lợi suất riêng)",
                "White p-value": "Giá trị p kiểm định White",
                "B-G p-value": "Giá trị p kiểm định B-G",
                "RESET p-value": "Giá trị p kiểm định RESET",
                "JB p-value": "Giá trị p kiểm định JB",
            }
        ).replace(
            {
                "N/A": "Không áp dụng (N/A)",
                "ok": "Đạt (ok)",
                "warning": "Cảnh báo (warning)",
                "unknown": "Không rõ (unknown)",
            }
        )
        styled = sim_display.style.map(_hl_beta, subset=['Beta (Độ nhạy)']).format({
            'Beta (Độ nhạy)': '{:.3f}', 'Alpha (lợi suất riêng)': '{:.5f}', 'Rủi ro Hệ thống': '{:.5f}',
            'Rủi ro Phi hệ thống': '{:.5f}', 'Tổng Rủi ro': '{:.5f}', 'R^2': '{:.3f}',
            'Giá trị p kiểm định White': '{:.4f}', 'Giá trị p kiểm định B-G': '{:.4f}',
            'Giá trị p kiểm định RESET': '{:.4f}', 'Giá trị p kiểm định JB': '{:.4f}',
        }, na_rep='Không áp dụng (N/A)')
        st.dataframe(styled, width="stretch")
        _download_df(sim_display, "⬇️ Tải bảng mô hình chỉ số đơn (SIM) — tệp bảng (CSV)", "sim_results.csv")

        with st.expander("📚 Giải thích ý nghĩa các chỉ số Kinh tế lượng"):
            st.markdown("""
*   **Beta (độ nhạy, $\\beta$):** Đo mức biến động của cổ phiếu so với thị trường. $\\beta>1$: *năng động* (rủi ro & kỳ vọng cao); $\\beta<1$: *thụ động* (an toàn hơn).
*   **Alpha (lợi suất riêng, $\\alpha$):** Lợi suất vượt trội do yếu tố riêng của cổ phiếu.
*   **Rủi ro Hệ thống:** Do biến động chung của thị trường (không thể đa dạng hoá để loại bỏ).
*   **Rủi ro Phi hệ thống:** Do đặc thù công ty (loại bỏ được bằng đa dạng hoá).
*   **R² :** Tỷ lệ biến động giá cổ phiếu được giải thích bởi VNINDEX.
*   **Kiểm định White (White test):** `Yes` (Có) = có phương sai sai số thay đổi (cần sai số chuẩn vững).
*   **Kiểm định Breusch-Godfrey:** `Yes` (Có) = có tự tương quan chuỗi.\n*   **Dạng hàm (Ramsey RESET):** 'Có thể có' = mô hình có thể bị sai dạng hàm / bỏ sót biến (Chương 5).\n*   **Phân phối chuẩn (Jarque-Bera):** 'Không chuẩn' = phần dư không phân phối chuẩn, ảnh hưởng suy diễn thống kê mẫu nhỏ.
            """)

        st.subheader("Biểu đồ hồi quy mô hình chỉ số đơn (SIM)")
        selected_ticker = st.selectbox("Chọn cổ phiếu để xem biểu đồ hồi quy:", valid_assets)
        if selected_ticker in returns_df.columns:
            fig = px.scatter(returns_df, x=market_ticker, y=selected_ticker, trendline="ols",
                             title=f"Hồi quy {selected_ticker} theo {market_ticker}",
                             labels={market_ticker: f"Lợi suất {market_ticker}", selected_ticker: f"Lợi suất {selected_ticker}"})
            fig.update_traces(marker=dict(color="#00A67E", opacity=0.5))
            st.plotly_chart(fig, width="stretch")


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
            st.caption("Biến động tối thiểu (Min Volatility) — rủi ro thấp nhất")
            min_vol_df = pd.DataFrame({'Tài sản': opt_res['assets'], 'Tỷ trọng': opt_res['min_vol_weights']})
            fig_mv = px.pie(min_vol_df, values='Tỷ trọng', names='Tài sản', hole=0.45,
                            color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig_mv, width="stretch")
        with c2:
            st.subheader("🚀 Danh mục Hiệu quả nhất")
            st.caption("Chỉ số Sharpe tối đa (Max Sharpe) trong mô hình — có thể chọn tiền mặt")
            max_sharpe_assets = list(opt_res['assets']) + ['Tiền mặt']
            max_sharpe_values = list(opt_res['max_sharpe_weights']) + [
                float(opt_res.get('max_sharpe_cash_weight', 0.0))
            ]
            max_sharpe_df = pd.DataFrame({'Tài sản': max_sharpe_assets, 'Tỷ trọng': max_sharpe_values})
            max_sharpe_df = max_sharpe_df[max_sharpe_df['Tỷ trọng'] > 1e-10]
            fig_ms = px.pie(max_sharpe_df, values='Tỷ trọng', names='Tài sản', hole=0.45,
                            color_discrete_sequence=px.colors.sequential.Agsunset)
            st.plotly_chart(fig_ms, width="stretch")

        w_table = pd.DataFrame({
            'Tài sản': list(opt_res['assets']) + ['Tiền mặt'],
            'Biến động tối thiểu (Min Volatility, %)': np.append(np.array(opt_res['min_vol_weights']) * 100, 0.0).round(2),
            'Sharpe tối đa (Max Sharpe, %)': np.append(
                np.array(opt_res['max_sharpe_weights']) * 100,
                float(opt_res.get('max_sharpe_cash_weight', 0.0)) * 100,
            ).round(2),
        })
        st.dataframe(w_table, width="stretch")
        _download_df(w_table, "⬇️ Tải tỷ trọng danh mục — tệp bảng (CSV)", "portfolio_weights.csv")

        q1, q2, q3 = st.columns(3)
        q1.metric("Số phiên hợp lệ", int(opt_res.get('n_observations', len(returns_df))))
        q2.metric("Lãi suất phi rủi ro", f"{float(opt_res.get('risk_free_rate', 0.04)):.2%}")
        q3.metric("Điều chỉnh hiệp phương sai (covariance)", f"{float(opt_res.get('covariance_regularization', 0.0)):.2e}")

        st.subheader("Đường Biên hiệu quả (Efficient Frontier)")
        # Toạ độ 2 danh mục tối ưu để đánh dấu sao
        mean_ret = returns_df[valid_assets].mean() * 252
        cov = returns_df[valid_assets].cov() * 252

        def _perf(w, cash_weight=0.0):
            w = np.array(w)
            expected = float(mean_ret.values @ w) + float(cash_weight) * float(opt_res.get('risk_free_rate', 0.04))
            return float(np.sqrt(max(w @ cov.values @ w, 0.0))), expected
        mv_std, mv_ret = _perf(opt_res['min_vol_weights'])
        ms_std, ms_ret = _perf(
            opt_res['max_sharpe_weights'], opt_res.get('max_sharpe_cash_weight', 0.0)
        )

        ef_fig = go.Figure()
        ef_fig.add_trace(go.Scatter(x=opt_res['ef_vols'], y=opt_res['ef_rets'], mode='markers',
                                    marker=dict(color=opt_res['ef_sharpes'], colorscale='Viridis',
                                                showscale=True, size=6, colorbar=dict(title="Chỉ số Sharpe")),
                                    name='Danh mục rủi ro mô phỏng'))
        ef_fig.add_trace(go.Scatter(x=[mv_std], y=[mv_ret], mode='markers',
                                    marker=dict(color='#4dd0e1', size=18, symbol='star',
                                                line=dict(color='white', width=1)),
                                    name='🛡️ Biến động tối thiểu (Min Volatility)'))
        ef_fig.add_trace(go.Scatter(x=[ms_std], y=[ms_ret], mode='markers',
                                    marker=dict(color='#ffd166', size=18, symbol='star',
                                                line=dict(color='white', width=1)),
                                    name='🚀 Sharpe tối đa (Max Sharpe)'))
        ef_fig.update_layout(title='Không gian danh mục rủi ro và phương án tiền mặt',
                             xaxis_title='Rủi ro (Độ lệch chuẩn năm hoá)',
                             yaxis_title='Lợi suất kỳ vọng (năm hoá)',
                             legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(ef_fig, width="stretch")


# ---------- TAB 3: AI ----------
with tab3:
    if not has_data:
        st.info("👈 Chạy **Phân tích** trước để nhận khuyến nghị.")
    else:
        st.subheader("Trợ lý quyết định có điều kiện")
        st.caption("Máy tính tạo số liệu; trí tuệ nhân tạo (AI) chỉ diễn giải. Mọi kế hoạch phải có điểm vô hiệu, giới hạn lỗ và ngày hết hiệu lực.")
        sim_results_list = st.session_state.sim_results_list
        opt_res = st.session_state.opt_res
        prices_df = st.session_state.prices_df
        market_ticker = st.session_state.market_ticker
        rule_advice = generate_expert_advice(sim_results_list, opt_res, prices_df[market_ticker])
        st.markdown(rule_advice)

        if ai_config and ai_config.get('api_key'):
            cache_material = (
                f"{ai_provider}|{ai_config.get('model')}|{st.session_state.get('data_last_date')}|"
                f"{','.join(st.session_state.valid_assets)}"
            )
            advice_key = hashlib.sha256(cache_material.encode('utf-8')).hexdigest()
            if st.button("Tạo bản diễn giải bằng trí tuệ nhân tạo (AI)", width="stretch", type="primary", key="generate_investment_advice"):
                with st.spinner(f"Đang chờ {ai_provider} diễn giải kết quả đã kiểm định..."):
                    st.session_state.advice_cache[advice_key] = generate_expert_advice(
                        sim_results_list, opt_res, prices_df[market_ticker], ai_config
                    )
            if advice_key in st.session_state.advice_cache:
                st.markdown("#### Bản diễn giải bằng trí tuệ nhân tạo (AI)")
                st.markdown(st.session_state.advice_cache[advice_key])
        else:
            st.info("Nhập khóa API nếu muốn trí tuệ nhân tạo (AI) diễn giải sâu hơn. Phần tính toán định lượng vẫn chạy cục bộ.")

        st.warning(
            "Không dùng phần này làm lệnh mua/bán trực tiếp. Hãy kiểm tra thẻ kiểm thử quá khứ (backtest), "
            "mức sụt giảm (drawdown), phí giao dịch và danh mục mô phỏng (paper portfolio) trước."
        )


# ---------- TAB 4: EVIEWS ----------
with tab4:
    st.subheader("📈 Eviews tiếng Việt (Giả lập)")
    st.markdown("Tải tệp (file), chọn trang tính (sheet), rồi dùng trình đơn (menu) **Chọn nhanh** hoặc gõ lệnh EViews. "
                "Hỗ trợ: `LS` (hồi quy bình phương tối thiểu), `GENR` (tạo biến: LOG/D/trễ X(-1)/@TREND), "
                "`ADF` (kiểm định nghiệm đơn vị), `STATS` (thống kê mô tả), `COR` (tương quan), "
                "`PLOT/SCAT/HIST` (đồ thị đường/phân tán/tần suất).")
    from eviews_emulator import parse_and_execute_command, format_eviews_output

    col_ev1, col_ev2 = st.columns([1, 2])
    with col_ev1:
        st.markdown("#### 📂 Tệp làm việc (Workfile)")
        uploaded_file = st.file_uploader("Tải tệp dữ liệu dạng bảng (CSV/Excel)", type=["csv", "xlsx", "xls"])

        if uploaded_file is not None:
            raw_bytes = uploaded_file.getvalue()
            fname = uploaded_file.name

            def _mkbuf():
                b = io.BytesIO(raw_bytes); b.name = fname; return b

            sheets = dc.list_sheets(_mkbuf())
            chosen_sheet = None
            if sheets:
                st.caption(f"📑 Tệp có **{len(sheets)}** trang tính (sheet).")
                chosen_sheet = st.selectbox("Chọn trang tính (sheet) để làm việc:", sheets)
            mode_label = st.radio("Cách đọc dữ liệu:",
                                  ["Tự động (thông minh)", "Thô (nguyên bản)"], horizontal=True)
            mode = 'auto' if mode_label.startswith("Tự") else 'raw'

            if st.button("📥 Nạp dữ liệu", width="stretch"):
                try:
                    df, report = dc.smart_import(_mkbuf(), sheet=chosen_sheet, mode=mode)
                    st.session_state.eviews_data = df
                    st.success("Nạp dữ liệu thành công!")
                    st.info(report)
                except Exception as e:
                    st.error(f"Lỗi đọc tệp (file): {e}")

        if not st.session_state.eviews_data.empty:
            st.markdown("**Các biến trong bộ nhớ:**")
            st.write(", ".join(map(str, st.session_state.eviews_data.columns.tolist())))
            with st.expander("👁️ Xem trước dữ liệu"):
                st.dataframe(st.session_state.eviews_data.head(20), width="stretch")
        else:
            st.info("Chưa có dữ liệu. Hãy tải tệp (file) và bấm **Nạp dữ liệu**.")

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
                    "Hồi quy bình phương tối thiểu (OLS) / Ước lượng mô hình chỉ số đơn (SIM, lệnh LS)",
                    "Tạo biến mới (GENR)",
                    "Kiểm định nghiệm đơn vị (ADF)",
                    "Thống kê mô tả (STATS)",
                    "Ma trận tương quan (COR)",
                    "Vẽ đồ thị (đường/phân tán/tần suất)",
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
                elif op.startswith("Tạo biến"):
                    st.caption("Có thể dùng hàm: LOG() (logarit), D() (sai phân), biến trễ X(-1), @TREND (xu hướng), hoặc điều kiện tạo biến giả (ví dụ: BID>20).")
                    newname = st.text_input("Tên biến mới:", "Z")
                    gmode = st.radio("Kiểu tạo:", ["Hai biến + phép toán", "Tự gõ biểu thức"],
                                     horizontal=True, key="genr_mode")
                    if gmode.startswith("Hai"):
                        cc1, cc2, cc3 = st.columns(3)
                        v1 = cc1.selectbox("Biến 1:", cols_list, key="genr_v1")
                        opr = cc2.selectbox("Phép toán:", ["+", "-", "*", "/"], key="genr_op")
                        v2 = cc3.selectbox("Biến 2:", cols_list, key="genr_v2")
                        expr = f"{v1} {opr} {v2}"
                    else:
                        expr = st.text_input("Biểu thức (ví dụ: LOG(BID) - LOG(BID(-1))):",
                                             f"LOG({cols_list[0]})", key="genr_expr")
                    if newname.strip() and expr.strip():
                        command_to_run = f"GENR {newname.strip()} = {expr}"
                elif op.startswith("Kiểm định nghiệm"):
                    st.caption("Kiểm định chuỗi có DỪNG không (nghiệm đơn vị) — dùng cho số liệu chuỗi thời gian.")
                    v = st.selectbox("Chọn biến:", cols_list, key="adf_v")
                    command_to_run = f"ADF {v}"
                elif op.startswith("Thống kê"):
                    vs = st.multiselect("Chọn biến (bỏ trống = tất cả):", cols_list, key="stats_v")
                    command_to_run = "STATS " + " ".join(vs) if vs else "STATS"
                elif op.startswith("Ma trận tương quan"):
                    vs = st.multiselect("Chọn biến (≥2, bỏ trống = tất cả):", cols_list, key="cor_v")
                    command_to_run = "COR " + " ".join(vs) if vs else "COR"
                else:  # Vẽ đồ thị
                    gtype = st.selectbox("Loại đồ thị:",
                                         ["Đường (line)", "Phân tán (scatter)", "Tần suất (histogram)"],
                                         key="plot_type_sel")
                    if gtype.startswith("Phân"):
                        c1p, c2p = st.columns(2)
                        vx = c1p.selectbox("Trục X:", cols_list, key="plot_x")
                        vy = c2p.selectbox("Trục Y:", cols_list,
                                           index=min(1, len(cols_list) - 1), key="plot_y")
                        command_to_run = f"SCAT {vx} {vy}"
                    elif gtype.startswith("Tần"):
                        vh = st.selectbox("Biến:", cols_list, key="plot_h")
                        command_to_run = f"HIST {vh}"
                    else:
                        vs = st.multiselect("Chọn 1 hoặc nhiều biến:", cols_list,
                                            default=cols_list[:1], key="plot_l")
                        if vs:
                            command_to_run = "PLOT " + " ".join(vs)

                if command_to_run:
                    st.caption("📋 Câu lệnh EViews tương ứng (học thuộc để sau tự gõ tay):")
                    st.code(command_to_run, language="text")
                    run_now = st.button("▶️ Xem kết quả", width="stretch", type="primary")
            else:
                command_to_run = st.text_input(
                    "Nhập lệnh (ví dụ: LS Y C X | GENR Z=LOG(X) | ADF X | STATS X | COR | PLOT X Y):", key="eviews_cmd")
                run_now = st.button("▶️ Chạy lệnh", width="stretch")

            deep_ai = st.checkbox("🤖 Kèm phân tích chuyên sâu bằng trí tuệ nhân tạo (AI) — cần khóa API ở thanh bên (sidebar)")

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
                    elif res.get("plot"):
                        st.markdown("##### 📈 Đồ thị")
                        render_eviews_plot(res["plot"])
                    elif res.get("message"):
                        st.success(res["message"])
                        with st.expander("👁️ Xem dữ liệu sau khi tạo biến"):
                            st.dataframe(st.session_state.eviews_data.head(20), width="stretch")
                    else:
                        st.markdown("##### 📤 Kết quả (Output)")
                        html_output = format_eviews_output(res)
                        st.components.v1.html(html_output, height=460, scrolling=True)

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
                                with st.spinner("Trí tuệ nhân tạo (AI) đang phân tích chuyên sâu..."):
                                    out = call_llm(prompt, ai_config)
                                if out:
                                    st.markdown("##### 🤖 Phân tích chuyên sâu bằng trí tuệ nhân tạo (AI)")
                                    st.markdown(out)
                            else:
                                st.warning("Hãy nhập khóa API ở thanh bên (sidebar), mục Tích hợp trí tuệ nhân tạo (AI), để dùng phân tích chuyên sâu.")


# ---------- TAB 5: ÔN THI ----------
with tab5:
    st.subheader("🎓 Công cụ Ôn thi Kinh tế lượng")
    st.markdown("Tính nhanh các đại lượng để làm bài kiểm tra thực hành. Dùng chung dữ liệu đã nạp ở thẻ (tab) **EViews**.")
    from exam_calculator import (
        calc_return_formula, calc_returns_data,
        calc_sim_risks_formula, calc_sim_risks_data,
        calc_cov_matrix_formula, calc_cov_matrix_data,
        calc_markowitz_params_formula, calc_markowitz_params_data
    )

    if st.session_state.eviews_data.empty:
        st.info("Hãy nạp tệp (file) số liệu ở thẻ (tab) **📈 EViews tiếng Việt** để dùng công cụ tính nhanh.")
    else:
        exam_data = st.session_state.eviews_data
        with st.expander("👁️ Dữ liệu hiện tại"):
            st.dataframe(exam_data.head(20), width="stretch")

        st.caption("💡 Chọn **cột giá** (không phải cột r_...) làm tài sản (Asset) và thị trường (Market) — công cụ tự tính lợi suất.")
        c1, c2 = st.columns(2)
        selected_asset = c1.selectbox("Mã cổ phiếu — tài sản (Asset):", exam_data.columns)
        selected_market = c2.selectbox("Chỉ số thị trường (Market):", exam_data.columns,
                                       index=min(1, len(exam_data.columns) - 1))

        st.markdown("##### Các lệnh tính nhanh")
        b1, b2 = st.columns(2)
        b3, b4 = st.columns(2)

        if b1.button("1️⃣ Tỷ suất Sinh lời", width="stretch"):
            st.latex(calc_return_formula())
            try:
                ret = calc_returns_data(exam_data[selected_asset])
                st.write(f"Lợi suất của **{selected_asset}** (5 ngày đầu):")
                st.dataframe(ret.head())
            except Exception as e:
                st.error(f"Lỗi: {e}. Đảm bảo cột là dạng số hợp lệ.")

        if b2.button("2️⃣ Rủi ro hệ thống / phi hệ thống — mô hình chỉ số đơn (SIM)", width="stretch"):
            st.latex(calc_sim_risks_formula())
            try:
                r_asset = calc_returns_data(exam_data[selected_asset])
                r_market = calc_returns_data(exam_data[selected_market])
                risks = calc_sim_risks_data(r_asset, r_market)
                st.write(f"Kết quả **{selected_asset}** so với **{selected_market}**:")
                risk_labels = {
                    "Beta": "Beta (độ nhạy)",
                    "Sys_Risk": "Rủi ro hệ thống (systematic risk)",
                    "Unsys_Risk": "Rủi ro phi hệ thống (unsystematic risk)",
                    "Total_Risk": "Tổng rủi ro (total risk)",
                    "Market_Var": "Phương sai thị trường (market variance)",
                }
                st.json({risk_labels.get(k, k): float(v) for k, v in risks.items()})
            except Exception as e:
                st.error(f"Lỗi: {e}")

        if b3.button("3️⃣ Ma trận Hiệp phương sai (V)", width="stretch"):
            st.latex(calc_cov_matrix_formula())
            try:
                numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
                returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
                st.dataframe(calc_cov_matrix_data(returns_all), width="stretch")
            except Exception as e:
                st.error(f"Lỗi: {e}")

        if b4.button("4️⃣ Đại lượng Markowitz (A,B,C,D)", width="stretch"):
            st.latex(calc_markowitz_params_formula())
            try:
                numeric_cols = exam_data.select_dtypes(include=[np.number]).columns
                returns_all = exam_data[numeric_cols].apply(calc_returns_data).dropna()
                params = calc_markowitz_params_data(returns_all)
                st.json({k: float(v) if not isinstance(v, str) else v for k, v in params.items()})
            except Exception as e:
                st.error(f"Lỗi: {e}")

        # ===== Danh mục theo trọng số W =====
        st.markdown("---")
        st.markdown("##### 🧺 Danh mục theo trọng số cho trước (W)")
        st.caption("Chọn các mã (cột GIÁ), số quan sát, thứ tự ngày và nhập trọng số → ra lợi suất TB & rủi ro danh mục.")
        num_cols = list(exam_data.select_dtypes(include=[np.number]).columns)
        if len(num_cols) < 1:
            st.info("Không có cột số hợp lệ trong dữ liệu.")
        else:
            pf_assets = st.multiselect("Các mã trong danh mục (cột giá):", num_cols, key="pf_assets")
            pc1, pc2 = st.columns(2)
            pf_n = pc1.number_input("Số quan sát đầu (0 = tất cả):", min_value=0, value=0, step=1, key="pf_n")
            pf_order = pc2.radio("Thứ tự ngày trong file:", ["Giữ nguyên", "Đảo ngược (cũ → mới)"],
                                 key="pf_order", horizontal=True)
            pc3, pc4 = st.columns(2)
            pf_isret = pc3.checkbox("Dữ liệu đã là lợi suất", key="pf_isret",
                                    help="Đánh dấu (tick) nếu cột đã là r_... để không tính lợi suất lại.")
            pf_ddofr = pc4.radio("Kiểu phương sai:", ["Mẫu ÷(n−1)", "Tổng thể ÷n"],
                                 key="pf_ddof", horizontal=True,
                                 help="Bảng Excel của giảng viên thường dùng Tổng thể ÷n; EViews dùng Mẫu ÷(n−1).")
            if pf_assets:
                st.caption("Nhập trọng số W cho từng mã:")
                wcols = st.columns(len(pf_assets))
                pf_weights = []
                for i, a in enumerate(pf_assets):
                    wv = wcols[i].number_input(a, value=round(1.0 / len(pf_assets), 4),
                                               step=0.05, format="%.4f", key=f"pf_w_{a}")
                    pf_weights.append(wv)
                pf_norm = st.checkbox("Tự chuẩn hoá W về tổng = 1", value=True, key="pf_norm")
                if st.button("📊 Tính danh mục", width="stretch", type="primary", key="pf_btn"):
                    try:
                        res = compute_portfolio(exam_data, pf_assets, pf_weights,
                                                nobs=pf_n, reverse=pf_order.startswith("Đảo"),
                                                normalize=pf_norm, is_returns=pf_isret,
                                                ddof=(1 if pf_ddofr.startswith("Mẫu") else 0))
                        st.caption(f"Dùng {res['n_prices']} giá → {res['n_returns']} lợi suất. "
                                   f"Trọng số áp dụng: " + ", ".join(f"{a}={w:.4f}" for a, w in zip(res['assets'], res['weights'])))
                        mA, mB, mC = st.columns(3)
                        mA.metric("Lợi suất TB danh mục", f"{res['mean']*100:.4f}%")
                        mB.metric("Rủi ro (độ lệch chuẩn)", f"{res['std']*100:.4f}%")
                        mC.metric("Phương sai danh mục", f"{res['variance']:.8f}")
                        st.write("Lợi suất trung bình từng mã:")
                        st.dataframe((res['asset_means'] * 100).round(4).rename("Lợi suất TB (%)"),
                                     width="stretch")
                        st.write("Ma trận hiệp phương sai V:")
                        st.dataframe(res['cov'], width="stretch")
                        direction = "âm (danh mục giảm giá trong kỳ)" if res['mean'] < 0 else "dương (danh mục tăng giá)"
                        st.markdown(
                            f"**Diễn giải:** Lợi suất trung bình danh mục ≈ **{res['mean']*100:.4f}%/phiên** ({direction}); "
                            f"rủi ro (độ lệch chuẩn) ≈ **{res['std']*100:.4f}%**. "
                            f"Tính bằng r_P = Σ wᵢ·rᵢ rồi lấy trung bình & độ lệch chuẩn — bằng đúng W'VW. "
                            f"\n\n> ⚠️ Lợi suất TB đổi dấu nếu thay đổi thứ tự ngày; rủi ro không đổi.")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

        # ===== Rủi ro danh mục theo mô hình SIM =====
        st.markdown("---")
        st.markdown("##### 🎯 Rủi ro danh mục theo mô hình chỉ số đơn (SIM): hệ thống / phi hệ thống")
        st.caption("Chọn các mã + chỉ số thị trường + trọng số → ứng dụng chạy mô hình chỉ số đơn (SIM) từng mã, tách rủi ro hệ thống và phi hệ thống của danh mục.")
        num_cols2 = list(exam_data.select_dtypes(include=[np.number]).columns)
        s_assets = st.multiselect("Các mã trong danh mục:", num_cols2, key="sim_assets")
        sc1, sc2 = st.columns(2)
        s_market = sc1.selectbox("Chỉ số thị trường:", num_cols2,
                                 index=len(num_cols2) - 1 if num_cols2 else 0, key="sim_market")
        s_n = sc2.number_input("Số quan sát đầu (0 = tất cả):", min_value=0, value=0, step=1, key="sim_n")
        sc3, sc4 = st.columns(2)
        s_isret = sc3.checkbox("Dữ liệu đã là lợi suất", key="sim_isret")
        s_order = sc4.radio("Thứ tự ngày:", ["Giữ nguyên", "Đảo ngược"], key="sim_order", horizontal=True)
        if s_assets and s_market:
            st.caption("Nhập trọng số W cho từng mã:")
            swcols = st.columns(len(s_assets))
            s_weights = []
            for i, a in enumerate(s_assets):
                wv = swcols[i].number_input(a, value=round(1.0 / len(s_assets), 4),
                                            step=0.05, format="%.4f", key=f"sim_w_{a}")
                s_weights.append(wv)
            s_norm = st.checkbox("Tự chuẩn hoá W về tổng = 1", value=True, key="sim_norm")
            if st.button("🎯 Tính rủi ro danh mục theo mô hình chỉ số đơn (SIM)", width="stretch", type="primary", key="sim_btn"):
                try:
                    r = compute_sim_portfolio_risk(exam_data, s_assets, s_market, s_weights,
                                                   nobs=s_n, reverse=s_order.startswith("Đảo"),
                                                   normalize=s_norm, is_returns=s_isret)
                    st.caption(f"{r['n_returns']} lợi suất | σ²_thị trường = {r['sigma_market2']:.8f} | "
                               f"Beta danh mục β_P = {r['beta_p']:.6f}")
                    st.write("Chi tiết từng cổ phiếu theo mô hình chỉ số đơn (SIM):")
                    sim_detail = pd.DataFrame(r['per_stock']).rename(
                        columns={"Beta": "Beta (độ nhạy)"}
                    )
                    st.dataframe(sim_detail, width="stretch")
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Rủi ro hệ thống", f"{r['systematic']:.8f}")
                    k2.metric("Rủi ro phi hệ thống", f"{r['unsystematic']:.8f}")
                    k3.metric("TỔNG rủi ro danh mục", f"{r['total']:.8f}")
                    st.markdown(
                        f"**Diễn giải:** Rủi ro danh mục P theo mô hình chỉ số đơn (SIM) = **{r['total']:.8f}** "
                        f"(= hệ thống {r['systematic']:.8f} + phi hệ thống {r['unsystematic']:.8f}); "
                        f"độ lệch chuẩn ≈ **{r['total_std']*100:.4f}%**. "
                        f"Hệ thống = β²_P·σ²_I; phi hệ thống = Σ wᵢ²·ηᵢ² "
                        f"(ηᵢ² = phương sai phần dư hồi quy mô hình chỉ số đơn, SIM).")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    # ===== Trợ lý học tập an toàn (không thực thi mã do AI sinh) =====
    st.markdown("---")
    st.markdown("#### Trợ lý học tập — tính cục bộ, trí tuệ nhân tạo (AI) chỉ diễn giải")
    st.caption("Các phép tính chạy bằng bộ công cụ cố định đã kiểm thử. Ứng dụng không chạy mã Python do trí tuệ nhân tạo (AI) sinh ra.")

    ai_upload = st.file_uploader("Tải tệp (file) dữ liệu — bỏ trống thì dùng dữ liệu ở thẻ (tab) EViews:",
                                 type=["csv", "xlsx", "xls"], key="ai_upload")
    ai_df = None
    if ai_upload is not None:
        _raw_b = ai_upload.getvalue(); _fn = ai_upload.name

        def _aibuf():
            b = io.BytesIO(_raw_b); b.name = _fn; return b
        _sheets = dc.list_sheets(_aibuf())
        _chosen = st.selectbox("Chọn trang tính (sheet):", _sheets, key="ai_sheet") if _sheets else None
        try:
            ai_df, _ = dc.smart_import(_aibuf(), sheet=_chosen, mode='auto')
            st.success(f"Đã đọc dữ liệu cục bộ ({ai_df.shape[0]} dòng, {ai_df.shape[1]} cột).")
        except Exception as e:
            st.error(f"Lỗi đọc tệp (file): {e}")
    elif not st.session_state.eviews_data.empty:
        ai_df = st.session_state.eviews_data
        st.caption("→ Đang dùng dữ liệu đã nạp ở thẻ (tab) EViews.")
    else:
        st.info("Tải tệp (file) ở đây, hoặc nạp ở thẻ (tab) EViews để trí tuệ nhân tạo (AI) có dữ liệu làm việc.")

    ai_req = st.text_area("Yêu cầu / đề bài của bạn:",
                          placeholder="VD: Với 200 quan sát đầu, tính danh mục GAS HDB HPG "
                                      "W=(0.25;0.45;0.30) và ma trận hiệp phương sai.",
                          key="ai_req")
    allow_ai_explanation = False
    if ai_config and ai_config.get('api_key'):
        allow_ai_explanation = st.checkbox(
            "Cho phép gửi yêu cầu và kết quả tính đã rút gọn tới nhà cung cấp (provider) AI để diễn giải",
            value=False,
            help="Không gửi các dòng dữ liệu thô; chỉ gửi yêu cầu, giả định và kết quả định lượng rút gọn.",
            key="allow_ai_explanation",
        )
    if st.button("Tính và giải thích", width="stretch", type="primary", key="ai_calc_btn"):
        if ai_df is None:
            st.warning("Chưa có dữ liệu — tải tệp (file) hoặc nạp ở thẻ (tab) EViews.")
        elif not ai_req.strip():
            st.warning("Hãy nhập yêu cầu.")
        else:
            explanation_config = ai_config if allow_ai_explanation else None
            with st.spinner("Đang chạy phép tính đã kiểm định..."):
                out = run_ai_analysis(ai_df, ai_req, explanation_config)
            if out.get("narrative"):
                st.markdown(out["narrative"])
            if out.get("assumptions"):
                with st.expander("Giả định đã áp dụng"):
                    for assumption in out["assumptions"]:
                        st.write(f"- {assumption}")
            if out.get("error"):
                st.error(out["error"])
            res = out.get("result")
            if res is not None:
                st.write("**Kết quả tính:**")
                if isinstance(res, (pd.DataFrame, pd.Series)):
                    st.dataframe(res, width="stretch")
                elif isinstance(res, dict):
                    for _k, _v in res.items():
                        if isinstance(_v, (pd.DataFrame, pd.Series)):
                            st.write(f"**{_k}:**"); st.dataframe(_v, width="stretch")
                        elif isinstance(_v, (int, float, np.floating, np.integer)):
                            st.write(f"**{_k}:** {float(_v):.6g}")
                        else:
                            st.write(f"**{_k}:** {_v}")
                else:
                    st.write(res)
            st.caption("Phép tính là cục bộ; phần diễn giải bằng trí tuệ nhân tạo (AI), nếu bật, vẫn cần được kiểm chứng trước khi nộp bài.")
