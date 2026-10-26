"""Prepare minimal course submissions, without Streamlit or network access.

This step does not authenticate pupils, verify their scores, or write Firebase.
Class/student codes identify a submission; later access control must bind them
to an authenticated UID and the teacher's class membership.
"""

from __future__ import annotations

from collections.abc import Mapping

import classroom_packages as packages


class SubmissionValidationError(packages.ClassroomPackageError):
    """Input cannot safely be converted into a course summary."""


class SubmissionNotConfiguredError(RuntimeError):
    """Firebase transport is deliberately unavailable at this milestone."""


def _mapping(value):
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SubmissionValidationError("Trường dữ liệu phải là đối tượng.")
    return value


def _list(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise SubmissionValidationError("Lịch sử và nhật ký phải là danh sách.")
    return value


def _score(value):
    return None if value is None else packages._progress(value)


def _attempt_scores(attempts):
    scores = []
    for attempt in _list(attempts):
        record = _mapping(attempt)
        if record.get("score") is None:
            raise SubmissionValidationError("Lần làm bài phải có điểm.")
        scores.append(packages._progress(record["score"]))
    return scores


def _check_summary(value):
    """Reuse the existing sensitive-key/text filters at every output level."""
    if isinstance(value, dict):
        packages._reject_sensitive_key(value)
        for item in value.values():
            _check_summary(item)
    elif isinstance(value, list):
        for item in value:
            _check_summary(item)
    elif isinstance(value, str):
        packages._scan_text(value)


def build_submission(profile, assignment, class_code, student_code) -> dict:
    """Project actual local records onto a bounded, code-only summary.

    Only assigned lessons are included. Unattempted lessons retain null scores;
    old profiles keep their known score but do not invent attempt counts.
    Journals are reduced to a count: regex filters cannot reliably anonymise
    names inside free text, even when parental consent has been confirmed.
    Extra profile fields (including personal/financial data) are never copied.
    """
    try:
        if not isinstance(profile, Mapping):
            raise SubmissionValidationError("Hồ sơ phải là đối tượng.")
        # Bound input work and output bytes using the same classroom limit.
        packages._encode(dict(profile))
        clean_assignment = packages.import_assignment(packages.export_assignment(assignment))
        class_code = packages._id(class_code, "class_code")
        student_code = packages._student_code(student_code)
        latest = _mapping(profile.get("lesson_scores"))
        attempts = _mapping(profile.get("lesson_attempts"))
        lessons = []
        for lesson_id in clean_assignment["lesson_ids"]:
            scores = _attempt_scores(attempts.get(lesson_id))
            latest_score = scores[-1] if scores else _score(latest.get(lesson_id))
            lessons.append({
                "lesson_id": lesson_id,
                "latest_score": latest_score,
                "best_score": max(scores) if scores else latest_score,
                "attempt_count": len(scores),
            })
        history = _mapping(profile.get("diagnostic_attempts"))
        diagnostics = {}
        for name in ("pre_test", "post_test"):
            scores = _attempt_scores(history.get(name))
            diagnostics[name] = {
                "score": scores[-1] if scores else _score(_mapping(profile.get(name)).get("score")),
                "attempt_count": len(scores),
            }
        result = {
            "schema_version": 1,
            "class_code": class_code,
            "student_code": student_code,
            "assignment_id": clean_assignment["id"],
            "lesson_results": lessons,
            "diagnostics": diagnostics,
            "journal_count": len(_list(profile.get("journal"))),
        }
        _check_summary(result)
        packages._encode(result)
        return result
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        if isinstance(exc, SubmissionValidationError):
            raise
        # Existing validators use fixed messages; never echo input values.
        message = str(exc) if isinstance(exc, packages.ClassroomPackageError) else "Dữ liệu bài nộp không hợp lệ."
        raise SubmissionValidationError(message) from None


def submit(submission) -> dict:
    """Fail closed until authenticated transport and Rules are verified.

    No network, disk write, or success receipt is produced in this milestone.
    """
    raise SubmissionNotConfiguredError(
        "Kênh nộp Firebase chưa được cấu hình; chưa có dữ liệu nào được gửi."
    )
