"""Portable teacher/student classroom packages.

Packages are deliberately small, local-first JSON documents.  The strict
allowlists keep classroom handoff separate from identity, credentials, and
private finance data.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = 1
MAX_IMPORT_BYTES = 256 * 1024
MAX_JSON_DEPTH = 8
MAX_LESSONS = 200
MAX_ATTEMPTS_PER_LESSON = 100
MAX_ID_LEN = 64
MAX_TITLE_LEN = 200
MAX_INSTRUCTIONS_LEN = 8_000
MAX_TRACK_LEN = 32
MAX_DUE_LABEL_LEN = 120
MAX_STUDENT_CODE_LEN = 32
MAX_REFLECTION_LEN = 2_000

ASSIGNMENT_KEYS = {
    "version", "id", "title", "instructions", "lesson_ids",
    "learner_track", "due_label",
}
RESULT_KEYS = {
    "version", "assignment_id", "student_code", "lesson_attempts",
    "self_reflection",
}
ATTEMPT_KEYS = {"lesson_id", "attempts", "progress"}

# Keep marker checks close to progress_profile.py so both import boundaries have
# the same privacy posture.
_PII_MARKERS = (
    "cccd", "cmnd", "can_cuoc", "passport", "ho_chieu", "khai_sinh",
    "ngay_sinh", "dob", "birthdate", "kyc", "bank_account", "so_tai_khoan",
    "ho_ten", "full_name", "email", "phone", "dien_thoai", "so_dien_thoai",
    "address", "dia_chi", "school_id", "student_name", "teacher_name",
)
_SECRET_MARKERS = (
    "api_key", "apikey", "access_token", "refresh_token", "bearer",
    "secret", "credential", "password", "private_key",
)
_PRIVATE_FINANCE_MARKERS = (
    "holding", "holdings", "portfolio", "danh_muc", "wallet", "vi_tien",
    "bank", "account", "so_du", "balance", "cash", "ticker", "symbol",
    "price", "gia", "trade", "order", "transaction", "giao_dich",
    "investment", "dau_tu",
)
_EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)")
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{9,16}(?!\d)")
_API_VALUE_RE = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|bearer\s+[A-Za-z0-9._-]{16,})")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")


class ClassroomPackageError(ValueError):
    """Package is malformed, oversized, or contains disallowed data."""


PackageError = ClassroomPackageError


def _depth(value: Any, level: int = 1) -> int:
    if level > MAX_JSON_DEPTH:
        return level
    if isinstance(value, dict):
        return max((_depth(item, level + 1) for item in value.values()), default=level)
    if isinstance(value, list):
        return max((_depth(item, level + 1) for item in value), default=level)
    return level


def _normalised_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _reject_sensitive_key(mapping: Mapping[Any, Any]) -> None:
    for key in mapping:
        name = _normalised_key(key)
        if any(marker in name for marker in _PII_MARKERS):
            raise ClassroomPackageError("Gói chứa trường dữ liệu định danh; hãy dùng mã ẩn danh cục bộ.")
        if any(marker in name for marker in _SECRET_MARKERS):
            raise ClassroomPackageError("Gói không được chứa khóa API, token hoặc thông tin xác thực.")
        if any(marker in name for marker in _PRIVATE_FINANCE_MARKERS):
            raise ClassroomPackageError("Gói lớp học không được chứa dữ liệu tài chính riêng.")


def _scan_text(value: str) -> None:
    if _EMAIL_RE.search(value) or _PHONE_RE.search(value) or _LONG_DIGITS_RE.search(value):
        raise ClassroomPackageError("Gói chứa dữ liệu định danh; hãy xóa email, số điện thoại hoặc mã định danh.")
    if _API_VALUE_RE.search(value):
        raise ClassroomPackageError("Gói không được chứa khóa API, token hoặc thông tin xác thực.")


def _text(value: Any, field: str, limit: int, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ClassroomPackageError(f"Trường '{field}' phải là chuỗi.")
    if not allow_empty and not value.strip():
        raise ClassroomPackageError(f"Trường '{field}' không được để trống.")
    if len(value) > limit:
        raise ClassroomPackageError(f"Trường '{field}' quá dài.")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ClassroomPackageError(f"Trường '{field}' chứa ký tự điều khiển.")
    _scan_text(value)
    return value


def _version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != SCHEMA_VERSION:
        raise ClassroomPackageError("Phiên bản gói không được hỗ trợ.")
    return value


def _id(value: Any, field: str = "id") -> str:
    text = _text(value, field, MAX_ID_LEN, allow_empty=False)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", text):
        raise ClassroomPackageError(f"Trường '{field}' chỉ được chứa chữ, số, '-' hoặc '_'.")
    return text


def _lesson_ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ClassroomPackageError("'lesson_ids' phải là danh sách.")
    if not value or len(value) > MAX_LESSONS:
        raise ClassroomPackageError("Danh sách bài học phải có từ 1 đến 200 bài.")
    result = []
    seen: set[str] = set()
    for lesson_id in value:
        clean = _id(lesson_id, "lesson_id")
        if clean in seen:
            raise ClassroomPackageError("Danh sách bài học không được lặp.")
        seen.add(clean)
        result.append(clean)
    return result


def _validate_assignment(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ClassroomPackageError("Gói giao bài phải là một đối tượng JSON.")
    _reject_sensitive_key(payload)
    if set(payload) != ASSIGNMENT_KEYS:
        unknown = set(payload) - ASSIGNMENT_KEYS
        missing = ASSIGNMENT_KEYS - set(payload)
        detail = []
        if unknown:
            detail.append("khóa lạ: " + ", ".join(sorted(map(str, unknown))))
        if missing:
            detail.append("thiếu khóa: " + ", ".join(sorted(missing)))
        raise ClassroomPackageError("Gói giao bài không đúng cấu trúc (" + "; ".join(detail) + ").")
    return {
        "version": _version(payload["version"]),
        "id": _id(payload["id"]),
        "title": _text(payload["title"], "title", MAX_TITLE_LEN, allow_empty=False),
        "instructions": _text(payload["instructions"], "instructions", MAX_INSTRUCTIONS_LEN, allow_empty=False),
        "lesson_ids": _lesson_ids(payload["lesson_ids"]),
        "learner_track": _text(payload["learner_track"], "learner_track", MAX_TRACK_LEN, allow_empty=False),
        "due_label": _text(payload["due_label"], "due_label", MAX_DUE_LABEL_LEN),
    }


def _progress(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClassroomPackageError("Tiến độ phải là số từ 0 đến 100.")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ClassroomPackageError("Tiến độ phải là số hữu hạn từ 0 đến 100.")
    return int(number) if number.is_integer() else number


def _attempts(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClassroomPackageError("Số lần làm phải là số nguyên từ 0 đến 100.")
    if not 0 <= value <= MAX_ATTEMPTS_PER_LESSON:
        raise ClassroomPackageError("Số lần làm phải là số nguyên từ 0 đến 100.")
    return value


def _student_code(value: Any) -> str:
    text = _text(value, "student_code", MAX_STUDENT_CODE_LEN, allow_empty=False)
    if not _CODE_RE.fullmatch(text) or not any(char.isdigit() for char in text):
        raise ClassroomPackageError("student_code phải là mã ẩn danh cục bộ, ví dụ HS-7F3K.")
    return text


def _validate_attempts(value: Any, allowed_lessons: set[str] | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise ClassroomPackageError("'lesson_attempts' phải là danh sách.")
    if len(value) > MAX_LESSONS:
        raise ClassroomPackageError("Quá nhiều bài học trong kết quả.")
    result = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ClassroomPackageError("Mỗi mục lesson_attempts phải là một đối tượng.")
        _reject_sensitive_key(item)
        if set(item) != ATTEMPT_KEYS:
            raise ClassroomPackageError("Mỗi mục lesson_attempts phải có đúng lesson_id, attempts, progress.")
        lesson_id = _id(item["lesson_id"], "lesson_id")
        if lesson_id in seen:
            raise ClassroomPackageError("lesson_attempts không được lặp bài học.")
        if allowed_lessons is not None and lesson_id not in allowed_lessons:
            raise ClassroomPackageError("Kết quả chứa bài học không thuộc gói giao bài.")
        seen.add(lesson_id)
        result.append({
            "lesson_id": lesson_id,
            "attempts": _attempts(item["attempts"]),
            "progress": _progress(item["progress"]),
        })
    return result


def _validate_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ClassroomPackageError("Gói kết quả phải là một đối tượng JSON.")
    _reject_sensitive_key(payload)
    if set(payload) != RESULT_KEYS:
        unknown = set(payload) - RESULT_KEYS
        missing = RESULT_KEYS - set(payload)
        detail = []
        if unknown:
            detail.append("khóa lạ: " + ", ".join(sorted(map(str, unknown))))
        if missing:
            detail.append("thiếu khóa: " + ", ".join(sorted(missing)))
        raise ClassroomPackageError("Gói kết quả không đúng cấu trúc (" + "; ".join(detail) + ").")
    reflection = payload["self_reflection"]
    if reflection is not None:
        reflection = _text(reflection, "self_reflection", MAX_REFLECTION_LEN)
    return {
        "version": _version(payload["version"]),
        "assignment_id": _id(payload["assignment_id"], "assignment_id"),
        "student_code": _student_code(payload["student_code"]),
        "lesson_attempts": _validate_attempts(payload["lesson_attempts"]),
        "self_reflection": reflection,
    }


def _decode(payload: bytes | str) -> Any:
    raw = payload if isinstance(payload, bytes) else str(payload or "").encode("utf-8")
    if not raw.strip():
        raise ClassroomPackageError("Tệp gói rỗng.")
    if len(raw) > MAX_IMPORT_BYTES:
        raise ClassroomPackageError(f"Tệp gói quá lớn (giới hạn {MAX_IMPORT_BYTES // 1024} KB).")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ClassroomPackageError("Tệp gói không phải JSON hợp lệ.") from exc
    except RecursionError as exc:
        raise ClassroomPackageError("Cấu trúc JSON lồng quá sâu.") from exc
    if _depth(data) > MAX_JSON_DEPTH:
        raise ClassroomPackageError("Cấu trúc JSON lồng quá sâu.")
    return data


def _encode(payload: Mapping[str, Any]) -> bytes:
    try:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ClassroomPackageError("Không thể mã hóa gói JSON an toàn.") from exc
    if len(raw) > MAX_IMPORT_BYTES:
        raise ClassroomPackageError(f"Gói quá lớn (giới hạn {MAX_IMPORT_BYTES // 1024} KB).")
    return raw


def make_assignment(
    *,
    assignment_id: str,
    title: str,
    instructions: str,
    lesson_ids: Sequence[str],
    learner_track: str = "thpt",
    due_label: str = "",
) -> dict[str, Any]:
    """Create a validated teacher-to-student assignment package."""

    return _validate_assignment({
        "version": SCHEMA_VERSION,
        "id": assignment_id,
        "title": title,
        "instructions": instructions,
        "lesson_ids": list(lesson_ids) if not isinstance(lesson_ids, list) else lesson_ids,
        "learner_track": learner_track,
        "due_label": due_label,
    })


def export_assignment(payload: Mapping[str, Any]) -> bytes:
    return _encode(_validate_assignment(payload))


def import_assignment(payload: bytes | str) -> dict[str, Any]:
    return _validate_assignment(_decode(payload))


def make_result(
    *,
    assignment: Mapping[str, Any],
    student_code: str,
    lesson_attempts: Sequence[Mapping[str, Any]],
    self_reflection: str | None = None,
) -> dict[str, Any]:
    """Create a validated student-to-teacher result package."""

    clean_assignment = _validate_assignment(assignment)
    return _validate_result({
        "version": SCHEMA_VERSION,
        "assignment_id": clean_assignment["id"],
        "student_code": student_code,
        "lesson_attempts": list(lesson_attempts) if not isinstance(lesson_attempts, list) else lesson_attempts,
        "self_reflection": self_reflection,
    }) | {
        "lesson_attempts": _validate_attempts(
            lesson_attempts, allowed_lessons=set(clean_assignment["lesson_ids"])
        )
    }


def export_result(payload: Mapping[str, Any]) -> bytes:
    return _encode(_validate_result(payload))


def import_result(payload: bytes | str) -> dict[str, Any]:
    return _validate_result(_decode(payload))


# Descriptive aliases keep call sites readable without adding another schema.
assignment_to_json = export_assignment
assignment_from_json = import_assignment
result_to_json = export_result
result_from_json = import_result

