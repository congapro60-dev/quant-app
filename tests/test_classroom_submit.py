"""Submission boundary checks using fabricated classroom data only."""

from copy import deepcopy
import json
import subprocess
import sys

import pytest

import classroom_packages as cp
import classroom_submit as cs
import progress_profile as pp


@pytest.fixture
def assignment():
    return cp.make_assignment(
        assignment_id="cuoi-khoa-01", title="Bài cuối khoá",
        instructions="Hoàn thành hai mô-đun được giao.",
        lesson_ids=["m1_tien_ngan_sach", "m2_thi_truong"],
    )


@pytest.fixture
def profile():
    result = pp.empty_profile()
    pp.record_lesson_attempt(result, "m1_tien_ngan_sach", 50, {"m1_q1": False})
    pp.record_lesson_attempt(result, "m1_tien_ngan_sach", 100, {"m1_q1": True})
    pp.record_lesson_attempt(result, "m2_thi_truong", 75, {"m2_q1": True})
    pp.record_lesson_attempt(result, "not-assigned", 95)
    pp.record_test(result, "pre_test", 25)
    pp.record_diagnostic(result, {}, which="post_test")
    pp.add_journal_entry(result, title="Bản nháp riêng", decision="Chờ", sources="Nguồn đã đọc")
    return result


def _build(profile, assignment, **kwargs):
    return cs.build_submission(profile, assignment, kwargs.get("class_code", "LOP-10A"),
                               kwargs.get("student_code", "HS-7F3K"))


def _assert_clean(value):
    if isinstance(value, dict):
        # This is the existing filter, not a parallel list of sensitive keys.
        cp._reject_sensitive_key(value)
        for item in value.values():
            _assert_clean(item)
    elif isinstance(value, list):
        for item in value:
            _assert_clean(item)
    elif isinstance(value, str):
        cp._scan_text(value)


def test_summary_matches_actual_records_without_mutating_inputs(profile, assignment):
    original_profile, original_assignment = deepcopy(profile), deepcopy(assignment)
    result = _build(profile, assignment)
    assert set(result) == {"schema_version", "class_code", "student_code", "assignment_id",
                           "lesson_results", "diagnostics", "journal_count"}
    assert result["class_code"] == "LOP-10A"
    assert result["assignment_id"] == assignment["id"]
    assert result["lesson_results"] == [
        {"lesson_id": "m1_tien_ngan_sach", "latest_score": 100, "best_score": 100, "attempt_count": 2},
        {"lesson_id": "m2_thi_truong", "latest_score": 75, "best_score": 75, "attempt_count": 1},
    ]
    assert result["diagnostics"] == {
        "pre_test": {"score": 25, "attempt_count": 0},
        "post_test": {"score": 0, "attempt_count": 1},
    }
    assert result["journal_count"] == 1
    assert len(cp._encode(result)) <= cp.MAX_IMPORT_BYTES
    _assert_clean(result)
    assert (profile, assignment) == (original_profile, original_assignment)


@pytest.mark.parametrize("marker", cp._PII_MARKERS)
def test_pii_is_never_copied_from_profile(profile, assignment, marker):
    profile[marker] = "PRIVATE_PII_SENTINEL"
    profile["journal"][0]["title"] = "Nguyễn Văn A · student@example.com · 0901234567"
    result = _build(profile, assignment)
    raw = json.dumps(result, ensure_ascii=False)
    assert "PRIVATE_PII_SENTINEL" not in raw
    assert "Nguyễn Văn A" not in raw and "student@example.com" not in raw
    _assert_clean(result)


@pytest.mark.parametrize("marker", cp._SECRET_MARKERS + cp._PRIVATE_FINANCE_MARKERS)
def test_secrets_and_finance_are_never_copied(profile, assignment, marker):
    profile[marker] = {"value": "PRIVATE_FINANCE_SENTINEL"}
    result = _build(profile, assignment)
    assert "PRIVATE_FINANCE_SENTINEL" not in json.dumps(result)
    _assert_clean(result)


@pytest.mark.parametrize("field", ["class_code", "student_code"])
@pytest.mark.parametrize("bad", [None, "", " ", "../bad", "0901234567", "student@example.com", "a" * 65])
def test_missing_or_unsafe_codes_rejected(profile, assignment, field, bad):
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment, **{field: bad})


def test_oversized_input_rejected(profile, assignment):
    profile["journal"][0]["title"] = "x" * (cp.MAX_IMPORT_BYTES + 1)
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


def test_limit_uses_utf8_bytes_and_does_not_return_partial_payload(profile, assignment):
    profile["journal"][0]["title"] = "ệ" * (cp.MAX_IMPORT_BYTES // 2)
    assert len(json.dumps(profile, ensure_ascii=False).encode("utf-8")) > cp.MAX_IMPORT_BYTES
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


def test_output_size_limit_is_enforced_even_for_small_inputs(profile, assignment, monkeypatch):
    real_encode = cp._encode

    def small_output_limit(payload):
        if isinstance(payload, dict) and "class_code" in payload:
            monkeypatch.setattr(cp, "MAX_IMPORT_BYTES", 20)
        return real_encode(payload)

    monkeypatch.setattr(cp, "_encode", small_output_limit)
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


@pytest.mark.parametrize("bad", [True, "100", -1, 101, float("nan"), float("inf"), 10 ** 400])
def test_invalid_score_rejected(profile, assignment, bad):
    profile["lesson_attempts"]["m1_tien_ngan_sach"][-1]["score"] = bad
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


@pytest.mark.parametrize("field,bad", [("lesson_scores", []), ("lesson_attempts", []),
                                      ("diagnostic_attempts", []), ("journal", {})])
def test_wrong_profile_shapes_rejected(profile, assignment, field, bad):
    profile[field] = bad
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


def test_legacy_profile_keeps_missing_attempts_honest(assignment):
    result = _build({"lesson_scores": {"m1_tien_ngan_sach": 85}}, assignment)
    assert result["lesson_results"][0] == {
        "lesson_id": "m1_tien_ngan_sach", "latest_score": 85, "best_score": 85, "attempt_count": 0,
    }
    assert result["lesson_results"][1]["latest_score"] is None
    assert result["diagnostics"]["pre_test"]["score"] is None


def test_existing_filters_are_called(profile, assignment, monkeypatch):
    def reject(*args, **kwargs):
        raise cp.ClassroomPackageError("reused filter")

    monkeypatch.setattr(cp, "_reject_sensitive_key", reject)
    with pytest.raises(cs.SubmissionValidationError, match="reused filter"):
        _build(profile, assignment)


def test_bad_assignment_is_rejected(profile, assignment):
    assignment["email"] = "student@example.com"
    with pytest.raises(cs.SubmissionValidationError):
        _build(profile, assignment)


def test_submit_is_disabled_and_never_mints_a_receipt(profile, assignment, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        pytest.fail("Step 2 must never open a network connection")

    monkeypatch.setattr(socket, "socket", no_network)
    result = _build(profile, assignment)
    original = deepcopy(result)
    with pytest.raises(cs.SubmissionNotConfiguredError, match="chưa"):
        cs.submit(result)
    assert result == original


def test_import_has_no_streamlit_or_firebase_side_effects():
    subprocess.run([
        sys.executable, "-c",
        "import sys, classroom_submit; "
        "assert 'streamlit' not in sys.modules; assert 'firebase_admin' not in sys.modules",
    ], check=True, timeout=15)
