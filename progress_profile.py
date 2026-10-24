"""Hồ sơ tiến độ học tập, lưu cục bộ và xuất/nhập bằng JSON.

Hồ sơ nằm trong phiên Streamlit nên sẽ mất khi đóng trình duyệt. Người học chủ
động tải tệp JSON về để giữ, và nạp lại khi cần.

Phần nhập tệp coi mọi dữ liệu bên ngoài là **không đáng tin**: kiểm tra kích
thước, độ sâu, khóa, kiểu và miền giá trị trước khi nhận. Sai một điểm là từ
chối cả tệp, không cố sửa, vì "sửa hộ" dữ liệu hỏng dễ tạo ra hồ sơ sai lặng lẽ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 2

# Trọng số rubric theo yêu cầu chương trình.
RUBRIC_WEIGHTS: dict[str, float] = {
    "kien_thuc": 0.30,
    "lap_luan": 0.30,
    "rui_ro_nguon": 0.25,
    "nhat_ky": 0.15,
}

RUBRIC_LABELS = {
    "kien_thuc": "Kiến thức",
    "lap_luan": "Lập luận",
    "rui_ro_nguon": "Kỷ luật rủi ro và chất lượng nguồn",
    "nhat_ky": "Nhật ký và phản tư",
}

# ---- Giới hạn an toàn khi nhập tệp ----
MAX_IMPORT_BYTES = 256 * 1024      # 256 KB là quá đủ cho một hồ sơ
MAX_JSON_DEPTH = 8
MAX_LESSONS = 200
MAX_JOURNAL_ENTRIES = 500
MAX_ATTEMPTS_PER_LESSON = 100
MAX_DIAGNOSTIC_ATTEMPTS = 50
MAX_TEXT_LEN = 2000
MAX_KEY_LEN = 64

TOP_LEVEL_KEYS = {
    "schema_version", "pre_test", "post_test",
    "lesson_scores", "lesson_attempts", "diagnostic_attempts",
    "journal", "rubric_scores", "self_reflection_scores",
    "seen_tour",
}
TEST_KEYS = {"score", "taken_at"}
ATTEMPT_KEYS = {"score", "taken_at", "correct_qids", "correct"}
JOURNAL_KEYS = {"at", "title", "decision", "rationale", "risk", "sources"}

# Dấu hiệu dữ liệu định danh — hồ sơ học tập không chứa các trường này.
_PII_MARKERS = (
    "cccd", "cmnd", "can_cuc", "passport", "ho_chieu", "khai_sinh",
    "ngay_sinh", "dob", "birthdate", "kyc", "bank_account", "so_tai_khoan",
)


class ProfileImportError(ValueError):
    """Tệp hồ sơ không hợp lệ hoặc không an toàn."""


@dataclass
class RubricResult:
    parts: dict[str, float]
    total: float

    def as_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "Tiêu chí": RUBRIC_LABELS[key],
                "Trọng số": f"{RUBRIC_WEIGHTS[key]:.0%}",
                "Điểm thành phần": round(self.parts.get(key, 0.0), 2),
            }
            for key in RUBRIC_WEIGHTS
        ]


class DiagnosticResult(dict):
    """Mapping result with attribute access for local diagnostic quiz callers."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def empty_profile() -> dict[str, Any]:
    # rubric_scores để rỗng, không điền sẵn 0.0: "chưa chấm" và "chấm 0 điểm"
    # là hai trạng thái khác nhau, điền sẵn 0 sẽ xoá mất ranh giới đó.
    return {
        "schema_version": SCHEMA_VERSION,
        "pre_test": {"score": None, "taken_at": None},
        "post_test": {"score": None, "taken_at": None},
        "lesson_scores": {},
        "lesson_attempts": {},
        "diagnostic_attempts": {"pre_test": [], "post_test": []},
        "journal": [],
        "rubric_scores": {},
        "self_reflection_scores": {},
        "seen_tour": False,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ProfileImportError("Điểm phải là số.") from exc
    if score != score or score in (float("inf"), float("-inf")):
        raise ProfileImportError("Điểm không hợp lệ.")
    return max(0.0, min(100.0, score))


def _timestamp(value: Any = None) -> str:
    if value is None:
        return _now_iso()
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)[:64]


def _diagnostic_lessons(lessons: Any = None) -> tuple[Any, ...]:
    if lessons is not None:
        return tuple(lessons)
    # Lazy import keeps progress_profile usable as a small standalone storage
    # module and avoids a module-level dependency cycle for callers/tests.
    import curriculum

    return tuple(curriculum.all_lessons())


def diagnostic_questions(lessons: Any = None) -> list[dict[str, Any]]:
    """Return local quiz metadata derived from ``Lesson.questions``.

    The question objects stay local; only safe display metadata is returned so
    Streamlit can render a diagnostic form without an API key or network call.
    """

    rows: list[dict[str, Any]] = []
    for lesson in _diagnostic_lessons(lessons):
        for question in lesson.questions:
            rows.append({
                "lesson_id": str(lesson.lesson_id),
                "qid": str(question.qid),
                "prompt": question.prompt,
                "kind": question.kind,
                "options": tuple(question.options),
            })
    return rows


def build_diagnostic_quiz(lessons: Any = None) -> list[dict[str, Any]]:
    """Alias for callers that prefer the assessment-oriented name."""

    return diagnostic_questions(lessons)


def _response_for(responses: Any, lesson_id: str, qid: str) -> Any:
    if not isinstance(responses, dict):
        return None
    if qid in responses:
        return responses[qid]
    scoped = responses.get(lesson_id)
    if isinstance(scoped, dict):
        return scoped.get(qid)
    return responses.get((lesson_id, qid))


def grade_diagnostic(
    lessons: Any = None,
    responses: dict[str, Any] | None = None,
) -> DiagnosticResult:
    """Grade a complete local diagnostic quiz from ``Lesson.questions``.

    ``grade_diagnostic(responses)`` uses the default THPT curriculum;
    ``grade_diagnostic(lessons, responses)`` supports a selected track.
    """

    if responses is None and isinstance(lessons, dict):
        responses, lessons = lessons, None
    records = []
    lesson_scores: dict[str, float] = {}
    for lesson in _diagnostic_lessons(lessons):
        correct_for_lesson: dict[str, bool] = {}
        for question in lesson.questions:
            ok = bool(question.check(_response_for(responses, lesson.lesson_id, question.qid)))
            correct_for_lesson[str(question.qid)] = ok
            records.append((str(lesson.lesson_id), str(question.qid), ok))
        if lesson.questions:
            lesson_scores[str(lesson.lesson_id)] = round(
                sum(correct_for_lesson.values()) / len(lesson.questions) * 100,
                2,
            )
    correct = {qid: ok for _, qid, ok in records}
    correct_qids = [qid for _, qid, ok in records if ok]
    total = len(records)
    return DiagnosticResult(
        score=round(len(correct_qids) / total * 100, 2) if total else 0.0,
        correct_count=len(correct_qids),
        total=total,
        correct=correct,
        correct_qids=correct_qids,
        lesson_scores=lesson_scores,
    )


# ---------------------------------------------------------------------------
# Ghi tiến độ
# ---------------------------------------------------------------------------

def record_test(profile: dict[str, Any], which: str, score: Any) -> dict[str, Any]:
    """Legacy score setter retained only for old imported profiles/callers.

    New UI code records answers through :func:`record_diagnostic` instead.
    """

    if which not in ("pre_test", "post_test"):
        raise ValueError("which phải là 'pre_test' hoặc 'post_test'.")
    profile[which] = {"score": _clamp_score(score), "taken_at": _now_iso()}
    return profile


def record_diagnostic(
    profile: dict[str, Any],
    responses: dict[str, Any] | DiagnosticResult,
    *,
    which: str = "pre_test",
    lessons: Any = None,
    at: Any = None,
) -> dict[str, Any]:
    """Persist one local pre/post diagnostic attempt.

    The legacy ``pre_test``/``post_test`` summary is updated so older exports
    and rubric calculations continue to work; answers never become rubric data.
    """

    if which in ("pre", "pretest"):
        which = "pre_test"
    elif which in ("post", "posttest"):
        which = "post_test"
    if which not in ("pre_test", "post_test"):
        raise ValueError("which phải là 'pre_test' hoặc 'post_test'.")
    result = (
        responses
        if isinstance(responses, DiagnosticResult)
        else grade_diagnostic(lessons, responses)
    )
    taken_at = _timestamp(at)
    attempts = profile.setdefault("diagnostic_attempts", {"pre_test": [], "post_test": []})
    if not isinstance(attempts, dict):
        raise ValueError("diagnostic_attempts phải là đối tượng.")
    bucket = attempts.setdefault(which, [])
    if len(bucket) >= MAX_DIAGNOSTIC_ATTEMPTS:
        del bucket[0]
    bucket.append({
        "score": _clamp_score(result.get("score", 0.0)),
        "taken_at": taken_at,
        "correct_qids": list(result.get("correct_qids", [])),
        "correct": dict(result.get("correct", {})),
    })
    profile[which] = {
        "score": _clamp_score(result.get("score", 0.0)),
        "taken_at": taken_at,
    }
    return profile


def diagnostic_attempts(profile: dict[str, Any], which: str = "pre_test") -> list[dict[str, Any]]:
    key = {"pre": "pre_test", "pretest": "pre_test", "post": "post_test", "posttest": "post_test"}.get(which, which)
    buckets = profile.get("diagnostic_attempts") or {}
    return list(buckets.get(key) or []) if isinstance(buckets, dict) else []


def record_lesson_attempt(
    profile: dict[str, Any],
    lesson_id: str,
    score: Any,
    correct: Any = None,
    *,
    at: Any = None,
) -> dict[str, Any]:
    """Append a lesson attempt while keeping latest ``lesson_scores`` intact."""

    key = str(lesson_id or "").strip()[:MAX_KEY_LEN]
    if not key:
        raise ValueError("lesson_id trống.")
    scores = profile.setdefault("lesson_scores", {})
    attempts_by_lesson = profile.setdefault("lesson_attempts", {})
    if len(scores) >= MAX_LESSONS and key not in scores:
        raise ValueError("Vượt quá số bài học cho phép.")
    if not isinstance(attempts_by_lesson, dict):
        raise ValueError("lesson_attempts phải là đối tượng.")
    bucket = attempts_by_lesson.setdefault(key, [])
    if len(bucket) >= MAX_ATTEMPTS_PER_LESSON:
        del bucket[0]
    if isinstance(correct, dict):
        correct_map = {str(qid)[:MAX_KEY_LEN]: bool(ok) for qid, ok in correct.items()}
    elif correct is None:
        correct_map = {}
    else:
        correct_map = {str(qid)[:MAX_KEY_LEN]: True for qid in correct}
    clean_score = _clamp_score(score)
    bucket.append({
        "score": clean_score,
        "taken_at": _timestamp(at),
        "correct_qids": [qid for qid, ok in correct_map.items() if ok],
        "correct": correct_map,
    })
    # Existing unlock code reads this map. It intentionally remains latest,
    # while ``best_lesson_score`` exposes the historical maximum separately.
    scores[key] = clean_score
    return profile


def record_lesson(profile: dict[str, Any], lesson_id: str, score: Any) -> dict[str, Any]:
    """Backward-compatible score setter; now also leaves an attempt trail."""

    return record_lesson_attempt(profile, lesson_id, score)


def lesson_attempts(profile: dict[str, Any], lesson_id: str) -> list[dict[str, Any]]:
    key = str(lesson_id or "").strip()[:MAX_KEY_LEN]
    attempts = profile.get("lesson_attempts") or {}
    if not isinstance(attempts, dict):
        return []
    return list(attempts.get(key) or [])


def latest_lesson_attempt(profile: dict[str, Any], lesson_id: str) -> dict[str, Any] | None:
    attempts = lesson_attempts(profile, lesson_id)
    return attempts[-1] if attempts else None


def best_lesson_score(profile: dict[str, Any], lesson_id: str) -> float | None:
    attempts = lesson_attempts(profile, lesson_id)
    if attempts:
        return max(_clamp_score(item.get("score", 0.0)) for item in attempts)
    legacy = (profile.get("lesson_scores") or {}).get(str(lesson_id))
    return None if legacy is None else _clamp_score(legacy)


def add_journal_entry(
    profile: dict[str, Any],
    *,
    title: str,
    decision: str,
    rationale: str = "",
    risk: str = "",
    sources: str = "",
) -> dict[str, Any]:
    journal = profile.setdefault("journal", [])
    if len(journal) >= MAX_JOURNAL_ENTRIES:
        raise ValueError("Nhật ký đã đầy.")
    journal.append({
        "at": _now_iso(),
        "title": str(title)[:MAX_TEXT_LEN],
        "decision": str(decision)[:MAX_TEXT_LEN],
        "rationale": str(rationale)[:MAX_TEXT_LEN],
        "risk": str(risk)[:MAX_TEXT_LEN],
        "sources": str(sources)[:MAX_TEXT_LEN],
    })
    return profile


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------

def compute_rubric(profile: dict[str, Any]) -> RubricResult:
    """Điểm tổng theo trọng số 30/30/25/15.

    Điểm kiến thức lấy từ bài học và bài kiểm tra sau; ba tiêu chí còn lại do
    người chấm nhập vào ``rubric_scores`` vì chúng đánh giá lập luận và kỷ luật,
    không suy ra được từ điểm trắc nghiệm.
    """

    lessons = profile.get("lesson_scores") or {}
    lesson_avg = (
        sum(float(v) for v in lessons.values()) / len(lessons) if lessons else 0.0
    )
    post = (profile.get("post_test") or {}).get("score")
    knowledge = (lesson_avg + float(post)) / 2 if post is not None else lesson_avg

    manual = profile.get("rubric_scores") or {}
    journal_count = len(profile.get("journal") or [])
    # Nhật ký: 5 mục trở lên coi là đủ, quy về thang 100.
    journal_auto = min(100.0, journal_count / 5 * 100.0)

    def _manual(key: str) -> float | None:
        """Điểm người chấm nhập, hoặc None nếu chưa chấm.

        Dùng `is None` chứ không dùng `or`: điểm 0 là một đánh giá hợp lệ,
        `or` sẽ coi 0 là "chưa chấm" và lặng lẽ thay bằng giá trị khác.
        """

        value = manual.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    journal_manual = _manual("nhat_ky")

    raw = {
        "kien_thuc": knowledge,
        "lap_luan": _manual("lap_luan") or 0.0,
        "rui_ro_nguon": _manual("rui_ro_nguon") or 0.0,
        "nhat_ky": journal_auto if journal_manual is None else journal_manual,
    }

    parts = {k: max(0.0, min(100.0, v)) * RUBRIC_WEIGHTS[k] for k, v in raw.items()}
    return RubricResult(parts=parts, total=round(sum(parts.values()), 2))


# ---------------------------------------------------------------------------
# Xuất / nhập JSON
# ---------------------------------------------------------------------------

def export_json(profile: dict[str, Any]) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pre_test": profile.get("pre_test") or {"score": None, "taken_at": None},
        "post_test": profile.get("post_test") or {"score": None, "taken_at": None},
        "lesson_scores": profile.get("lesson_scores") or {},
        "lesson_attempts": profile.get("lesson_attempts") or {},
        "diagnostic_attempts": profile.get("diagnostic_attempts") or {"pre_test": [], "post_test": []},
        "journal": profile.get("journal") or [],
        "rubric_scores": profile.get("rubric_scores") or {},
        "self_reflection_scores": profile.get("self_reflection_scores") or {},
        "seen_tour": bool(profile.get("seen_tour", False)),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _depth(obj: Any, level: int = 1) -> int:
    if level > MAX_JSON_DEPTH:
        return level
    if isinstance(obj, dict):
        return max((_depth(v, level + 1) for v in obj.values()), default=level)
    if isinstance(obj, list):
        return max((_depth(v, level + 1) for v in obj), default=level)
    return level


def _reject_pii(mapping: dict[str, Any]) -> None:
    for key in mapping:
        name = str(key).strip().lower()
        if any(marker in name for marker in _PII_MARKERS):
            raise ProfileImportError(
                "Tệp chứa trường dữ liệu định danh; hồ sơ học tập không lưu loại dữ liệu này."
            )


def import_json(text: str | bytes) -> dict[str, Any]:
    """Đọc hồ sơ từ JSON, từ chối mọi tệp không đạt kiểm tra an toàn."""

    if isinstance(text, bytes):
        raw = text
    else:
        raw = str(text or "").encode("utf-8")

    if not raw.strip():
        raise ProfileImportError("Tệp rỗng.")
    if len(raw) > MAX_IMPORT_BYTES:
        raise ProfileImportError(
            f"Tệp quá lớn (giới hạn {MAX_IMPORT_BYTES // 1024} KB)."
        )

    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProfileImportError("Tệp không phải JSON hợp lệ.") from exc
    except RecursionError as exc:
        # json.loads đệ quy theo độ sâu của tệp, nên tệp lồng hàng chục nghìn
        # cấp làm tràn ngăn xếp *trước khi* _depth() kịp chạy. Không bọc thì
        # RecursionError thoát ra ngoài và làm sập cả trang.
        raise ProfileImportError("Cấu trúc JSON lồng quá sâu.") from exc

    if not isinstance(data, dict):
        raise ProfileImportError("Hồ sơ phải là một đối tượng JSON.")
    if _depth(data) > MAX_JSON_DEPTH:
        raise ProfileImportError("Cấu trúc JSON lồng quá sâu.")

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        raise ProfileImportError(
            "Tệp chứa khóa không hợp lệ: " + ", ".join(sorted(str(k) for k in unknown))
        )
    _reject_pii(data)

    version = data.get("schema_version", SCHEMA_VERSION)
    if not isinstance(version, int) or version > SCHEMA_VERSION or version < 1:
        raise ProfileImportError("Phiên bản hồ sơ không được hỗ trợ.")

    profile = empty_profile()

    for which in ("pre_test", "post_test"):
        block = data.get(which)
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ProfileImportError(f"Trường '{which}' phải là đối tượng.")
        if set(block) - TEST_KEYS:
            raise ProfileImportError(f"Trường '{which}' chứa khóa lạ.")
        score = block.get("score")
        profile[which] = {
            "score": None if score is None else _clamp_score(score),
            "taken_at": (str(block.get("taken_at"))[:64]
                         if block.get("taken_at") is not None else None),
        }

    # Dùng `is None` chứ không dùng `or {}`: một giá trị sai kiểu nhưng rỗng
    # (ví dụ danh sách rỗng) là falsy, `or {}` sẽ nuốt mất và cho qua kiểm tra kiểu.
    lessons = data.get("lesson_scores")
    if lessons is None:
        lessons = {}
    if not isinstance(lessons, dict):
        raise ProfileImportError("'lesson_scores' phải là đối tượng.")
    if len(lessons) > MAX_LESSONS:
        raise ProfileImportError("Quá nhiều bài học trong hồ sơ.")
    _reject_pii(lessons)
    profile["lesson_scores"] = {
        str(k)[:MAX_KEY_LEN]: _clamp_score(v) for k, v in lessons.items()
    }

    attempts = data.get("lesson_attempts")
    if attempts is None:
        attempts = {}
    if not isinstance(attempts, dict):
        raise ProfileImportError("'lesson_attempts' phải là đối tượng.")
    if len(attempts) > MAX_LESSONS:
        raise ProfileImportError("Quá nhiều bài học trong lịch sử.")
    _reject_pii(attempts)
    clean_attempts: dict[str, list[dict[str, Any]]] = {}
    for lesson_id, bucket in attempts.items():
        if not isinstance(bucket, list):
            raise ProfileImportError("Lịch sử mỗi bài học phải là danh sách.")
        if len(bucket) > MAX_ATTEMPTS_PER_LESSON:
            raise ProfileImportError("Quá nhiều lần làm một bài học.")
        clean_bucket = []
        for item in bucket:
            if not isinstance(item, dict) or set(item) - ATTEMPT_KEYS:
                raise ProfileImportError("Lần làm bài chứa khóa không hợp lệ.")
            correct = item.get("correct") or {}
            if not isinstance(correct, dict):
                raise ProfileImportError("Trường 'correct' phải là đối tượng.")
            if any(not isinstance(value, bool) for value in correct.values()):
                raise ProfileImportError("Trường 'correct' phải chứa boolean.")
            correct_qids = item.get("correct_qids") or []
            if not isinstance(correct_qids, list) or any(not isinstance(qid, str) for qid in correct_qids):
                raise ProfileImportError("Trường 'correct_qids' phải là danh sách chuỗi.")
            clean_bucket.append({
                "score": _clamp_score(item.get("score")),
                "taken_at": _timestamp(item.get("taken_at")),
                "correct_qids": [str(qid)[:MAX_KEY_LEN] for qid in correct_qids],
                "correct": {str(qid)[:MAX_KEY_LEN]: value for qid, value in correct.items()},
            })
        clean_attempts[str(lesson_id)[:MAX_KEY_LEN]] = clean_bucket
    profile["lesson_attempts"] = clean_attempts

    diagnostic = data.get("diagnostic_attempts")
    if diagnostic is None:
        diagnostic = {"pre_test": [], "post_test": []}
    if not isinstance(diagnostic, dict) or set(diagnostic) - {"pre_test", "post_test"}:
        raise ProfileImportError("'diagnostic_attempts' chứa khóa không hợp lệ.")
    clean_diagnostic: dict[str, list[dict[str, Any]]] = {"pre_test": [], "post_test": []}
    for which in clean_diagnostic:
        bucket = diagnostic.get(which) or []
        if not isinstance(bucket, list) or len(bucket) > MAX_DIAGNOSTIC_ATTEMPTS:
            raise ProfileImportError("Lịch sử chẩn đoán không hợp lệ.")
        for item in bucket:
            if not isinstance(item, dict) or set(item) - ATTEMPT_KEYS:
                raise ProfileImportError("Lần chẩn đoán chứa khóa không hợp lệ.")
            correct = item.get("correct") or {}
            correct_qids = item.get("correct_qids") or []
            if not isinstance(correct, dict) or any(not isinstance(value, bool) for value in correct.values()):
                raise ProfileImportError("Trường 'correct' của chẩn đoán không hợp lệ.")
            if not isinstance(correct_qids, list) or any(not isinstance(qid, str) for qid in correct_qids):
                raise ProfileImportError("Trường 'correct_qids' của chẩn đoán không hợp lệ.")
            clean_diagnostic[which].append({
                "score": _clamp_score(item.get("score")),
                "taken_at": _timestamp(item.get("taken_at")),
                "correct_qids": [str(qid)[:MAX_KEY_LEN] for qid in correct_qids],
                "correct": {str(qid)[:MAX_KEY_LEN]: value for qid, value in correct.items()},
            })
    profile["diagnostic_attempts"] = clean_diagnostic

    journal = data.get("journal")
    if journal is None:
        journal = []
    if not isinstance(journal, list):
        raise ProfileImportError("'journal' phải là danh sách.")
    if len(journal) > MAX_JOURNAL_ENTRIES:
        raise ProfileImportError("Nhật ký vượt quá số mục cho phép.")
    clean_journal = []
    for item in journal:
        if not isinstance(item, dict):
            raise ProfileImportError("Mỗi mục nhật ký phải là đối tượng.")
        if set(item) - JOURNAL_KEYS:
            raise ProfileImportError("Mục nhật ký chứa khóa lạ.")
        _reject_pii(item)
        clean_journal.append({
            key: str(item.get(key, ""))[:MAX_TEXT_LEN] for key in JOURNAL_KEYS
        })
    profile["journal"] = clean_journal

    rubric = data.get("rubric_scores")
    if rubric is None:
        rubric = {}
    if not isinstance(rubric, dict):
        raise ProfileImportError("'rubric_scores' phải là đối tượng.")
    if set(rubric) - set(RUBRIC_WEIGHTS):
        raise ProfileImportError("'rubric_scores' chứa tiêu chí không hợp lệ.")
    # Chỉ giữ tiêu chí thực sự có trong tệp, để tiêu chí chưa chấm vẫn là chưa chấm.
    clean_rubric_scores = {
        key: _clamp_score(value)
        for key, value in rubric.items()
        if value is not None
    }
    # Version 1 exposed editable rubric fields to learners. Preserve those
    # values as reflection data instead of silently treating them as teacher
    # marks after the schema split.
    profile["rubric_scores"] = {} if version < 2 else clean_rubric_scores

    reflection = data.get("self_reflection_scores")
    if reflection is None:
        reflection = {}
    if not isinstance(reflection, dict):
        raise ProfileImportError("'self_reflection_scores' phải là đối tượng.")
    if set(reflection) - set(RUBRIC_WEIGHTS):
        raise ProfileImportError("'self_reflection_scores' chứa tiêu chí không hợp lệ.")
    profile["self_reflection_scores"] = {
        key: _clamp_score(value)
        for key, value in reflection.items()
        if value is not None
    }
    if version < 2:
        profile["self_reflection_scores"].update(clean_rubric_scores)

    profile["seen_tour"] = data.get("seen_tour") is True
    return profile
