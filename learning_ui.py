"""Giao diện cho hai khu vực mới: Lộ trình học, Nhật ký và tiến độ.

Tách khỏi ``app.py`` theo đúng nếp của ``investment_ui.py`` để tệp giao diện
chính không phình thêm.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

import curriculum as cur
import feature_guides as guides
import learning_modes as lmode
import policy_audit as audit
import progress_profile as pp
import provider_directory as pdir
import readiness_gate as rg
import risk_limits as rlim


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
        "do": "Nhập mã ở thanh bên rồi bấm Phân tích. Đối chiếu phiên dữ liệu và nguồn.",
        "where": "Khám phá dữ liệu → Giá trong phiên",
        "trap": "Dữ liệu lỗi vẫn cho ra hệ số đẹp. Kiểm tra trước, đừng tin bảng kết quả.",
    },
    {
        "title": "2. Mô hình chỉ số đơn (SIM)",
        "goal": "Ước lượng beta, tách rủi ro hệ thống khỏi rủi ro riêng lẻ.",
        "do": "Chạy hồi quy từng mã theo chỉ số, đọc beta, R² và phần dư.",
        "where": "Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn (SIM)",
        "trap": "R² cao không có nghĩa mô hình đúng; phải xem chẩn đoán phần dư.",
    },
    {
        "title": "3. Chẩn đoán khuyết tật mô hình",
        "goal": "Biết khi nào suy diễn thống kê từ mô hình là không dùng được.",
        "do": "Đọc kiểm định White, Breusch–Godfrey, Ramsey RESET và Jarque–Bera.",
        "where": "Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn (SIM)",
        "trap": "Phương sai sai số thay đổi làm sai số chuẩn sai, kéo theo t và F sai.",
    },
    {
        "title": "4. Danh mục trung bình–phương sai (Markowitz)",
        "goal": "Tìm danh mục biến động nhỏ nhất và danh mục Sharpe cao nhất.",
        "do": "Chọn từ hai mã trở lên, xem tỷ trọng và đường biên hiệu quả.",
        "where": "Phòng thí nghiệm mô hình → Danh mục Markowitz",
        "trap": "Tỷ trọng tối ưu rất nhạy với lợi suất kỳ vọng; sai đầu vào là sai tất cả.",
    },
    {
        "title": "5. Kiểm thử ngoài mẫu (out-of-sample backtest)",
        "goal": "Xem chiến lược còn đứng vững khi rời khỏi dữ liệu đã dùng để xây.",
        "do": "Chạy kiểm thử cuốn chiếu, tính đủ phí, thuế và trượt giá.",
        "where": "Phòng thí nghiệm mô hình → Kiểm thử ngoài mẫu",
        "trap": "Quyết định tại T phải thực thi từ T+1; trộn lẫn là rò rỉ tương lai.",
    },
    {
        "title": "6. EViews tiếng Việt và ôn thi",
        "goal": "Làm lại bài tập trên lớp và đối chiếu đáp án.",
        "do": "Tải tệp của bạn, gõ lệnh LS/GENR/ADF quen thuộc.",
        "where": "Khám phá dữ liệu → EViews tiếng Việt",
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
        "Bản đồ sáu bước dẫn tới đúng công cụ trong ứng dụng, kèm cái bẫy hay "
        "gặp ở mỗi bước. Đây không phải bài giảng nhập môn."
    )
    for step in UNIVERSITY_TRACK:
        with st.expander(step["title"]):
            st.markdown(f"**Mục tiêu.** {step['goal']}")
            st.markdown(f"**Cần làm.** {step['do']}")
            st.markdown(f"**Ở đâu.** {step['where']}")
            st.warning(f"**Dễ sai.** {step['trap']}")

    st.markdown("---")
    with st.expander("📗 Cần ôn lại nền tảng? Mở sáu mô-đun trung học phổ thông"):
        st.caption(
            "Dành cho người muốn xem lại khái niệm gốc: lãi kép, lợi suất, "
            "biến động, tương quan và nhân quả."
        )
        _render_highschool_track(compact=True)


def _render_highschool_track(compact: bool = False) -> None:
    if not compact:
        st.header("Lộ trình học")
    st.caption(
        "Sáu mô-đun nền tảng. Bài làm được chấm ngay trên máy, không cần khóa "
        "giao diện lập trình (API) hay kết nối tới trí tuệ nhân tạo (AI)."
    )

    profile = _profile()
    scores = profile.setdefault("lesson_scores", {})

    done = sum(1 for l in cur.all_lessons() if scores.get(l.lesson_id, 0) >= cur.UNLOCK_THRESHOLD)
    st.progress(
        min(1.0, done / cur.UNLOCK_REQUIRED_LESSONS),
        text=f"Đã đạt {done}/{cur.UNLOCK_REQUIRED_LESSONS} mô-đun cần thiết để mở khóa công cụ nâng cao",
    )

    titles = [f"{l.order}. {l.title}" for l in cur.all_lessons()]
    picked = st.selectbox("Chọn mô-đun:", range(len(titles)), format_func=lambda i: titles[i])
    lesson = cur.all_lessons()[picked]

    st.subheader(lesson.title)
    current = scores.get(lesson.lesson_id)
    if current is not None:
        st.caption(f"Điểm gần nhất của bạn: **{current:.0f}/100**")

    st.markdown("#### 🎯 Mục tiêu")
    st.write(lesson.objective)

    st.markdown("#### 📖 Giải thích")
    st.write(lesson.explanation)

    st.markdown("#### 🧮 Ví dụ")
    st.write(lesson.example)

    st.markdown("#### 🛠️ Thực hành")
    st.info(lesson.interactive)

    st.markdown("#### ✍️ Câu hỏi")
    with st.form(f"quiz_{lesson.lesson_id}"):
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
                    key=f"{q.qid}_r", label_visibility="collapsed",
                )
            else:
                # value=None vì lý do tương tự: ô để trống phải khác với số 0
                # do học sinh chủ động nhập.
                responses[q.qid] = st.number_input(
                    "Nhập kết quả:", value=None, step=0.01,
                    placeholder="Nhập số…",
                    key=f"{q.qid}_n", label_visibility="collapsed",
                )
        submitted = st.form_submit_button("Nộp bài", type="primary")

    if submitted:
        score = lesson.grade(responses)
        pp.record_lesson(profile, lesson.lesson_id, score)
        if score >= cur.UNLOCK_THRESHOLD:
            st.success(f"Bạn được {score:.0f}/100. Đạt yêu cầu của mô-đun này.")
        else:
            st.warning(f"Bạn được {score:.0f}/100. Cần từ {cur.UNLOCK_THRESHOLD:.0f} điểm để đạt.")

        st.markdown("##### Đáp án và giải thích")
        for idx, q in enumerate(lesson.questions, start=1):
            ok = q.check(responses.get(q.qid))
            st.markdown(f"{'✅' if ok else '❌'} **Câu {idx}.** {q.explanation}")

        if (cur.should_unlock_advanced(profile.get("lesson_scores"))
                and not st.session_state.get(lmode.UNLOCK_KEY)):
            st.session_state[lmode.UNLOCK_KEY] = True
            st.success(
                "🔓 Bạn đã mở khóa nhóm công cụ nâng cao: mô hình chỉ số đơn (SIM), "
                "Markowitz, EViews và kiểm thử ngoài mẫu (out-of-sample backtest)."
            )
            # Danh sách thẻ được dựng ở đầu app.py nên phải chạy lại cả trang,
            # nếu không các thẻ vừa mở khóa chỉ hiện ở lần tương tác kế tiếp.
            st.rerun()

    st.markdown("#### ⚠️ Lỗi hiểu sai thường gặp")
    for wrong, correction in lesson.misconceptions:
        with st.expander(f"“{wrong}”"):
            st.write(correction)

    st.markdown("#### 📚 Nguồn học liệu")
    for name, url in lesson.resources:
        st.markdown(f"- [{name}]({url})")


# ---------------------------------------------------------------------------
# Khu vực: Nhật ký và tiến độ
# ---------------------------------------------------------------------------

def render_journal_area() -> None:
    st.header("Nhật ký và tiến độ")
    profile = _profile()

    # "Sẵn sàng dùng vốn thật" và "Nơi mở tài khoản" đã chuyển sang khu Đầu tư,
    # nơi chúng thuộc về. Trước đây chúng nằm ở đây chỉ vì tiện lúc viết mã.
    tab_progress, tab_journal, tab_settings = st.tabs(
        ["Tiến độ và rubric", "Nhật ký quyết định", "Lịch sử thiết lập"]
    )

    with tab_progress:
        _render_progress(profile)
    with tab_journal:
        _render_journal(profile)
    with tab_settings:
        render_policy_audit()


def _render_progress(profile: dict[str, Any]) -> None:
    guides.render_guide(guides.PANEL_PROGRESS)
    st.subheader("Bài kiểm tra đầu vào và đầu ra")
    c1, c2 = st.columns(2)
    with c1:
        pre = st.number_input("Điểm kiểm tra đầu vào (pre-test):", 0.0, 100.0, step=1.0)
        if st.button("Lưu điểm đầu vào"):
            pp.record_test(profile, "pre_test", pre)
            st.success("Đã lưu.")
    with c2:
        post = st.number_input("Điểm kiểm tra đầu ra (post-test):", 0.0, 100.0, step=1.0)
        if st.button("Lưu điểm đầu ra"):
            pp.record_test(profile, "post_test", post)
            st.success("Đã lưu.")

    st.subheader("Điểm từng mô-đun")
    scores = profile.get("lesson_scores") or {}
    if scores:
        st.dataframe(
            [{"Mô-đun": (cur.get_lesson(k).title if cur.get_lesson(k) else k),
              "Điểm": v} for k, v in scores.items()],
            width="stretch",
        )
    else:
        st.info("Chưa có mô-đun nào được chấm.")

    st.subheader("Điểm tổng theo rubric")
    st.caption(
        "Kiến thức 30%, lập luận 30%, kỷ luật rủi ro và chất lượng nguồn 25%, "
        "nhật ký và phản tư 15%."
    )
    manual = profile.setdefault("rubric_scores", {k: 0.0 for k in pp.RUBRIC_WEIGHTS})
    cols = st.columns(3)
    for col, key in zip(cols, ("lap_luan", "rui_ro_nguon", "nhat_ky")):
        with col:
            manual[key] = st.number_input(
                pp.RUBRIC_LABELS[key], 0.0, 100.0,
                value=float(manual.get(key, 0.0)), step=1.0, key=f"rub_{key}",
            )

    result = pp.compute_rubric(profile)
    st.dataframe(result.as_rows(), width="stretch")
    st.metric("Tổng điểm", f"{result.total:.2f}/100")
    st.caption("Điểm này đo năng lực và kỷ luật, không đo lợi nhuận.")

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
        st.error("Kết luận: **chỉ dùng giao dịch mô phỏng trong ứng dụng.**")
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
