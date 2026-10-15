"""Safety and round-trip checks for portable classroom packages."""

from __future__ import annotations

import json

import pytest

import classroom_packages as cp


def _assignment() -> dict:
    return cp.make_assignment(
        assignment_id="bai-01",
        title="Đọc biểu đồ",
        instructions="Hoàn thành bài học, ghi lại một điều còn chưa rõ.",
        lesson_ids=["bai-1", "bai-2"],
        learner_track="thpt",
        due_label="Cuối tuần",
    )


def _result() -> dict:
    return cp.make_result(
        assignment=_assignment(),
        student_code="HS-7F3K",
        lesson_attempts=[
            {"lesson_id": "bai-1", "attempts": 2, "progress": 80},
            {"lesson_id": "bai-2", "attempts": 1, "progress": 100},
        ],
        self_reflection="Em cần luyện thêm cách đọc trục thời gian.",
    )


def test_assignment_has_only_portable_fields_and_round_trips_as_bytes():
    assignment = _assignment()
    assert set(assignment) == cp.ASSIGNMENT_KEYS
    raw = cp.export_assignment(assignment)
    assert isinstance(raw, bytes)
    assert cp.import_assignment(raw) == assignment


def test_result_has_only_anon_student_fields_and_round_trips():
    result = _result()
    assert set(result) == cp.RESULT_KEYS
    assert result["assignment_id"] == "bai-01"
    assert cp.import_result(cp.export_result(result)) == result


@pytest.mark.parametrize("bad", [
    {"email": "student@example.com"},
    {"api_key": "sk-abcdefghijklmnopqrstuvwxyz"},
    {"holdings": {"CTG": 10}},
])
def test_rejects_unknown_or_sensitive_top_level_data(bad):
    payload = _assignment() | bad
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_assignment(json.dumps(payload))


def test_rejects_unknown_nested_attempt_keys_and_private_finance():
    payload = _result()
    payload["lesson_attempts"][0]["ticker"] = "CTG"
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_result(json.dumps(payload))


def test_result_must_use_lessons_from_assignment():
    with pytest.raises(cp.ClassroomPackageError):
        cp.make_result(
            assignment=_assignment(),
            student_code="HS-7F3K",
            lesson_attempts=[{"lesson_id": "bai-99", "attempts": 1, "progress": 10}],
        )


@pytest.mark.parametrize("code", ["Nguyễn Văn A", "student@example.com", "0901234567", "HS-abc"])
def test_rejects_non_anonymous_student_code(code):
    with pytest.raises(cp.ClassroomPackageError):
        cp.make_result(assignment=_assignment(), student_code=code, lesson_attempts=[])


def test_rejects_size_depth_and_pii_in_text():
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_assignment(json.dumps(_assignment() | {"id": "a" * 65}))
    with pytest.raises(cp.ClassroomPackageError):
        cp.make_assignment(
            assignment_id="bai-01", title="Bài", instructions="email student@example.com",
            lesson_ids=["bai-1"],
        )
    bomb = '{"lesson_attempts":' + "[" * 40 + "]" * 40 + "}"
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_result(bomb)


def test_rejects_unknown_result_fields_and_bad_progress():
    payload = _result() | {"private_note": "x"}
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_result(json.dumps(payload))
    payload = _result()
    payload["lesson_attempts"][0]["progress"] = 101
    with pytest.raises(cp.ClassroomPackageError):
        cp.import_result(json.dumps(payload))

