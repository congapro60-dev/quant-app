"""Real Streamlit reruns: lesson navigation, grading feedback, and unlocks."""

import pytest
from streamlit.testing.v1 import AppTest

import curriculum as cur
import curriculum_university as uni
import learning_modes as lmode
import progress_profile as pp


def _run(mode=lmode.MODE_HIGHSCHOOL, scores=None):
    at = AppTest.from_string(
        "from learning_ui import render_learning_area\nrender_learning_area()",
        default_timeout=30,
    )
    profile = pp.empty_profile()
    profile["lesson_scores"] = dict(scores or {})
    at.session_state["progress_profile"] = profile
    at.session_state[lmode.MODE_KEY] = mode
    at.run()
    assert not at.exception
    return at


def _submit(at, lesson, prefix, *, correct=False):
    if correct:
        for question in lesson.questions:
            if question.kind == cur.QUESTION_SINGLE:
                at.radio(key=f"{prefix}_{question.qid}_r").set_value(question.answer_index)
            else:
                at.number_input(key=f"{prefix}_{question.qid}_n").set_value(question.answer_value)
    at.button(key=f"FormSubmitter:quiz_{prefix}_{lesson.lesson_id}-Nộp bài").click().run()
    assert not at.exception
    return at


@pytest.mark.parametrize("mode,prefix,lessons", [
    (lmode.MODE_HIGHSCHOOL, "thpt", cur.all_lessons()),
    (lmode.MODE_UNIVERSITY, "dh", uni.all_lessons()),
])
def test_continue_previous_next_preserve_scores(mode, prefix, lessons):
    scores = {lessons[0].lesson_id: 70, lessons[1].lesson_id: 69,
              lessons[2].lesson_id: 100}
    at = _run(mode, scores)
    assert at.selectbox(key=f"{prefix}_pick").value == 1
    at.button(key=f"{prefix}_next").click().run()
    assert at.selectbox(key=f"{prefix}_pick").value == 2
    at.button(key=f"{prefix}_previous").click().run()
    assert at.selectbox(key=f"{prefix}_pick").value == 1
    at.selectbox(key=f"{prefix}_pick").set_value(len(lessons) - 1).run()
    assert at.button(key=f"{prefix}_next").disabled
    at.button(key=f"{prefix}_continue").click().run()
    assert at.selectbox(key=f"{prefix}_pick").value == 1
    at.selectbox(key=f"{prefix}_pick").set_value(0).run()
    assert at.button(key=f"{prefix}_previous").disabled
    assert not at.exception
    assert at.session_state["progress_profile"]["lesson_scores"] == scores


def test_finished_track_keeps_review_available():
    at = _run(scores={lesson.lesson_id: 100 for lesson in cur.all_lessons()})
    assert at.button(key="thpt_continue").disabled
    assert not at.button(key="thpt_next").disabled
    at.button(key="thpt_next").click().run()
    assert at.selectbox(key="thpt_pick").value == 1
    assert not at.exception


@pytest.mark.parametrize("mode,prefix,lesson", [
    (lmode.MODE_HIGHSCHOOL, "thpt", cur.all_lessons()[0]),
    (lmode.MODE_UNIVERSITY, "dh", uni.all_lessons()[0]),
])
def test_blank_answers_remain_wrong_and_feedback_survives_rerun(mode, prefix, lesson):
    at = _run(mode)
    quiz_keys = tuple(f"{prefix}_{q.qid}_" for q in lesson.questions)
    assert all(widget.value is None for widget in at.radio if widget.key.startswith(quiz_keys))
    assert all(widget.value is None for widget in at.number_input if widget.key.startswith(quiz_keys))
    _submit(at, lesson, prefix)
    assert at.session_state["progress_profile"]["lesson_scores"][lesson.lesson_id] == 0
    assert at.session_state["lesson_feedback"][lesson.lesson_id]["correct"] == [False] * len(lesson.questions)
    assert not at.session_state.filtered_state.get(lmode.UNLOCK_KEY, False)
    at.run()
    assert not at.exception
    assert any("0/100" in warning.value for warning in at.warning)
    for question in lesson.questions:
        assert any(question.explanation in item.value for item in at.markdown)


def test_unlock_rerun_retains_feedback_and_selected_lesson():
    lessons = cur.all_lessons()
    scores = {lesson.lesson_id: 100 for lesson in lessons[:3]}
    at = _run(scores=scores)
    lesson = lessons[3]
    _submit(at, lesson, "thpt", correct=True)
    assert at.session_state[lmode.UNLOCK_KEY] is True
    assert at.selectbox(key="thpt_pick").value == 3
    assert any("100/100" in success.value for success in at.success)
    assert any("mở khóa" in success.value for success in at.success)
    assert any("4/4" in item.proto.text for item in at.get("progress"))
    saved = dict(at.session_state["lesson_feedback"][lesson.lesson_id])
    at.run()
    assert at.session_state["lesson_feedback"][lesson.lesson_id] == saved
    at.button(key="thpt_next").click().run()
    assert not any("Kết quả lần nộp gần nhất" in item.value for item in at.markdown)
    at.button(key="thpt_previous").click().run()
    assert any("100/100" in success.value for success in at.success)
    assert at.session_state["lesson_feedback"][lesson.lesson_id] == saved
    assert not at.exception


def test_latest_submission_replaces_feedback_without_changing_unlock_rules():
    lesson = uni.all_lessons()[0]
    at = _run(lmode.MODE_UNIVERSITY)
    _submit(at, lesson, "dh", correct=True)
    assert at.session_state["progress_profile"]["lesson_scores"][lesson.lesson_id] == 100
    assert not at.session_state.filtered_state.get(lmode.UNLOCK_KEY, False)
    for question in lesson.questions:
        if question.kind == cur.QUESTION_SINGLE:
            at.radio(key=f"dh_{question.qid}_r").set_value((question.answer_index + 1) % len(question.options))
        else:
            at.number_input(key=f"dh_{question.qid}_n").set_value(question.answer_value + 100)
    _submit(at, lesson, "dh")
    assert at.session_state["progress_profile"]["lesson_scores"][lesson.lesson_id] == 0
    assert not at.session_state["lesson_feedback"][lesson.lesson_id]["unlocked"]
    assert any("0/100" in warning.value for warning in at.warning)
    assert not any("100/100" in success.value for success in at.success)


def test_university_practice_buttons_match_lesson_instructions(monkeypatch):
    import learning_ui

    destinations = []
    monkeypatch.setattr(learning_ui, "navigate_to", lambda *args: destinations.append(args))
    at = _run(lmode.MODE_UNIVERSITY)
    expected = [lmode.FEATURE_EXAM, lmode.FEATURE_EXAM, lmode.FEATURE_SIM,
                lmode.FEATURE_SIM, lmode.FEATURE_EVIEWS, lmode.FEATURE_EXAM]
    for index, feature in enumerate(expected):
        at.selectbox(key="dh_pick").set_value(index).run()
        at.button(key="dh_practice").click().run()
        assert destinations[-1] == (lmode.FEATURES[feature]["area"], feature)
    at.button(key="dh_map_0").click().run()
    assert destinations[-1] == (lmode.AREA_DATA, "history")
    assert "Lịch sử giá cuối ngày" in learning_ui.UNIVERSITY_TRACK[0]["where"]
    assert not at.exception


def test_every_highschool_lesson_has_a_real_practice_action():
    at = _run(lmode.MODE_HIGHSCHOOL)
    expected_keys = {
        cur.INTERACTIVE_COMPOUND: "thpt_compound_run",
        cur.INTERACTIVE_MARKET: "thpt_practice",
        cur.INTERACTIVE_RETURN: "thpt_practice",
        cur.INTERACTIVE_RISK: "thpt_risk_run",
        cur.INTERACTIVE_CHART: "thpt_practice",
        cur.INTERACTIVE_PAPER: "thpt_practice",
        cur.INTERACTIVE_SAI_SO: "thpt_saiso_run",
        cur.INTERACTIVE_DAC_TRUNG: "thpt_ungrouped_run",
        cur.INTERACTIVE_GHEP_NHOM: "thpt_grouped_run",
        cur.INTERACTIVE_PHAN_TAN: "thpt_practice",
    }
    for index, lesson in enumerate(cur.all_lessons()):
        at.selectbox(key="thpt_pick").set_value(index).run()
        assert not at.exception
        assert at.button(key=expected_keys[lesson.interactive_kind])
