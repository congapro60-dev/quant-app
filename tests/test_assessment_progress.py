import json

import curriculum as cur
import progress_profile as pp


def test_lesson_attempt_history_keeps_latest_and_best_scores():
    profile = pp.empty_profile()
    pp.record_lesson_attempt(profile, "m1", 40, {"q1": False})
    pp.record_lesson_attempt(profile, "m1", 90, {"q1": True})
    assert [a["score"] for a in pp.lesson_attempts(profile, "m1")] == [40.0, 90.0]
    assert pp.best_lesson_score(profile, "m1") == 90.0
    assert profile["lesson_scores"]["m1"] == 90.0


def test_diagnostic_uses_answers_and_records_wrong_questions():
    lessons = cur.all_lessons()[:1]
    responses = {q.qid: q.answer_index if q.kind == cur.QUESTION_SINGLE else q.answer_value
                 for q in lessons[0].questions}
    result = pp.grade_diagnostic(lessons, responses)
    profile = pp.empty_profile()
    pp.record_diagnostic(profile, result, which="pre_test")
    assert result["score"] == 100.0
    assert profile["pre_test"]["score"] == 100.0
    assert len(pp.diagnostic_attempts(profile, "pre_test")) == 1


def test_self_reflection_never_changes_official_rubric():
    profile = pp.empty_profile()
    profile["self_reflection_scores"] = {"lap_luan": 100, "rui_ro_nguon": 100, "nhat_ky": 100}
    assert pp.compute_rubric(profile).total == 0.0


def test_old_profile_rubric_values_are_not_promoted_to_official_scores():
    restored = pp.import_json(json.dumps({
        "schema_version": 1,
        "rubric_scores": {"lap_luan": 100, "rui_ro_nguon": 100, "nhat_ky": 100},
    }))
    assert restored["rubric_scores"] == {}
    assert restored["self_reflection_scores"] == {
        "lap_luan": 100.0, "rui_ro_nguon": 100.0, "nhat_ky": 100.0,
    }
