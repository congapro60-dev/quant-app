"""Giao diện cho hai khu vực mới: Lộ trình học, Nhật ký và tiến độ.

Tách khỏi ``app.py`` theo đúng nếp của ``investment_ui.py`` để tệp giao diện
chính không phình thêm.
"""

from __future__ import annotations

from typing import Any
from statistics import pstdev

import streamlit as st

import curriculum as cur
import curriculum_university as uni
import feature_guides as guides
import learning_modes as lmode
import policy_audit as audit
import stats_tools as stt
import progress_profile as pp
import provider_directory as pdir
import readiness_gate as rg
import risk_limits as rlim
import classroom_packages as cp
from workspace_ui import navigate_to


def _profile() -> dict[str, Any]:
    if "progress_profile" not in st.session_state:
        st.session_state["progress_profile"] = pp.empty_profile()
    return st.session_state["progress_profile"]


# ---------------------------------------------------------------------------
# Khu vực: Lộ trình học
# ---------------------------------------------------------------------------

# Lộ trình dành cho người học đại học và người nghiên cứu: không phải bài giảng
# nhập môn mà là bản đồ dẫn tới đúng công cụ, kèm điều kiện dùng đúng.
UNIVERSITY_TRACK = (
    {
        "title": "1. Nạp và kiểm định dữ liệu",
        "goal": "Có bộ giá sạch, đúng mã, đúng khoảng ngày trước khi chạy bất kỳ mô hình nào.",
        "do": "Mở lịch sử giá, nhập mã rồi bấm Phân tích. Đối chiếu phiên dữ liệu và nguồn.",
        "where": "Khám phá dữ liệu → Lịch sử giá cuối ngày",
        "area": lmode.AREA_DATA,
        "feature": "history",
        "trap": "Dữ liệu lỗi vẫn cho ra hệ số đẹp. Kiểm tra trước, đừng tin bảng kết quả.",
    },
    {
        "title": "2. Mô hình chỉ số đơn (SIM)",
        "goal": "Ước lượng beta, tách rủi ro hệ thống khỏi rủi ro riêng lẻ.",
        "do": "Chạy hồi quy từng mã theo chỉ số, đọc beta, R² và phần dư.",
        "where": "Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn (SIM)",
        "area": lmode.AREA_MODEL_LAB,
        "feature": lmode.FEATURE_SIM,
        "trap": "R² cao không có nghĩa mô hình đúng; phải xem chẩn đoán phần dư.",
    },
    {
        "title": "3. Chẩn đoán khuyết tật mô hình",
        "goal": "Biết khi nào suy diễn thống kê từ mô hình là không dùng được.",
        "do": "Đọc kiểm định White, Breusch–Godfrey, Ramsey RESET và Jarque–Bera.",
        "where": "Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn (SIM)",
        "area": lmode.AREA_MODEL_LAB,
        "feature": lmode.FEATURE_SIM,
        "trap": "Phương sai sai số thay đổi làm sai số chuẩn sai, kéo theo t và F sai.",
    },
    {
        "title": "4. Danh mục trung bình–phương sai (Markowitz)",
        "goal": "Tìm danh mục biến động nhỏ nhất và danh mục Sharpe cao nhất.",
        "do": "Chọn từ hai mã trở lên, xem tỷ trọng và đường biên hiệu quả.",
        "where": "Phòng thí nghiệm mô hình → Danh mục Markowitz",
        "area": lmode.AREA_MODEL_LAB,
        "feature": lmode.FEATURE_MARKOWITZ,
        "trap": "Tỷ trọng tối ưu rất nhạy với lợi suất kỳ vọng; sai đầu vào là sai tất cả.",
    },
    {
        "title": "5. Kiểm thử ngoài mẫu (out-of-sample backtest)",
        "goal": "Xem chiến lược còn đứng vững khi rời khỏi dữ liệu đã dùng để xây.",
        "do": "Chạy kiểm thử cuốn chiếu, tính đủ phí, thuế và trượt giá.",
        "where": "Phòng thí nghiệm mô hình → Kiểm thử ngoài mẫu",
        "area": lmode.AREA_MODEL_LAB,
        "feature": lmode.FEATURE_BACKTEST,
        "trap": "Quyết định tại T phải thực thi từ T+1; trộn lẫn là rò rỉ tương lai.",
    },
    {
        "title": "6. EViews tiếng Việt và ôn thi",
        "goal": "Làm lại bài tập trên lớp và đối chiếu đáp án.",
        "do": "Tải tệp của bạn, gõ lệnh LS/GENR/ADF quen thuộc.",
        "where": "Khám phá dữ liệu → EViews tiếng Việt",
        "area": lmode.AREA_DATA,
        "feature": lmode.FEATURE_EVIEWS,
        "trap": "Đơn vị và tần suất dữ liệu phải khớp đề bài, nếu không hệ số lệch.",
    },
)


def render_learning_area() -> None:
    """Nội dung khác hẳn nhau theo lộ trình.

    Trước đây cả hai chế độ đều thấy sáu mô-đun trung học phổ thông, nên đổi
    chế độ gần như không thấy khác biệt gì.
    """

    if lmode.get_mode(st.session_state) == lmode.MODE_UNIVERSITY:
        _render_university_track()
        return
    _render_highschool_track()


def _render_university_track() -> None:
    st.header("Lộ trình định lượng")
    st.caption(
        "Sáu bài bám giáo trình môn học: lợi suất, độ dao động danh mục, mô hình "
        "chỉ số đơn, phân tách rủi ro, quy trình ước lượng và phân tích trung "
        "bình–phương sai. Chấm điểm ngay trên máy."
    )

    with st.expander("🧭 Bản đồ nhanh: mỗi bước dùng công cụ nào"):
        for idx, step in enumerate(UNIVERSITY_TRACK):
            st.markdown(f"**{step['title']}** — {step['goal']}")
            st.write(step["do"])
            st.caption(f"Ở đâu: {step['where']} · Dễ sai: {step['trap']}")
            st.button(
                f"Mở công cụ bước {idx + 1}", key=f"dh_map_{idx}",
                on_click=navigate_to, args=(step["area"], step["feature"]),
            )

    _render_lesson_track(
        uni.all_lessons(),
        unlock_note=None,
        key_prefix="dh",
    )

    st.markdown("---")
    with st.expander("📗 Cần ôn lại nền tảng? Mở mười bài học trung học phổ thông"):
        st.caption(
            "Dành cho người muốn xem lại khái niệm gốc: lãi kép, lợi suất, "
            "biến động, tương quan và nhân quả."
        )
        _render_lesson_track(cur.all_lessons(), unlock_note=None, key_prefix="thpt_on")


def _render_highschool_track(compact: bool = False) -> None:
    if not compact:
        st.header("Lộ trình học")
    st.caption(
        "Mười bài học đi theo nhịp làm dự án: bài thống kê (Toán 10, 11, 12) "
        "xen giữa các bài tài chính đúng lúc dự án cần đến nó — học sai số sau "
        "bài dự báo, học phân tán trước bài rủi ro. Bài làm được chấm ngay trên "
        "máy, không cần khóa giao diện lập trình (API) hay kết nối tới trí tuệ "
        "nhân tạo (AI)."
    )
    _render_lesson_track(
        cur.all_lessons(),
        unlock_note=(
            f"Đã đạt {{done}}/{cur.UNLOCK_REQUIRED_LESSONS} mô-đun cần thiết "
            "để mở khóa công cụ nâng cao"
        ),
        key_prefix="thpt",
    )


def _pick_lesson(key: str, index: int) -> None:
    st.session_state[key] = index


def _render_thpt_practice(lesson, *, key_prefix: str) -> None:
    """Run one local practice action for every THPT lesson.

    Each curriculum promise must point to a real action. Network data remains
    optional; the first and fourth modules therefore use tiny local calculators.
    """

    kind = lesson.interactive_kind
    if kind == cur.INTERACTIVE_COMPOUND:
        principal, rate, years = st.columns(3)
        with principal:
            p = st.number_input("Tiền gốc (triệu đồng)", min_value=0.0, value=20.0,
                                step=1.0, key=f"{key_prefix}_compound_p")
        with rate:
            r = st.number_input("Lãi suất (%/năm)", min_value=-100.0, value=5.0,
                                step=0.5, key=f"{key_prefix}_compound_r")
        with years:
            n = st.number_input("Số năm", min_value=0.0, value=3.0, step=1.0,
                                key=f"{key_prefix}_compound_n")
        if st.button("Tính lãi kép", key=f"{key_prefix}_compound_run", type="primary"):
            value = p * (1 + r / 100) ** n
            st.success(f"Giá trị sau {n:g} năm: **{value:,.2f} triệu đồng**.")
            st.caption("Đây là phép tính minh họa, chưa trừ thuế/phí và không phải dự báo đầu tư.")
    elif kind == cur.INTERACTIVE_MARKET:
        st.button("Mở giá trong phiên", key=f"{key_prefix}_practice",
                  on_click=navigate_to, args=(lmode.AREA_DATA, lmode.FEATURE_INTRADAY))
    elif kind in (cur.INTERACTIVE_RETURN, cur.INTERACTIVE_CHART):
        st.button("Mở lịch sử giá", key=f"{key_prefix}_practice",
                  on_click=navigate_to, args=(lmode.AREA_DATA, "history"))
    elif kind == cur.INTERACTIVE_RISK:
        raw = st.text_input(
            "Nhập các lợi suất (%) cách nhau bằng dấu phẩy",
            value="-2, 1, 0.5, 3, -1",
            key=f"{key_prefix}_risk_values",
        )
        if st.button("Tính độ dao động", key=f"{key_prefix}_risk_run", type="primary"):
            try:
                values = [float(item.strip()) for item in raw.split(",") if item.strip()]
                if len(values) < 2:
                    raise ValueError
                st.success(f"Độ lệch chuẩn mẫu minh họa: **{pstdev(values):.2f} điểm phần trăm**.")
            except ValueError:
                st.warning("Cần ít nhất hai số hợp lệ, ngăn cách bằng dấu phẩy.")
    elif kind == cur.INTERACTIVE_PAPER:
        st.button("Mở giao dịch mô phỏng", key=f"{key_prefix}_practice",
                  on_click=navigate_to, args=(lmode.AREA_INVEST, lmode.FEATURE_PAPER))
    elif kind == cur.INTERACTIVE_SAI_SO:
        left, right = st.columns(2)
        with left:
            assumed = st.number_input("Giá dự báo ā (nghìn đồng)", value=25.0,
                                      step=0.1, key=f"{key_prefix}_saiso_hat")
        with right:
            actual = st.number_input("Giá thực tế a (nghìn đồng)", value=25.5,
                                     step=0.1, key=f"{key_prefix}_saiso_a")
        if st.button("Tính sai số", key=f"{key_prefix}_saiso_run", type="primary"):
            if assumed == 0:
                st.warning("Giá dự báo phải khác 0 để tính sai số tương đối.")
            else:
                err = stt.approx_error(actual, assumed)
                st.success(
                    f"Δa = **{err['abs_error']:.2f} nghìn đồng**, "
                    f"δ = **{err['rel_error_pct']:.2f}%**."
                )
                st.caption("Số gần đúng ā thay cho số thật a; δ càng nhỏ dự báo "
                           "càng chính xác — so hai dự báo bằng δ, không bằng Δa.")
    elif kind == cur.INTERACTIVE_DAC_TRUNG:
        raw = st.text_area("Nhập các lợi suất (%) cách nhau bằng dấu phẩy",
                           value="-2, 1, 0.5, 3, -1",
                           key=f"{key_prefix}_ungrouped_values")
        if st.button("Tính số đặc trưng", key=f"{key_prefix}_ungrouped_run",
                     type="primary"):
            try:
                s = stt.summarize_ungrouped(stt.parse_values(raw))
                st.success(
                    f"Số trung bình **{s['mean']:.3f}**, phương sai "
                    f"**{s['variance']:.3f}**, độ lệch chuẩn **{s['std']:.3f}** (%)."
                )
                st.caption("Cùng trung bình vẫn có thể khác phân tán. Máy tính "
                           "đầy đủ có ở tab Khám phá dữ liệu.")
            except (TypeError, ValueError) as exc:
                st.warning(str(exc) or "Cần ít nhất hai số hợp lệ, ngăn cách bằng dấu phẩy.")
        st.button("Mở máy tính số đặc trưng", key=f"{key_prefix}_calc_nav",
                  on_click=navigate_to, args=(lmode.AREA_DATA, lmode.FEATURE_STATS_CALC))
    elif kind == cur.INTERACTIVE_GHEP_NHOM:
        raw = st.text_area("Nhập các lợi suất (%) cách nhau bằng dấu phẩy",
                           value="-2, 1, 0.5, 3, -1, 1, -0.5, 2",
                           key=f"{key_prefix}_grouped_values")
        groups = st.slider("Số nhóm k", 2, 10, 4, key=f"{key_prefix}_grouped_k")
        if st.button("Ghép nhóm và so sánh", key=f"{key_prefix}_grouped_run",
                     type="primary"):
            try:
                _, _, table = stt.compare_grouping(stt.parse_values(raw), groups)
                mean_row = table.iloc[0]
                std_row = table.iloc[3]
                st.success(
                    f"x̄: ghép nhóm **{mean_row['Ghép nhóm (ước lượng)']:.3f}** "
                    f"trực tiếp **{mean_row['Không ghép nhóm']:.3f}** — sai số tương "
                    f"đối **{mean_row['Sai số tương đối (%)']:.2f}%**. s: ghép nhóm "
                    f"**{std_row['Ghép nhóm (ước lượng)']:.3f}** trực tiếp "
                    f"**{std_row['Không ghép nhóm']:.3f}**."
                )
                st.caption("Ghép nhóm mất chi tiết nên lệch đi — đúng tinh thần "
                           "bài Số gần đúng và sai số (Toán 10).")
            except (TypeError, ValueError) as exc:
                st.warning(str(exc) or "Cần ít nhất hai số hợp lệ.")
        st.button("Mở phòng thí nghiệm ghép nhóm", key=f"{key_prefix}_lab_nav",
                  on_click=navigate_to, args=(lmode.AREA_DATA, lmode.FEATURE_GROUPING_LAB))
    elif kind == cur.INTERACTIVE_PHAN_TAN:
        left, right = st.columns(2)
        with left:
            raw_a = st.text_area("Giai đoạn 1 — lợi suất (%) cách nhau bằng dấu phẩy",
                                 value="-1, 0.5, -0.5, 1, 0.5, -1, 1, 0.5",
                                 key=f"{key_prefix}_ptan_a")
        with right:
            raw_b = st.text_area("Giai đoạn 2 — lợi suất (%) cách nhau bằng dấu phẩy",
                                 value="-3, 1.5, -1, 2.5, 0.5, -2, 1.5, 2.5",
                                 key=f"{key_prefix}_ptan_b")
        if st.button("So sánh độ phân tán", key=f"{key_prefix}_practice",
                     type="primary"):
            try:
                s_a = stt.summarize_grouped(stt.parse_values(raw_a), 4)
                s_b = stt.summarize_grouped(stt.parse_values(raw_b), 4)
                wider = "Giai đoạn 2" if s_b["std"] > s_a["std"] else "Giai đoạn 1"
                st.success(
                    f"s_g giai đoạn 1: **{s_a['std']:.3f}**, giai đoạn 2: "
                    f"**{s_b['std']:.3f}**. {wider} biến động mạnh hơn."
                )
                st.caption("Cùng đơn vị mới so được s_g; phân tán lớn nghĩa là "
                           "mẫu dao động quanh trung tâm mạnh hơn.")
            except (TypeError, ValueError) as exc:
                st.warning(str(exc) or "Cần ít nhất hai số hợp lệ cho mỗi giai đoạn.")


def _render_lesson_track(lessons, *, unlock_note: str | None, key_prefix: str) -> None:
    """Dựng một lộ trình bài học.

    Dùng chung cho cả lộ trình trung học phổ thông và lộ trình đại học, để phần
    chấm điểm và hiển thị đáp án chỉ tồn tại một bản.
    """

    if not lessons:
        st.info("Lộ trình này chưa có bài học.")
        return

    profile = _profile()
    scores = profile.setdefault("lesson_scores", {})
    unfinished = next(
        (i for i, lesson in enumerate(lessons)
         if scores.get(lesson.lesson_id, 0) < cur.UNLOCK_THRESHOLD),
        None,
    )

    if unlock_note:
        done = sum(
            1 for l in lessons if scores.get(l.lesson_id, 0) >= cur.UNLOCK_THRESHOLD
        )
        st.progress(
            min(1.0, done / cur.UNLOCK_REQUIRED_LESSONS),
            text=unlock_note.format(done=done),
        )

    titles = [f"{l.order}. {l.title}" for l in lessons]
    pick_key = f"{key_prefix}_pick"
    st.button(
        "Tiếp tục bài chưa đạt", key=f"{key_prefix}_continue",
        disabled=unfinished is None,
        on_click=_pick_lesson, args=(pick_key, unfinished),
    )
    if unfinished is None:
        st.success("Đã đạt tất cả bài học. Bạn có thể chọn bài để ôn lại.")
    else:
        st.caption(f"Bài chưa đạt đầu tiên: {titles[unfinished]}")
    picked = st.selectbox(
        "Chọn bài:", range(len(titles)), index=unfinished or 0,
        format_func=lambda i: titles[i], key=pick_key,
    )
    lesson = lessons[picked]
    previous, following = st.columns(2)
    previous.button(
        "Bài trước", key=f"{key_prefix}_previous", disabled=picked == 0,
        on_click=_pick_lesson, args=(pick_key, max(0, picked - 1)),
        width="stretch",
    )
    following.button(
        "Bài tiếp theo", key=f"{key_prefix}_next", disabled=picked == len(lessons) - 1,
        on_click=_pick_lesson, args=(pick_key, min(len(lessons) - 1, picked + 1)),
        width="stretch",
    )

    st.subheader(lesson.title)
    st.caption(f"Bài {picked + 1}/{len(lessons)} · Đạt từ {cur.UNLOCK_THRESHOLD:.0f}/100 điểm")
    current = scores.get(lesson.lesson_id)
    if current is not None:
        st.caption(f"Điểm gần nhất của bạn: **{current:.0f}/100**")

    st.markdown("#### 1. Mục tiêu")
    st.write(lesson.objective)

    with st.expander("Đọc giải thích", expanded=True):
        st.write(lesson.explanation)
    with st.expander("Xem ví dụ có lời giải"):
        st.write(lesson.example)

    st.markdown("#### 2. Thực hành")
    st.info(lesson.interactive)
    if lesson.lesson_id.startswith("dh"):
        feature = {
            uni.INT_RETURN: lmode.FEATURE_EXAM,
            uni.INT_COV: lmode.FEATURE_EXAM,
            uni.INT_SIM: lmode.FEATURE_SIM,
            uni.INT_DIAG: lmode.FEATURE_EVIEWS,
            uni.INT_MARKOWITZ: lmode.FEATURE_EXAM,
        }.get(lesson.interactive_kind)
        if feature:
            target = lmode.FEATURES[feature]
            st.button(
                f"Mở {target['label']}", key=f"{key_prefix}_practice",
                on_click=navigate_to, args=(target["area"], feature),
            )
    else:
        _render_thpt_practice(lesson, key_prefix=key_prefix)

    st.markdown("#### 3. Tự kiểm tra")
    st.caption("Câu để trống tính là chưa đúng. Có thể làm lại; điểm lần nộp gần nhất được lưu.")
    with st.form(f"quiz_{key_prefix}_{lesson.lesson_id}"):
        responses: dict[str, Any] = {}
        for idx, q in enumerate(lesson.questions, start=1):
            st.markdown(f"**Câu {idx}.** {q.prompt}")
            if q.kind == cur.QUESTION_SINGLE:
                # index=None để không đáp án nào được chọn sẵn. Nếu để mặc định
                # là 0, câu nào có đáp án đúng ở vị trí đầu sẽ được chấm đúng
                # dù học sinh chưa hề trả lời.
                responses[q.qid] = st.radio(
                    "Chọn một đáp án:", range(len(q.options)),
                    index=None,
                    format_func=lambda i, opts=q.options: opts[i],
                    key=f"{key_prefix}_{q.qid}_r", label_visibility="collapsed",
                )
            else:
                # value=None vì lý do tương tự: ô để trống phải khác với số 0
                # do học sinh chủ động nhập.
                responses[q.qid] = st.number_input(
                    "Nhập kết quả:", value=None, step=0.01,
                    placeholder="Nhập số…",
                    key=f"{key_prefix}_{q.qid}_n", label_visibility="collapsed",
                )
        submitted = st.form_submit_button("Nộp bài", type="primary")

    if submitted:
        score = lesson.grade(responses)
        pp.record_lesson_attempt(
            profile,
            lesson.lesson_id,
            score,
            {q.qid: q.check(responses.get(q.qid)) for q in lesson.questions},
        )
        unlocked = (
            cur.should_unlock_advanced(profile.get("lesson_scores"))
            and not st.session_state.get(lmode.UNLOCK_KEY)
        )
        # Lưu trước rerun: lần mở khóa phải giữ được đáp án và phản hồi chấm.
        st.session_state.setdefault("lesson_feedback", {})[lesson.lesson_id] = {
            "score": score,
            "correct": [q.check(responses.get(q.qid)) for q in lesson.questions],
            "unlocked": unlocked,
        }
        if unlocked:
            st.session_state[lmode.UNLOCK_KEY] = True
        st.rerun()

    feedback = st.session_state.get("lesson_feedback", {}).get(lesson.lesson_id)
    if feedback:
        score = feedback["score"]
        st.markdown("##### Kết quả lần nộp gần nhất")
        if score >= cur.UNLOCK_THRESHOLD:
            st.success(f"Bạn được {score:.0f}/100. Đạt yêu cầu của mô-đun này.")
        else:
            st.warning(f"Bạn được {score:.0f}/100. Cần từ {cur.UNLOCK_THRESHOLD:.0f} điểm để đạt.")

        st.markdown("##### Đáp án và giải thích")
        for idx, (q, ok) in enumerate(zip(lesson.questions, feedback["correct"]), start=1):
            st.markdown(f"{'✅' if ok else '❌'} **Câu {idx}.** {q.explanation}")

        if feedback["unlocked"]:
            st.success(
                "🔓 Bạn đã mở khóa nhóm công cụ nâng cao: mô hình chỉ số đơn (SIM), "
                "Markowitz, EViews và kiểm thử ngoài mẫu (out-of-sample backtest)."
            )

    with st.expander("Lỗi hiểu sai thường gặp"):
        for wrong, correction in lesson.misconceptions:
            st.markdown(f"**“{wrong}”**")
            st.write(correction)

    with st.expander("Nguồn học liệu"):
        for name, url in lesson.resources:
            # Tài liệu bản in không có URL: giữ tên nguồn, không tạo liên kết rỗng.
            if url:
                st.markdown(f"- [{name}]({url})")
            else:
                st.markdown(f"- {name}")


# ---------------------------------------------------------------------------
# Khu vực: Nhật ký và tiến độ
# ---------------------------------------------------------------------------

def render_journal_area() -> None:
    st.header("Nhật ký và tiến độ")
    profile = _profile()

    # "Sẵn sàng dùng vốn thật" và "Nơi mở tài khoản" đã chuyển sang khu Đầu tư,
    # nơi chúng thuộc về. Trước đây chúng nằm ở đây chỉ vì tiện lúc viết mã.
    tab_progress, tab_journal, tab_classroom, tab_settings = st.tabs(
        ["Tiến độ và tiêu chí đánh giá (rubric)", "Nhật ký quyết định",
         "Gói lớp học", "Lịch sử thiết lập"]
    )

    with tab_progress:
        _render_progress(profile)
    with tab_journal:
        _render_journal(profile)
    with tab_classroom:
        _render_classroom_packages(profile)
    with tab_settings:
        render_policy_audit()


def _render_diagnostic_form(
    profile: dict[str, Any], which: str, title: str, key_prefix: str,
) -> None:
    st.markdown(f"**{title}**")
    questions = pp.diagnostic_questions(cur.all_lessons())
    with st.form(f"diagnostic_{key_prefix}"):
        responses: dict[str, Any] = {}
        for index, question in enumerate(questions, start=1):
            st.markdown(f"**Câu {index}.** {question['prompt']}")
            if question["kind"] == cur.QUESTION_SINGLE:
                responses[question["qid"]] = st.radio(
                    "Chọn một đáp án:", range(len(question["options"])), index=None,
                    format_func=lambda i, opts=question["options"]: opts[i],
                    key=f"diagnostic_{key_prefix}_{question['qid']}_r",
                    label_visibility="collapsed",
                )
            else:
                responses[question["qid"]] = st.number_input(
                    "Nhập kết quả:", value=None, step=0.01,
                    placeholder="Nhập số…",
                    key=f"diagnostic_{key_prefix}_{question['qid']}_n",
                    label_visibility="collapsed",
                )
        submitted = st.form_submit_button("Nộp bài chẩn đoán", type="primary")

    if submitted:
        result = pp.grade_diagnostic(cur.all_lessons(), responses)
        pp.record_diagnostic(profile, result, which=which)
        st.success(f"Đã lưu {title.lower()}: {result['score']:.0f}/100.")

    previous = pp.diagnostic_attempts(profile, which)
    if previous:
        latest = previous[-1]
        st.caption(f"Lần gần nhất: **{latest['score']:.0f}/100** · {latest['taken_at']}")


def _render_progress(profile: dict[str, Any]) -> None:
    guides.render_guide(guides.PANEL_PROGRESS)
    st.subheader("Chẩn đoán đầu vào và đầu ra")
    st.caption(
        "Hai bài dùng cùng bộ câu hỏi cục bộ trong chương trình học. Điểm được "
        "tính từ câu trả lời, không nhập tay và không phải điểm rubric chính thức."
    )
    c1, c2 = st.columns(2)
    with c1:
        _render_diagnostic_form(profile, "pre_test", "Đầu vào (pre-test)", "pre")
    with c2:
        _render_diagnostic_form(profile, "post_test", "Đầu ra (post-test)", "post")

    st.subheader("Điểm từng mô-đun")
    scores = profile.get("lesson_scores") or {}
    if scores:
        st.dataframe(
            [{"Mô-đun": next((lesson.title for lesson in cur.all_lessons() + uni.all_lessons() if lesson.lesson_id == k), k),
              "Điểm": v} for k, v in scores.items()],
            width="stretch",
        )
    else:
        st.info("Chưa có mô-đun nào được chấm.")

    st.subheader("Điểm tổng theo tiêu chí đánh giá (rubric)")
    st.caption(
        "Kiến thức 30%, lập luận 30%, kỷ luật rủi ro và chất lượng nguồn 25%, "
        "nhật ký và phản tư 15%."
    )
    reflection = profile.setdefault("self_reflection_scores", {})
    st.caption(
        "Tự phản tư chỉ là dữ liệu của người học. Chỉ điểm trong "
        "`rubric_scores` do giáo viên/người chấm ghi mới được tính vào rubric."
    )
    cols = st.columns(3)
    for col, key in zip(cols, ("lap_luan", "rui_ro_nguon", "nhat_ky")):
        with col:
            value = st.number_input(
                f"Tự phản tư — {pp.RUBRIC_LABELS[key]}", 0.0, 100.0,
                value=float(reflection.get(key, 0.0)), step=1.0, key=f"self_reflection_{key}",
            )
            reflection[key] = value

    result = pp.compute_rubric(profile)
    st.dataframe(result.as_rows(), width="stretch")
    st.metric("Tổng điểm", f"{result.total:.2f}/100")
    st.caption("Điểm rubric chính thức chỉ dùng dữ liệu giáo viên/người chấm, không dùng tự phản tư.")

    st.subheader("Sao lưu hồ sơ")
    st.caption(
        "Hồ sơ chỉ tồn tại trong phiên trình duyệt. Hãy tải tệp về nếu muốn giữ lại."
    )
    st.download_button(
        "⬇️ Tải hồ sơ (JSON)",
        pp.export_json(profile).encode("utf-8"),
        file_name="ho_so_tien_do.json",
        mime="application/json",
    )
    uploaded = st.file_uploader("Nạp lại hồ sơ đã lưu:", type=["json"], key="profile_up")
    if uploaded is not None and st.button("Nạp hồ sơ"):
        try:
            st.session_state["progress_profile"] = pp.import_json(uploaded.getvalue())
            st.session_state.pop("lesson_feedback", None)
            st.success("Đã nạp hồ sơ.")
        except pp.ProfileImportError as exc:
            st.error(f"Tệp bị từ chối: {exc}")


def _render_journal(profile: dict[str, Any]) -> None:
    guides.render_guide(guides.PANEL_JOURNAL)
    st.subheader("Ghi nhật ký trước khi hành động")
    st.caption(
        "Viết trước khi đặt lệnh mô phỏng. Viết sau khi biết kết quả thì trí nhớ "
        "sẽ tự chỉnh lý do cho khớp, và bài học mất đi."
    )
    with st.form("journal_form"):
        title = st.text_input("Tiêu đề:")
        decision = st.text_input("Bạn định làm gì?")
        rationale = st.text_area("Vì sao?")
        risk = st.text_input("Điểm vô hiệu và giới hạn lỗ:")
        sources = st.text_input("Nguồn tham khảo:")
        if st.form_submit_button("Thêm vào nhật ký", type="primary"):
            if title.strip() and decision.strip():
                pp.add_journal_entry(
                    profile, title=title, decision=decision,
                    rationale=rationale, risk=risk, sources=sources,
                )
                st.success("Đã ghi.")
            else:
                st.warning("Cần ít nhất tiêu đề và nội dung quyết định.")

    entries = profile.get("journal") or []
    st.caption(f"Đã có **{len(entries)}** mục.")
    for item in reversed(entries[-20:]):
        with st.expander(f"{item.get('at', '')} — {item.get('title', '')}"):
            st.write(f"**Quyết định:** {item.get('decision', '')}")
            st.write(f"**Lý do:** {item.get('rationale', '')}")
            st.write(f"**Rủi ro:** {item.get('risk', '')}")
            st.write(f"**Nguồn:** {item.get('sources', '')}")


def _render_classroom_packages(profile: dict[str, Any]) -> None:
    """Local teacher/student handoff; no account, network, or learner identity."""

    st.subheader("Giao bài và nộp kết quả bằng tệp")
    st.caption(
        "Giáo viên tạo gói giao bài (.json), học sinh làm trên máy rồi xuất gói kết quả. "
        "Chỉ dùng mã học sinh tự đặt; không đưa họ tên, email, số điện thoại, danh mục hay khóa API."
    )
    lessons = uni.all_lessons() if lmode.get_mode(st.session_state) == lmode.MODE_UNIVERSITY else cur.all_lessons()
    lesson_map = {lesson.lesson_id: lesson for lesson in lessons}
    with st.expander("Giáo viên: tạo gói giao bài", expanded=True):
        assignment_id = st.text_input("Mã bài giao (assignment ID):", value="bai-01", key="cp_assignment_id")
        title = st.text_input("Tên bài:", value="Bài tự luyện tài chính", key="cp_assignment_title")
        instructions = st.text_area(
            "Yêu cầu:", value="Hoàn thành các mô-đun đã chọn và ghi lại một điều còn chưa rõ.",
            key="cp_assignment_instructions",
        )
        selected = st.multiselect(
            "Mô-đun giao:", list(lesson_map), default=list(lesson_map)[:1],
            format_func=lambda key: lesson_map[key].title, key="cp_assignment_lessons",
        )
        due_label = st.text_input("Hạn nộp (nhãn tùy chọn):", key="cp_assignment_due")
        if st.button("Tạo gói giao bài", key="cp_make_assignment", type="primary"):
            try:
                assignment = cp.make_assignment(
                    assignment_id=assignment_id, title=title, instructions=instructions,
                    lesson_ids=selected, learner_track=lmode.get_mode(st.session_state),
                    due_label=due_label,
                )
                st.session_state["classroom_assignment"] = assignment
                st.success("Đã tạo gói. Gửi tệp này cho học sinh qua kênh của lớp.")
            except cp.ClassroomPackageError as exc:
                st.error(f"Gói bị từ chối: {exc}")
        assignment = st.session_state.get("classroom_assignment")
        if assignment:
            st.download_button(
                "Tải gói giao bài (.json)", cp.export_assignment(assignment),
                file_name=f"giao_bai_{assignment['id']}.json", mime="application/json",
                key="cp_download_assignment",
            )

    with st.expander("Học sinh: nạp gói và xuất kết quả"):
        upload_assignment = st.file_uploader(
            "Nạp gói giao bài (.json):", type=["json"], key="cp_upload_assignment"
        )
        if upload_assignment is not None and st.button("Kiểm tra gói giao bài", key="cp_import_assignment"):
            try:
                st.session_state["classroom_assignment"] = cp.import_assignment(upload_assignment.getvalue())
                st.success("Gói hợp lệ. Làm các mô-đun được giao trong Lộ trình học.")
            except cp.ClassroomPackageError as exc:
                st.error(f"Tệp bị từ chối: {exc}")
        assignment = st.session_state.get("classroom_assignment")
        if assignment:
            code = st.text_input(
                "Mã học sinh tự đặt (ví dụ HS-7F3K):", key="cp_student_code",
                help="Không dùng họ tên, email, số điện thoại hoặc mã trường.",
            )
            reflection = st.text_area("Tự phản tư sau khi làm:", key="cp_reflection")
            if st.button("Tạo gói kết quả", key="cp_make_result", type="primary"):
                try:
                    rows = []
                    for lesson_id in assignment["lesson_ids"]:
                        attempts = pp.lesson_attempts(profile, lesson_id)
                        rows.append({
                            "lesson_id": lesson_id,
                            "attempts": len(attempts),
                            "progress": pp.best_lesson_score(profile, lesson_id) or 0.0,
                        })
                    result = cp.make_result(
                        assignment=assignment, student_code=code,
                        lesson_attempts=rows, self_reflection=reflection,
                    )
                    st.session_state["classroom_result"] = result
                    st.success("Đã tạo gói kết quả. Gửi tệp cho giáo viên.")
                except cp.ClassroomPackageError as exc:
                    st.error(f"Gói bị từ chối: {exc}")
            result = st.session_state.get("classroom_result")
            if result:
                st.download_button(
                    "Tải gói kết quả (.json)", cp.export_result(result),
                    file_name=f"ket_qua_{result['assignment_id']}_{result['student_code']}.json",
                    mime="application/json", key="cp_download_result",
                )

    with st.expander("Giáo viên: xem gói kết quả"):
        upload_result = st.file_uploader("Nạp gói kết quả (.json):", type=["json"], key="cp_upload_result")
        if upload_result is not None and st.button("Kiểm tra gói kết quả", key="cp_import_result"):
            try:
                result = cp.import_result(upload_result.getvalue())
                st.success(
                    f"Gói hợp lệ · mã {result['student_code']} · "
                    f"{len(result['lesson_attempts'])} mô-đun · không chứa dữ liệu định danh."
                )
                st.json(result)
            except cp.ClassroomPackageError as exc:
                st.error(f"Tệp bị từ chối: {exc}")


# ---------------------------------------------------------------------------
# Cổng vốn thật
# ---------------------------------------------------------------------------

def render_readiness_gate() -> None:
    st.subheader("Sẵn sàng dùng vốn thật")
    guides.render_guide(guides.PANEL_READINESS)
    st.warning(
        "Ứng dụng **không** mở tài khoản, **không** giữ tiền và **không** gửi lệnh. "
        "Phần này chỉ giúp bạn tự soát trước khi bàn với người đại diện và công ty "
        "chứng khoán."
    )
    st.caption(
        "Ứng dụng chỉ hỏi **nhóm tuổi**. Không nhập căn cước, giấy khai sinh hay "
        "bất kỳ giấy tờ định danh nào — ứng dụng không lưu các dữ liệu đó."
    )

    bands = list(rg.AGE_BANDS)
    current = (st.session_state.get("readiness_state") or {}).get("age_band")
    idx = bands.index(current) if current in bands else 0
    band = st.radio(
        "Nhóm tuổi của bạn:", bands, index=idx,
        format_func=lambda b: rg.AGE_LABELS[b],
    )

    paper_done = st.checkbox("Tôi đã hoàn thành giai đoạn giao dịch mô phỏng bắt buộc.")
    guardian = st.checkbox("Người đại diện theo pháp luật đã đồng ý và cùng tham gia.")
    broker_ok = st.checkbox(
        "Công ty chứng khoán đã xác nhận bằng văn bản về chính sách cho độ tuổi của tôi."
    )
    risk_ok = st.checkbox("Tôi đã làm bài kiểm tra kiến thức và rủi ro.")

    gate_inputs = {
        "age_band": band,
        "paper_first_completed": paper_done,
        "guardian_confirmed": guardian,
        "broker_policy_confirmed": broker_ok,
        "risk_check_passed": risk_ok,
    }
    rg.store_gate_inputs(st.session_state, gate_inputs)
    # Nghiệm thu ROADMAP: mọi thay đổi chính sách phải có nhật ký.
    audit.sync_and_record(
        st.session_state, gate_inputs,
        snapshot_key="_gate_snapshot", note="Người học tự khai tại cổng",
    )

    # Luôn tính lại từ đầu vào, không đọc cờ đã lưu.
    decision = rg.evaluate_session(st.session_state)

    st.markdown("---")
    if decision.paper_only:
        # Không tô đỏ: "chỉ dùng mô phỏng" là trạng thái mặc định an toàn và
        # đúng đắn, không phải sự cố. Tô đỏ làm người học tưởng mình đang gặp
        # lỗi, trong khi đây chính là chỗ họ nên ở.
        st.info(
            "Kết luận: **chỉ dùng giao dịch mô phỏng trong ứng dụng.** "
            "Đây là trạng thái an toàn, không phải lỗi."
        )
    else:
        # Cố ý không dùng ngôn ngữ "đủ điều kiện": các ô trên là tự khai, ứng
        # dụng không xác minh được người đại diện hay chính sách công ty chứng
        # khoán. Trình bày dạng danh sách phải tự xác minh, không phải đèn xanh.
        st.info(
            "**Đây là danh sách bạn phải tự xác minh, không phải xác nhận của ứng dụng.**  \n"
            "Các ô ở trên do bạn tự khai. Ứng dụng không kiểm chứng được người đại "
            "diện hay chính sách của công ty chứng khoán, nên không thể và không "
            "kết luận rằng bạn đủ điều kiện."
        )

    if decision.outstanding:
        st.markdown("**Còn thiếu:**")
        for item in decision.outstanding:
            st.markdown(f"- {item}")

    if decision.notes:
        st.markdown("**Lưu ý:**")
        for note in decision.notes:
            st.markdown(f"- {note}")

    st.markdown("**Nhóm sản phẩm bị khóa:**")
    for product in decision.blocked_products:
        st.markdown(
            f"- 🔒 {rg.PRODUCT_LABELS.get(product, product)} — "
            f"{decision.block_reasons.get(product, '')}"
        )

    st.markdown("---")
    _render_risk_limits(band)


def _render_risk_limits(age_band: str) -> None:
    st.markdown("### Hạn mức rủi ro")
    ceiling_note = {
        rg.AGE_UNDER_15: "Nhóm dưới 15 tuổi không dùng vốn thật nên mọi hạn mức bằng 0.",
        rg.AGE_15_17: "Nhóm 15–dưới 18 tuổi có trần cứng chặt hơn và thời gian chờ dài hơn.",
        rg.AGE_18_PLUS: "Bạn có thể siết chặt hơn mức mặc định, nhưng không nới quá trần.",
    }.get(age_band, "Chọn nhóm tuổi để mở phần hạn mức.")
    st.caption(ceiling_note)

    stored = st.session_state.get("risk_limits")
    base = rlim.default_limits_for(age_band)
    if isinstance(stored, dict):
        try:
            base = rlim.RiskLimits(**stored)
        except TypeError:
            base = rlim.default_limits_for(age_band)

    c1, c2, c3 = st.columns(3)
    with c1:
        capital = st.number_input(
            "Hạn mức vốn (VND):", min_value=0.0,
            value=float(base.capital_cap_vnd if base.capital_cap_vnd != float("inf") else 0.0),
            step=1_000_000.0, key="rl_capital",
        )
        cooldown = st.number_input(
            "Thời gian chờ trước lệnh (phút):", min_value=0,
            value=int(base.cooldown_minutes), step=15, key="rl_cooldown",
        )
    with c2:
        pos = st.slider(
            "Tỷ trọng tối đa mỗi mã:", 0.0, 1.0,
            float(base.max_position_fraction), 0.01, key="rl_pos",
        )
        sector = st.slider(
            "Tỷ trọng tối đa mỗi ngành:", 0.0, 1.0,
            float(base.max_sector_fraction), 0.01, key="rl_sector",
        )
    with c3:
        daily = st.slider(
            "Mức lỗ tối đa trong ngày:", 0.0, 0.10,
            float(base.max_daily_loss_fraction), 0.005, key="rl_daily",
        )
        monthly = st.slider(
            "Mức lỗ tối đa trong tháng:", 0.0, 0.25,
            float(base.max_monthly_loss_fraction), 0.005, key="rl_monthly",
        )

    # Ép về trần cứng của nhóm tuổi: người học siết được, nới thì không.
    applied = rlim.clamp_to_age(
        rlim.RiskLimits(
            capital_cap_vnd=capital, max_position_fraction=pos,
            max_sector_fraction=sector, max_daily_loss_fraction=daily,
            max_monthly_loss_fraction=monthly, cooldown_minutes=int(cooldown),
        ),
        age_band,
    )
    st.session_state["risk_limits"] = applied.as_dict()
    audit.sync_and_record(
        st.session_state, applied.as_dict(),
        snapshot_key="_limits_snapshot", note="Thay đổi hạn mức rủi ro",
    )

    if applied.as_dict() != {
        "capital_cap_vnd": capital, "max_position_fraction": pos,
        "max_sector_fraction": sector, "max_daily_loss_fraction": daily,
        "max_monthly_loss_fraction": monthly, "cooldown_minutes": int(cooldown),
    }:
        st.warning(
            "Một vài giá trị đã được siết về trần cứng của nhóm tuổi. "
            "Bạn có thể đặt chặt hơn, nhưng không nới rộng hơn trần."
        )

    st.dataframe(
        [{"Hạn mức": audit.FIELD_LABELS.get(k, k), "Đang áp dụng": v}
         for k, v in applied.as_dict().items()],
        width="stretch",
    )
    st.caption(
        "Kế hoạch vượt ngưỡng mềm cần xác nhận hai bước. Chạm giới hạn lỗ ngày "
        "hoặc tháng thì bị chặn, không có xác nhận nào bỏ qua được."
    )


def render_policy_audit() -> None:
    st.subheader("Lịch sử thiết lập")
    guides.render_guide(guides.PANEL_POLICY)
    st.caption(
        "Ghi lại mọi lần đổi nhóm tuổi, đổi xác nhận hay đổi hạn mức rủi ro. "
        "Khác với **Nhật ký quyết định** — nơi bạn tự viết lý do trước khi đặt "
        "lệnh. Mục này do ứng dụng tự ghi, không chứa giấy tờ định danh."
    )
    rows = audit.audit_rows(st.session_state)
    if not rows:
        st.info("Chưa có thay đổi chính sách nào được ghi.")
        return
    st.dataframe(rows, width="stretch")
    st.download_button(
        "⬇️ Tải nhật ký chính sách (JSON)",
        audit.export_json(st.session_state).encode("utf-8"),
        file_name="nhat_ky_chinh_sach.json",
        mime="application/json",
    )


def render_provider_directory() -> None:
    st.subheader("Nơi mở tài khoản")
    guides.render_guide(guides.PANEL_PROVIDERS)
    st.caption(
        "Danh sách xếp theo bảng chữ cái, không xếp hạng, không mã giới thiệu và "
        "không tiếp thị liên kết. Ứng dụng không nhận hoa hồng từ bất kỳ đơn vị nào."
    )
    st.warning(
        "Điều kiện tuổi và sản phẩm thay đổi theo thời gian. Trước khi mở tài khoản, "
        "hãy đối chiếu tư cách thành viên tại danh sách của Tổng công ty Lưu ký và "
        "Bù trừ chứng khoán Việt Nam (VSDC) và hỏi trực tiếp nhà cung cấp."
    )
    st.dataframe(pdir.directory_rows(), width="stretch")
    st.markdown(f"- Tra tư cách thành viên: [{pdir.VSDC_MEMBER_LIST}]({pdir.VSDC_MEMBER_LIST})")

    for provider in pdir.all_providers():
        with st.expander(provider.legal_name):
            st.markdown(f"- Trang chính chủ: [{provider.official_url}]({provider.official_url})")
            st.markdown(f"- Nhóm sản phẩm: {', '.join(provider.products)}")
            st.markdown(f"- Chính sách tuổi: **{provider.age_policy_display()}**")
            for note in provider.notes:
                st.markdown(f"- {note}")
