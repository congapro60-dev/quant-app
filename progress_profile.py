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

SCHEMA_VERSION = 1

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
MAX_TEXT_LEN = 2000
MAX_KEY_LEN = 64

TOP_LEVEL_KEYS = {
    "schema_version", "pre_test", "post_test",
    "lesson_scores", "journal", "rubric_scores",
}
TEST_KEYS = {"score", "taken_at"}
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


def empty_profile() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pre_test": {"score": None, "taken_at": None},
        "post_test": {"score": None, "taken_at": None},
        "lesson_scores": {},
        "journal": [],
        "rubric_scores": {key: 0.0 for key in RUBRIC_WEIGHTS},
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


# ---------------------------------------------------------------------------
# Ghi tiến độ
# ---------------------------------------------------------------------------

def record_test(profile: dict[str, Any], which: str, score: Any) -> dict[str, Any]:
    if which not in ("pre_test", "post_test"):
        raise ValueError("which phải là 'pre_test' hoặc 'post_test'.")
    profile[which] = {"score": _clamp_score(score), "taken_at": _now_iso()}
    return profile


def record_lesson(profile: dict[str, Any], lesson_id: str, score: Any) -> dict[str, Any]:
    key = str(lesson_id or "").strip()[:MAX_KEY_LEN]
    if not key:
        raise ValueError("lesson_id trống.")
    scores = profile.setdefault("lesson_scores", {})
    if len(scores) >= MAX_LESSONS and key not in scores:
        raise ValueError("Vượt quá số bài học cho phép.")
    scores[key] = _clamp_score(score)
    return profile


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

    raw = {
        "kien_thuc": knowledge,
        "lap_luan": float(manual.get("lap_luan", 0.0) or 0.0),
        "rui_ro_nguon": float(manual.get("rui_ro_nguon", 0.0) or 0.0),
        "nhat_ky": float(manual.get("nhat_ky", 0.0) or 0.0) or journal_auto,
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
        "journal": profile.get("journal") or [],
        "rubric_scores": profile.get("rubric_scores") or {},
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
    profile["rubric_scores"] = {
        key: _clamp_score(rubric.get(key, 0.0)) for key in RUBRIC_WEIGHTS
    }

    return profile
