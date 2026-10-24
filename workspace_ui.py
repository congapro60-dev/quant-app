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
MUSE_LABEL = "Soạn học liệu với AI"


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


# ---------------------------------------------------------------------------
# Hành trình lần đầu (onboarding C2): checklist 5 bước cho người mới
# ---------------------------------------------------------------------------

JOURNEY_HIDE_KEY = "qa_first_journey_hidden"
BACKUP_FLAG_KEY = "qa_backup_downloaded"


def _journey_steps(lessons, scores) -> list[dict]:
    """Trả về 5 bước hành trình; trạng thái done đọc từ dữ liệu thật."""

    profile = st.session_state.get("progress_profile", {})

    pre = profile.get("pre_test") or {}
    pre_score = pre.get("score")
    pre_done = pre_score is not None

    passed = [
        (getattr(lesson, "title", "") or lesson.lesson_id, scores.get(lesson.lesson_id))
        for lesson in lessons
        if scores.get(lesson.lesson_id, 0) >= cur.UNLOCK_THRESHOLD
    ]
    lesson_done = bool(passed)

    ledger = st.session_state.get("paper_ledger") or {}
    journal = profile.get("journal") or []

    steps = [
        {
            "done": pre_done,
            "evidence": (f"{pre_score:.0f}/100 · {pre.get('taken_at', '')}"
                         if pre_done else ""),
            "title": "Làm bài chẩn đoán Đầu vào",
            "detail": "2 phút · đo điểm gốc trước khi học — sau này so bằng chính đề đó",
            "action": "Làm ngay",
            "target": (lmode.AREA_JOURNAL, None),
        },
        {
            "done": lesson_done,
            "evidence": (f"{passed[0][0]} — {passed[0][1]:.0f}/100"
                         if lesson_done else ""),
            "title": "Học xong bài 1",
            "detail": "ở Lộ trình học — hệ thống tự chấm",
            "action": "Đến lộ trình",
            "target": (lmode.AREA_LEARNING, None),
        },
        {
            "done": bool(ledger),
            "evidence": (f"{len(ledger.get('fills', []))} lệnh mô phỏng"
                         if ledger else ""),
            "title": "Tạo danh mục mô phỏng",
            "detail": "500 triệu VND ảo ở tab Đầu tư — tiền thật không dính vào đây",
            "action": "Đến Đầu tư",
            "target": (lmode.AREA_INVEST, lmode.FEATURE_PAPER),
        },
        {
            "done": bool(journal),
            "evidence": (f"{len(journal)} mục nhật ký" if journal else ""),
            "title": "Ghi 1 mục nhật ký quyết định",
            "detail": "viết lý do TRƯỚC khi đặt lệnh mô phỏng đầu tiên",
            "action": "Mở nhật ký",
            "target": (lmode.AREA_JOURNAL, None),
        },
        {
            "done": bool(st.session_state.get(BACKUP_FLAG_KEY)),
            "evidence": "Đã tải tệp JSON" if st.session_state.get(BACKUP_FLAG_KEY) else "",
            "title": "Tải hồ sơ (JSON) về máy",
            "detail": "điểm nằm trong trình duyệt — tải 1 lần để không mất",
            "action": "Tải hồ sơ",
            "target": (lmode.AREA_JOURNAL, None),
        },
    ]
    return steps


def render_first_journey(lessons, scores) -> None:
    """Checklist 5 bước đầu tiên — đọc tiến độ thật, tự ẩn khi đủ 5/5.

    Chỉ thêm vào Trang tổng quan, không dời khối nào. Nút bấm bên phải mỗi
    bước nhảy đúng khu chứa việc đó bằng cơ chế điều hướng sẵn có.
    """

    steps = _journey_steps(lessons, scores)
    if st.session_state.get(JOURNEY_HIDE_KEY) or all(s["done"] for s in steps):
        return

    done_n = sum(s["done"] for s in steps)
    with st.container(border=True):
        st.caption(f"HÀNH TRÌNH LẦN ĐẦU · {done_n}/5")
        for index, step in enumerate(steps):
            if step["done"]:
                title = f"✅ ~~{step['title']}~~"
                caption = step["evidence"] or "Hoàn thành"
                button_col = None
            else:
                title = f"⬜ **{step['title']}**"
                caption = step["detail"]
                button_col = step["action"]
            label_col, caption_col, action_col = st.columns(
                [0.62, 0.38, 0.24], vertical_alignment="center",
            )
            with label_col:
                st.markdown(title)
            with caption_col:
                st.caption(caption)
            with action_col:
                if button_col:
                    st.button(
                        button_col, key=f"journey_{index}",
                        on_click=navigate_to,
                        args=step["target"], width="stretch",
                    )
        st.button("Ẩn danh sách này", key="journey_hide",
                  on_click=lambda: st.session_state.update({JOURNEY_HIDE_KEY: True}))


# ---------------------------------------------------------------------------
# Onboarding C3: Tour 4 bước tự mở lần đầu (st.dialog chuẩn, 1 lần/máy)
# ---------------------------------------------------------------------------

TOUR_STEP_KEY = "_tour_step"

_TOUR_STEPS = (
    ("Đây là gì?", "Không cần tài khoản, không lệnh thật",
     "Ứng dụng dạy tài chính cho học sinh: điểm lưu trong trình duyệt của em, "
     "danh mục dùng tiền ảo, và không bao giờ gửi lệnh đến công ty chứng khoán."),
    ("Học ở đâu?", "Học ở Lộ trình học",
     "11 bài xếp theo trình độ lớp của em, mỗi bài có câu hỏi tự chấm. "
     "Điểm đạt 70 mới mở chương nâng cao."),
    ("Thực hành ra sao?", "Thực hành ở Đầu tư",
     "Lấy 500 triệu VND ảo, mua bán như thật. Trước khi đặt lệnh, ghi 1 dòng "
     '"vì sao" vào Nhật ký quyết định — viết trước để không tự lừa mình sau.'),
    ("Giữ lại cái gì?", "Giữ bằng chứng học tập",
     "Nhật ký & tiến độ lưu điểm, hai bài chẩn đoán, và gói nộp cho giáo viên. "
     "Xong lộ trình thì tải hồ sơ JSON về máy."))


def _profile_is_fresh(profile) -> bool:
    """Hồ sơ còn trống mới đáng xem tour: chưa điểm, chưa bài, chưa nhật ký."""

    pre = (profile.get("pre_test") or {}).get("score")
    return (pre is None
            and not (profile.get("lesson_scores") or {})
            and not (profile.get("journal") or [])
            and not st.session_state.get("paper_ledger"))


def _mark_tour_seen() -> None:
    state = st.session_state.get("progress_profile")
    if isinstance(state, dict):
        state["seen_tour"] = True


def _finish_tour() -> None:
    """Kết thúc tour: đánh dấu đã xem, chuyển khu, rồi buộc rerun toàn app.

    st.dialog chạy như fragment: bấm nút trong dialog chỉ rerun riêng dialog,
    thanh tab phía sau không được dựng lại. Thiếu st.rerun() thì cờ và
    NAV_KEY đổi đúng mà màn hình vẫn đứng ở Tổng quan.
    """

    _mark_tour_seen()
    navigate_to(lmode.AREA_JOURNAL)
    st.rerun()


@st.dialog("Chào mừng đến Quant App", width="large")
def _tour_dialog() -> None:
    step = min(int(st.session_state.get(TOUR_STEP_KEY, 0)), len(_TOUR_STEPS) - 1)
    kicker, title, body = _TOUR_STEPS[step]
    st.caption(f"BƯỚC {step + 1}/{len(_TOUR_STEPS)} · {kicker.upper()}")
    st.subheader(title)
    st.write(body)

    left, right = st.columns([0.4, 0.6])
    with left:
        st.button("Để sau", key="tour_defer", on_click=_mark_tour_seen)
    with right:
        nav = st.columns(2)
        if st.session_state.get(TOUR_STEP_KEY, 0) > 0:
            with nav[0]:
                st.button("← Trước", key="tour_back",
                          on_click=lambda: st.session_state.update(
                              {TOUR_STEP_KEY: step - 1}))
        with nav[1]:
            if step == len(_TOUR_STEPS) - 1:
                st.button("Đi làm bài Đầu vào", key="tour_finish", type="primary",
                          on_click=_finish_tour)
            else:
                st.button("Tiếp →", key="tour_next", type="primary",
                          on_click=lambda: st.session_state.update(
                              {TOUR_STEP_KEY: step + 1}))


def maybe_open_first_tour() -> None:
    """Chỉ mở tour đúng khi hồ sơ còn trống và lần đầu dùng trên máy này."""

    profile = st.session_state.get("progress_profile") or {}
    if isinstance(profile, dict) and _profile_is_fresh(profile) \
            and not profile.get("seen_tour"):
        _tour_dialog()


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
    maybe_open_first_tour()
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
    render_first_journey(lessons, scores)
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
    with st.expander("Có thể tận dụng AI bên ngoài vào việc gì?"):
        st.write("Soạn bài tự học, lên kịch bản hình/video minh họa, tổng hợp nghiên cứu công khai có nguồn. "
                 "Bắt đầu bằng bản yêu cầu học liệu từ bài học có sẵn trong Quant App, dán vào AI nào lớp bạn vào được.")
        st.button("Soạn yêu cầu học liệu cho AI", on_click=navigate_to,
                  args=(lmode.AREA_LEARNING, MUSE_LABEL), key="overview_muse")
    render_tab_map()


# Bảng "Tab nào — khi nào": mỗi khu vực đúng một dòng, việc cụ thể và mốc
# thời gian để người mới biết mở tab nào, thay vì đoán.
TAB_MAP = (
    (lmode.AREA_LEARNING, "Hiểu khái niệm, làm bài, được tự chấm điểm",
     "Bắt đầu ngay · mỗi ngày 1 bài"),
    (lmode.AREA_DATA, "Nạp giá cổ phiếu, so sánh biến động giữa các mã",
     "Khi cần dữ liệu thật cho bài tập"),
    (lmode.AREA_MODEL_LAB, "Chạy mô hình định lượng và kiểm định thống kê",
     "Sau khi học xong phần định lượng"),
    (lmode.AREA_INVEST, "Đặt lệnh bằng tiền ảo, tính phí và thuế như thật",
     "Sau bài 1 · trước mọi quyết định thật"),
    (lmode.AREA_JOURNAL, "Ghi lý do trước khi hành động, xem điểm, tải hồ sơ",
     "Trước mỗi lệnh · cuối mỗi buổi học"),
)


def render_tab_map() -> None:
    """Bảng chỉ đường 5 khu vực; luôn hiện, không phụ thuộc tiến độ."""

    st.subheader("Tab nào — khi nào")
    st.caption("Năm khu vực ở thanh trên cùng. Mở đúng tab để không phải dò.")
    st.dataframe(
        [{"Khu vực": lmode.AREA_LABELS[area], "Dùng để": use, "Khi nào": when}
         for area, use, when in TAB_MAP],
        width="stretch", hide_index=True,
    )


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
