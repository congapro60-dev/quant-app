"""Build minimal summaries; transport requires an explicit authenticated client.

Local scores are self-reported, not server-verified assessments.
"""

from __future__ import annotations

from collections.abc import Mapping

import classroom_packages as packages

MAX_ONLINE_LESSONS = packages.MAX_LESSONS

class SubmissionValidationError(packages.ClassroomPackageError):
    """Input cannot safely be converted into a course summary."""


class SubmissionNotConfiguredError(RuntimeError):
    """No authenticated submission transport was supplied."""


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


def validate_submission(submission) -> None:
    """Recheck the outbound trust boundary, including edited client payloads."""
    try:
        packages._encode(submission)
        keys = {"schema_version", "class_code", "student_code", "assignment_id",
                "lesson_results", "diagnostics", "journal_count"}
        if not isinstance(submission, dict) or set(submission) != keys or type(submission["schema_version"]) is not int or submission["schema_version"] != 1:
            raise SubmissionValidationError("Cấu trúc bài nộp không hợp lệ.")
        packages._id(submission["class_code"], "class_code")
        packages._student_code(submission["student_code"])
        packages._id(submission["assignment_id"], "assignment_id")
        lessons = _list(submission["lesson_results"])
        if not 1 <= len(lessons) <= MAX_ONLINE_LESSONS:
            raise SubmissionValidationError("Số mô-đun bài nộp vượt giới hạn gói lớp học.")
        seen = set()
        for row in lessons:
            if not isinstance(row, dict) or set(row) != {"lesson_id", "latest_score", "best_score", "attempt_count"}:
                raise SubmissionValidationError("Dữ liệu mô-đun không hợp lệ.")
            lesson_id = packages._id(row["lesson_id"], "lesson_id")
            if lesson_id in seen:
                raise SubmissionValidationError("Không nộp lặp mô-đun.")
            seen.add(lesson_id)
            _score(row["latest_score"])
            _score(row["best_score"])
            packages._attempts(row["attempt_count"])
        diagnostics = submission["diagnostics"]
        if not isinstance(diagnostics, dict) or set(diagnostics) != {"pre_test", "post_test"}:
            raise SubmissionValidationError("Dữ liệu chẩn đoán không hợp lệ.")
        for block in diagnostics.values():
            if not isinstance(block, dict) or set(block) != {"score", "attempt_count"}:
                raise SubmissionValidationError("Dữ liệu chẩn đoán không hợp lệ.")
            _score(block["score"])
            packages._attempts(block["attempt_count"])
        count = submission["journal_count"]
        if type(count) is not int or not 0 <= count <= 500:
            raise SubmissionValidationError("Số mục nhật ký không hợp lệ.")
        _check_summary(submission)
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, SubmissionValidationError):
            raise
        raise SubmissionValidationError("Dữ liệu bài nộp không hợp lệ.") from None


def submit(submission, *, client=None, session=None) -> dict:
    """Send only through an explicitly configured, authenticated client."""
    if client is None or session is None:
        raise SubmissionNotConfiguredError(
            "Kênh nộp Firebase chưa được cấu hình; chưa có dữ liệu nào được gửi."
        )
    validate_submission(submission)
    return client.submit(session, submission)
