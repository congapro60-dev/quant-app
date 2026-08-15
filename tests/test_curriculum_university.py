"""Kiểm thử bài học bậc đại học, bám giáo trình môn học tại chỗ."""

from __future__ import annotations

import pytest

import curriculum as cur
import curriculum_university as uni


EXPECTED_IDS = [
    "dh1_loi_suat",
    "dh2_do_dao_dong",
    "dh3_sim_gia_thiet",
    "dh4_phan_ra_rui_ro",
    "dh5_quy_trinh_uoc_luong",
    "dh6_markowitz",
]


def test_six_lessons_in_declared_order():
    lessons = uni.all_lessons()
    assert len(lessons) == 6
    assert [l.lesson_id for l in lessons] == EXPECTED_IDS
    assert [l.order for l in lessons] == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("lesson", list(uni.UNIVERSITY_LESSONS), ids=lambda l: l.lesson_id)
def test_each_lesson_has_all_seven_parts(lesson):
    assert lesson.objective.strip()
    assert lesson.explanation.strip()
    assert lesson.example.strip()
    assert lesson.interactive.strip()
    assert lesson.questions
    assert lesson.misconceptions
    assert lesson.resources


@pytest.mark.parametrize("lesson", list(uni.UNIVERSITY_LESSONS), ids=lambda l: l.lesson_id)
def test_question_count_between_three_and_five(lesson):
    assert 3 <= len(lesson.questions) <= 5


@pytest.mark.parametrize("lesson", list(uni.UNIVERSITY_LESSONS), ids=lambda l: l.lesson_id)
def test_every_question_has_gold_answer_and_explanation(lesson):
    for q in lesson.questions:
        assert q.prompt.strip()
        assert q.explanation.strip()
        if q.kind == cur.QUESTION_SINGLE:
            assert q.options and q.answer_index is not None
            assert 0 <= q.answer_index < len(q.options)
        else:
            assert q.answer_value is not None


def test_question_ids_do_not_collide_with_highschool():
    """Điểm lưu theo lesson_id và qid nên hai lộ trình không được trùng khóa."""

    uni_ids = {q.qid for l in uni.UNIVERSITY_LESSONS for q in l.questions}
    hs_ids = {q.qid for l in cur.LESSONS for q in l.questions}
    assert uni_ids & hs_ids == set()

    uni_lessons = {l.lesson_id for l in uni.UNIVERSITY_LESSONS}
    hs_lessons = {l.lesson_id for l in cur.LESSONS}
    assert uni_lessons & hs_lessons == set()


def test_grading_works_and_needs_no_api(monkeypatch):
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    lesson = uni.get_lesson("dh3_sim_gia_thiet")
    answers = {
        q.qid: (q.answer_index if q.kind == cur.QUESTION_SINGLE else q.answer_value)
        for q in lesson.questions
    }
    assert lesson.grade(answers) == 100.0


def test_unanswered_scores_zero():
    for lesson in uni.UNIVERSITY_LESSONS:
        assert lesson.grade({q.qid: None for q in lesson.questions}) == 0.0


# ---------------------------------------------------------------------------
# Bám đúng nội dung giáo trình
# ---------------------------------------------------------------------------

def test_sim_lesson_states_the_three_assumptions():
    text = uni.get_lesson("dh3_sim_gia_thiet").explanation
    assert "E(ε_i) = 0" in text
    assert "cov(ε_i, r_I) = 0" in text
    assert "cov(ε_i, ε_k) = 0" in text


def test_risk_split_lesson_carries_the_decomposition_formula():
    text = uni.get_lesson("dh4_phan_ra_rui_ro").explanation
    assert "σ_i² = β_i²·σ_I² + η_i²" in text


def test_risk_split_lesson_explains_r_squared_as_systematic_share():
    """Cách đọc R² này là điểm riêng của giáo trình, đáng khóa lại bằng kiểm thử."""

    text = uni.get_lesson("dh4_phan_ra_rui_ro").explanation
    assert "tỷ lệ rủi ro" in text.lower()
    assert "R²" in text


def test_portfolio_lesson_uses_matrix_form():
    text = uni.get_lesson("dh2_do_dao_dong").explanation
    assert "W′VW" in text


def test_markowitz_lesson_uses_textbook_letters():
    """Giáo trình đặt A = 1'V⁻¹1, B là số hạng chéo, C = r̄'V⁻¹r̄, D = AC − B².

    Nhiều tài liệu khác hoán đổi B và C. Bài học phải bám ký hiệu giáo trình vì
    sinh viên đối chiếu bài làm với giáo trình đó.
    """

    text = uni.get_lesson("dh6_markowitz").explanation
    assert "A = [1]′V⁻¹[1]" in text
    assert "B = [r̄]′V⁻¹[1]" in text
    assert "C = [r̄]′V⁻¹[r̄]" in text
    assert "D = A·C − B²" in text


def test_markowitz_question_matches_textbook_determinant():
    q = next(q for q in uni.get_lesson("dh6_markowitz").questions if q.qid == "dh6_q2")
    assert q.options[q.answer_index] == "D = A·C − B²"


def test_markowitz_lesson_warns_about_notation_differences():
    """Sinh viên phải biết chữ cái đổi vai trò giữa các tài liệu."""

    joined = " ".join(w + " " + c for w, c in uni.get_lesson("dh6_markowitz").misconceptions)
    assert "ký hiệu" in joined.lower()


def test_estimation_lesson_keeps_the_required_order():
    text = uni.get_lesson("dh5_quy_trinh_uoc_luong").explanation.lower()
    assert text.index("dừng") < text.index("ramsey")


def test_lessons_cite_the_local_course_material():
    for lesson in uni.UNIVERSITY_LESSONS:
        names = " ".join(name for name, _ in lesson.resources).lower()
        assert "tài liệu môn học" in names or "ôn thi" in names


def test_local_sources_carry_no_fabricated_url():
    """Tài liệu lưu hành nội bộ không có đường dẫn công khai; không được bịa."""

    for lesson in uni.UNIVERSITY_LESSONS:
        for name, url in lesson.resources:
            assert name.strip()
            assert url == "" or url.startswith("https://")


def test_total_questions_in_expected_range():
    assert 18 <= uni.total_questions() <= 30


def test_get_lesson_handles_unknown_id():
    assert uni.get_lesson("khong_co") is None
    assert uni.get_lesson("") is None
