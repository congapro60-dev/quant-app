"""Task entry points and historical-data views; no provider or AI calls."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import curriculum as cur
import curriculum_university as uni
import learning_modes as lmode

HOME = "tong_quan"
HOME_LABEL = "Tổng quan"
NAV_KEY = "workspace_tabs"
HISTORY = "history"
HISTORY_LABEL = "Lịch sử giá cuối ngày"
MUSE_LABEL = "Soạn học liệu với Muse"


def navigate_to(area: str, feature: str | None = None) -> None:
    """Use as an on_click callback, before keyed tabs are rendered."""
    if area not in lmode.visible_areas(st.session_state) and area != HOME:
        return
    if feature in lmode.FEATURES and feature not in lmode.visible_features(st.session_state):
        return
    st.session_state[NAV_KEY] = HOME_LABEL if area == HOME else lmode.AREA_LABELS[area]
    if area == lmode.AREA_LEARNING and feature is None:
        feature = "Bài học và thực hành"
    if feature:
        label = HISTORY_LABEL if feature == HISTORY else lmode.FEATURES.get(feature, {}).get("label", feature)
        st.session_state[f"tools_{area}"] = label


def workspace_tabs(labels: list[str], key: str):
    if st.session_state.get(key) not in labels:
        st.session_state[key] = labels[0]
    return st.tabs(labels, key=key, on_change="rerun")


def render_overview() -> None:
    mode = lmode.get_mode(st.session_state)
    lessons = uni.all_lessons() if mode == lmode.MODE_UNIVERSITY else cur.all_lessons()
    scores = st.session_state.get("progress_profile", {}).get("lesson_scores", {})
    done = sum(scores.get(lesson.lesson_id, 0) >= cur.UNLOCK_THRESHOLD for lesson in lessons)
    prices = st.session_state.get("prices_df", pd.DataFrame())
    ready = st.session_state.get("data_status") == "ok" and not prices.empty
    st.markdown('<div class="qa-eyebrow">KHÔNG GIAN HỌC & NGHIÊN CỨU</div>', unsafe_allow_html=True)
    st.header("Hôm nay, bạn muốn làm gì?")
    st.caption("Chọn một việc để bắt đầu. Công cụ tính toán và bài học không cần khóa AI.")
    actions = (
        ("01 · HỌC", "Hiểu trước khi đầu tư", "Bài học ngắn, ví dụ có lời giải, câu hỏi tự kiểm tra.",
         "Tiếp tục học", lmode.AREA_LEARNING, None),
        ("02 · NGHIÊN CỨU", "Đọc dữ liệu thị trường", "Nạp mã cổ phiếu, xem lịch sử giá, so sánh biến động.",
         "Phân tích dữ liệu", lmode.AREA_DATA, HISTORY),
        ("03 · THỰC HÀNH", "Thử bằng vốn mô phỏng", "Ghi nhận mua bán giả lập, theo dõi lãi/lỗ và phí.",
         "Mở danh mục mô phỏng", lmode.AREA_INVEST, lmode.FEATURE_PAPER),
    )
    for col, (eyebrow, title, detail, action, area, feature) in zip(st.columns(3), actions):
        with col, st.container(border=True):
            st.caption(eyebrow)
            st.subheader(title)
            st.write(detail)
            st.button(action, key=f"start_{area}", on_click=navigate_to,
                      args=(area, feature), width="stretch", type="primary")
    st.subheader("Công việc của bạn")
    progress, market, journal = st.columns(3)
    progress.metric("Bài học đạt yêu cầu", f"{done}/{len(lessons)}")
    market.metric("Dữ liệu thị trường", "Đã nạp" if ready else "Chưa sẵn sàng")
    ledger = st.session_state.get("paper_ledger") or {}
    journal.metric("Giao dịch mô phỏng", len(ledger.get("fills", [])))
    if ready:
        st.caption(f"Phiên cuối: {pd.Timestamp(prices.index.max()):%d/%m/%Y} · "
                   f"{len(prices)} phiên · {len(st.session_state.get('valid_assets', []))} cổ phiếu. "
                   "Dữ liệu cuối ngày (EOD), không phải báo giá trực tiếp.")
    else:
        st.caption("Lộ trình học và danh mục mô phỏng vẫn dùng được khi nguồn giá chưa sẵn sàng.")
    st.button("Xem tiến độ và sao lưu", on_click=navigate_to,
              args=(lmode.AREA_JOURNAL,), key="overview_progress")
    with st.expander("Có thể tận dụng Muse vào việc gì?"):
        st.write("Soạn bài tự học, lên kịch bản hình/video minh họa, tổng hợp nghiên cứu công khai có nguồn. "
                 "Bắt đầu bằng bản yêu cầu học liệu từ bài học có sẵn trong Quant App.")
        st.button("Soạn yêu cầu cho Muse", on_click=navigate_to,
                  args=(lmode.AREA_LEARNING, MUSE_LABEL), key="overview_muse")


def history_view(prices: pd.DataFrame, symbols: list[str], *, rebase: bool) -> pd.DataFrame:
    """Reject invalid inputs rather than plotting a misleading comparison."""
    if not symbols or len(set(symbols)) != len(symbols) or any(s not in prices for s in symbols):
        raise ValueError("Chọn ít nhất một mã có trong dữ liệu đã nạp.")
    frame = prices.loc[:, symbols].apply(pd.to_numeric, errors="coerce").sort_index()
    if frame.empty or not np.isfinite(frame.to_numpy()).all() or (frame <= 0).any().any():
        raise ValueError("Dữ liệu giá phải đầy đủ, hữu hạn và lớn hơn 0.")
    return frame.div(frame.iloc[0]).mul(100) if rebase else frame.copy()


def render_history() -> None:
    prices = st.session_state.get("prices_df", pd.DataFrame())
    if st.session_state.get("data_status") != "ok" or prices.empty:
        st.info("Chọn mã và bấm **Phân tích** để xem lịch sử giá. Có thể học hoặc chuẩn bị danh mục mô phỏng trong lúc chờ nguồn dữ liệu.")
        st.button(
            "Nạp bộ dữ liệu minh họa offline",
            key="load_sample_data",
            help="Dữ liệu tổng hợp cố định cho học tập; không phải giá thật và không dùng để giao dịch.",
            on_click=lambda: st.session_state.update(sample_data_requested=True),
        )
        st.caption("Bộ mẫu chạy không cần mạng, phù hợp khi nguồn giá bị chặn hoặc khi dạy trên lớp.")
        return
    st.subheader("Dữ liệu đang nghiên cứu")
    market = st.session_state.get("market_ticker", "")
    source = str(st.session_state.get("data_source") or "Chưa xác định nguồn")
    st.caption(f"Nguồn: {source} · {len(prices)} phiên · "
               f"{pd.Timestamp(prices.index.min()):%d/%m/%Y} – {pd.Timestamp(prices.index.max()):%d/%m/%Y}. "
               "Giá cổ phiếu: nghìn VND/cổ phiếu; chỉ số thị trường: điểm.")
    names = list(prices.columns)
    previous = st.session_state.get("history_symbols")
    if previous is not None and any(s not in names for s in previous):
        st.session_state.history_symbols = [s for s in previous if s in names]
    symbols = st.multiselect("Mã trên biểu đồ", names,
                             default=[s for s in names if s != market][:4], key="history_symbols")
    rebase = st.toggle("So sánh cùng mốc 100", value=True, key="history_rebase",
                       help="Mỗi mã bắt đầu ở 100 để so biến động; 110 nghĩa là tăng 10% so với phiên đầu.")
    if not symbols:
        st.caption("Chọn ít nhất một mã để hiển thị biểu đồ.")
        return
    try:
        frame = history_view(prices, symbols, rebase=rebase)
    except ValueError as exc:
        st.warning(str(exc))
        return
    groups = [(frame, "Mốc đầu = 100")] if rebase else [
        (frame[[s for s in symbols if s != market]], "Nghìn VND/cổ phiếu"),
        (frame[[market]] if market in symbols else pd.DataFrame(), "Điểm chỉ số"),
    ]
    for idx, (data, unit) in enumerate(groups):
        if data.empty:
            continue
        fig = px.line(data.rename_axis("Phiên"), labels={"value": unit, "variable": "Mã"},
                      color_discrete_sequence=["#5EEAD4", "#93C5FD", "#FBBF24", "#FDA4AF"])
        fig.update_layout(height=330, margin=dict(l=8, r=8, t=16, b=8),
                          legend=dict(orientation="h", y=1.12), hovermode="x unified")
        st.plotly_chart(fig, width="stretch", key=f"history_chart_{idx}")
    raw = prices.loc[:, symbols].sort_index().rename_axis("Ngày")
    summary = pd.DataFrame({
        "Mã": symbols,
        "Giá / điểm đầu": raw.iloc[0].to_numpy(),
        "Giá / điểm cuối": raw.iloc[-1].to_numpy(),
        "Thay đổi (%)": ((raw.iloc[-1] / raw.iloc[0] - 1) * 100).to_numpy(),
        "Đơn vị": ["Điểm" if s == market else "Nghìn VND/cổ phiếu" for s in symbols],
    })
    st.dataframe(summary, hide_index=True, width="stretch")
    with st.expander("Bảng giá và tải dữ liệu"):
        exported = raw.rename(columns={s: f"{s} ({'điểm' if s == market else 'nghìn VND/cổ phiếu'})" for s in symbols})
        st.dataframe(exported, width="stretch")
        st.download_button("Tải lịch sử giá (CSV)", exported.to_csv(index_label="Ngày").encode("utf-8-sig"),
                           file_name="lich_su_gia.csv", mime="text/csv", key="history_download")
