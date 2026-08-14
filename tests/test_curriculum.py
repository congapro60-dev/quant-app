"""Kiểm thử sáu mô-đun THPT: đủ cấu phần, chấm đúng, không cần API."""

from __future__ import annotations

import pytest

import curriculum as cur


EXPECTED_IDS = [
    "m1_tien_ngan_sach",
    "m2_co_phieu_thi_truong",
    "m3_gia_loi_suat",
    "m4_rui_ro_da_dang_hoa",
    "m5_bieu_do_nguon_tin",
    "m6_mo_phong_nhat_ky",
]


def test_exactly_six_modules_in_declared_order():
    lessons = cur.all_lessons()
    assert len(lessons) == 6
    assert [l.lesson_id for l in lessons] == EXPECTED_IDS
    assert [l.order for l in lessons] == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("lesson", list(cur.LESSONS), ids=lambda l: l.lesson_id)
def test_each_lesson_has_all_seven_required_parts(lesson):
    """Mục tiêu, giải thích, ví dụ, tương tác, câu hỏi, lỗi hiểu sai, nguồn."""

    assert lesson.objective.strip()
    assert lesson.explanation.strip()
    assert lesson.example.strip()
    assert lesson.interactive.strip()
    assert lesson.questions
    assert lesson.misconceptions
    assert lesson.resources


@pytest.mark.parametrize("lesson", list(cur.LESSONS), ids=lambda l: l.lesson_id)
def test_question_count_is_between_three_and_five(lesson):
    assert 3 <= len(lesson.questions) <= 5


@pytest.mark.parametrize("lesson", list(cur.LESSONS), ids=lambda l: l.lesson_id)
def test_each_lesson_lists_at_least_three_misconceptions(lesson):
    assert len(lesson.misconceptions) >= 3
    for wrong, correction in lesson.misconceptions:
        assert wrong.strip() and correction.strip()


@pytest.mark.parametrize("lesson", list(cur.LESSONS), ids=lambda l: l.lesson_id)
def test_resources_are_named_https_links(lesson):
    for name, url in lesson.resources:
        assert name.strip()
        assert url.startswith("https://"), url


@pytest.mark.parametrize("lesson", list(cur.LESSONS), ids=lambda l: l.lesson_id)
def test_every_question_has_a_gold_answer_and_explanation(lesson):
    for q in lesson.questions:
        assert q.prompt.strip()
        assert q.explanation.strip()
        if q.kind == cur.QUESTION_SINGLE:
            assert q.options and q.answer_index is not None
            assert 0 <= q.answer_index < len(q.options)
        elif q.kind == cur.QUESTION_NUMBER:
            assert q.answer_value is not None
        else:
            pytest.fail(f"Loại câu hỏi lạ: {q.kind}")


def test_question_ids_are_unique_across_all_modules():
    ids = [q.qid for lesson in cur.LESSONS for q in lesson.questions]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Chấm điểm cục bộ, không cần khoá API
# ---------------------------------------------------------------------------

def test_all_correct_scores_one_hundred():
    lesson = cur.get_lesson("m3_gia_loi_suat")
    answers = {
        q.qid: (q.answer_index if q.kind == cur.QUESTION_SINGLE else q.answer_value)
        for q in lesson.questions
    }
    assert lesson.grade(answers) == 100.0


def test_no_answers_scores_zero():
    lesson = cur.get_lesson("m1_tien_ngan_sach")
    assert lesson.grade({}) == 0.0
    assert lesson.grade(None) == 0.0


def test_partial_answers_score_proportionally():
    lesson = cur.get_lesson("m2_co_phieu_thi_truong")
    first = lesson.questions[0]
    score = lesson.grade({first.qid: first.answer_index})
    assert score == pytest.approx(100 / len(lesson.questions), abs=0.01)


def test_numeric_question_accepts_value_within_tolerance():
    q = cur.Question(
        qid="t", prompt="p", kind=cur.QUESTION_NUMBER,
        answer_value=23.15, tolerance=0.1,
    )
    assert q.check(23.2) is True
    assert q.check(23.15) is True
    assert q.check(25.0) is False


def test_question_rejects_wrong_types_safely():
    q = cur.Question(
        qid="t", prompt="p", kind=cur.QUESTION_NUMBER, answer_value=1.0,
    )
    for bad in (None, "abc", [], {}, float("nan")):
        assert q.check(bad) is False


def test_single_choice_rejects_bad_input():
    q = cur.Question(
        qid="t", prompt="p", kind=cur.QUESTION_SINGLE,
        options=("a", "b"), answer_index=1,
    )
    assert q.check(1) is True
    assert q.check("1") is True
    assert q.check(None) is False
    assert q.check("xyz") is False


def test_grading_needs_no_network_or_api_key(monkeypatch):
    """Chấm bài phải chạy được khi mọi biến môi trường khóa API bị xóa."""

    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    lesson = cur.get_lesson("m6_mo_phong_nhat_ky")
    answers = {q.qid: q.answer_index for q in lesson.questions}
    assert lesson.grade(answers) == 100.0


# ---------------------------------------------------------------------------
# Mở khóa công cụ nâng cao
# ---------------------------------------------------------------------------

def test_unlock_requires_four_passing_modules():
    assert cur.should_unlock_advanced({}) is False
    three = {EXPECTED_IDS[i]: 80 for i in range(3)}
    assert cur.should_unlock_advanced(three) is False
    four = {EXPECTED_IDS[i]: 80 for i in range(4)}
    assert cur.should_unlock_advanced(four) is True


def test_unlock_ignores_scores_below_threshold():
    weak = {EXPECTED_IDS[i]: 50 for i in range(6)}
    assert cur.should_unlock_advanced(weak) is False


def test_unlock_ignores_unknown_lesson_ids():
    fake = {f"bai_gia_{i}": 100 for i in range(10)}
    assert cur.should_unlock_advanced(fake) is False


def test_unlock_survives_malformed_scores():
    messy = {
        EXPECTED_IDS[0]: "rat gioi",
        EXPECTED_IDS[1]: None,
        EXPECTED_IDS[2]: 90,
        EXPECTED_IDS[3]: 90,
    }
    assert cur.should_unlock_advanced(messy) is False


def test_get_lesson_handles_missing_id():
    assert cur.get_lesson("khong_ton_tai") is None
    assert cur.get_lesson("") is None


def test_total_questions_between_eighteen_and_thirty():
    assert 18 <= cur.total_questions() <= 30
