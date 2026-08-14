"""Nhật ký thay đổi chính sách.

ROADMAP đặt điều kiện nghiệm thu: *"mọi thay đổi chính sách có nhật ký"*. Nhật
ký này ghi lại việc người học đổi nhóm tuổi, tích/bỏ tích các xác nhận, hay nới
hạn mức rủi ro — kèm thời điểm và giá trị cũ/mới.

Hai quy tắc chi phối thiết kế:

1. **Chỉ ghi khi giá trị thật sự đổi.** Streamlit chạy lại toàn bộ trang sau mỗi
   thao tác, nên ghi vô điều kiện sẽ sinh hàng nghìn mục trùng và làm nhật ký
   mất tác dụng.
2. **Không ghi dữ liệu định danh.** Nhật ký có thể được tải về và gửi cho giáo
   viên hay người đại diện, nên nó không được mang theo giấy tờ tùy thân.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

AUDIT_KEY = "policy_audit"

MAX_EVENTS = 500
MAX_VALUE_LEN = 120
MAX_NOTE_LEN = 240

# Dấu hiệu dữ liệu định danh — không bao giờ đi vào nhật ký.
_PII_MARKERS = (
    "cccd", "cmnd", "can_cuc", "passport", "ho_chieu", "khai_sinh",
    "ngay_sinh", "dob", "birthdate", "kyc", "bank_account", "so_tai_khoan",
)

# Nhãn tiếng Việt cho các trường chính sách.
FIELD_LABELS = {
    "age_band": "Nhóm tuổi",
    "guardian_confirmed": "Xác nhận của người đại diện",
    "broker_policy_confirmed": "Xác nhận chính sách công ty chứng khoán",
    "paper_first_completed": "Hoàn thành giai đoạn mô phỏng",
    "risk_check_passed": "Đạt bài kiểm tra rủi ro",
    "capital_cap_vnd": "Hạn mức vốn (VND)",
    "max_position_fraction": "Tỷ trọng tối đa mỗi mã",
    "max_sector_fraction": "Tỷ trọng tối đa mỗi ngành",
    "max_daily_loss_fraction": "Mức lỗ tối đa trong ngày",
    "max_monthly_loss_fraction": "Mức lỗ tối đa trong tháng",
    "cooldown_minutes": "Thời gian chờ trước lệnh (phút)",
}


class PolicyAuditError(ValueError):
    """Dữ liệu không được phép đưa vào nhật ký."""


@dataclass(frozen=True)
class PolicyEvent:
    at: str
    field: str
    old_value: str
    new_value: str
    note: str = ""

    @property
    def field_label(self) -> str:
        return FIELD_LABELS.get(self.field, self.field)

    def as_row(self) -> dict[str, str]:
        return {
            "Thời điểm": self.at,
            "Mục chính sách": self.field_label,
            "Giá trị cũ": self.old_value,
            "Giá trị mới": self.new_value,
            "Ghi chú": self.note,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _is_pii(name: str) -> bool:
    low = str(name).strip().lower()
    return any(marker in low for marker in _PII_MARKERS)


def _fmt(value: Any) -> str:
    """Chuẩn hoá giá trị về chuỗi ngắn, ổn định để so sánh và hiển thị."""

    if value is None:
        return "(chưa đặt)"
    if isinstance(value, bool):
        return "Có" if value else "Không"
    if isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value)
    return text.strip()[:MAX_VALUE_LEN]


def events(session: MutableMapping[str, Any] | None) -> list[PolicyEvent]:
    if session is None:
        return []
    raw = session.get(AUDIT_KEY)
    return list(raw) if isinstance(raw, list) else []


def record_change(
    session: MutableMapping[str, Any],
    field: str,
    old_value: Any,
    new_value: Any,
    note: str = "",
) -> PolicyEvent | None:
    """Ghi một thay đổi. Trả về None nếu giá trị không đổi.

    Không đổi thì không ghi — nếu không, mỗi lần Streamlit dựng lại trang sẽ
    thêm một mục và nhật ký thành vô dụng.
    """

    name = str(field or "").strip()
    if not name:
        raise PolicyAuditError("Thiếu tên mục chính sách.")
    if _is_pii(name):
        raise PolicyAuditError(
            "Nhật ký chính sách không nhận dữ liệu định danh."
        )

    before, after = _fmt(old_value), _fmt(new_value)
    if before == after:
        return None

    event = PolicyEvent(
        at=_now_iso(),
        field=name,
        old_value=before,
        new_value=after,
        note=str(note or "").strip()[:MAX_NOTE_LEN],
    )

    log = events(session)
    log.append(event)
    # Giữ các mục gần nhất; nhật ký là công cụ soát lại, không phải kho lưu trữ.
    session[AUDIT_KEY] = log[-MAX_EVENTS:]
    return event


def sync_and_record(
    session: MutableMapping[str, Any],
    current: Mapping[str, Any],
    *,
    snapshot_key: str,
    note: str = "",
) -> list[PolicyEvent]:
    """So sánh giá trị hiện tại với lần trước và ghi từng thay đổi.

    ``snapshot_key`` là nơi lưu ảnh chụp lần trước, tách khỏi chính dữ liệu
    nghiệp vụ để việc so sánh không phụ thuộc thứ tự dựng giao diện.
    """

    if not isinstance(current, Mapping):
        raise PolicyAuditError("Dữ liệu chính sách phải là ánh xạ khoá/giá trị.")
    for key in current:
        if _is_pii(key):
            raise PolicyAuditError(
                "Nhật ký chính sách không nhận dữ liệu định danh."
            )

    previous = session.get(snapshot_key)
    previous = previous if isinstance(previous, Mapping) else {}

    recorded: list[PolicyEvent] = []
    for key, value in current.items():
        # Lần đầu thiết lập cũng là một thay đổi chính sách đáng ghi.
        event = record_change(session, key, previous.get(key), value, note=note)
        if event is not None:
            recorded.append(event)

    session[snapshot_key] = {k: _fmt(v) for k, v in current.items()}
    return recorded


def export_json(session: MutableMapping[str, Any] | None) -> str:
    return json.dumps(
        [asdict(e) for e in events(session)], ensure_ascii=False, indent=2
    )


def audit_rows(session: MutableMapping[str, Any] | None) -> list[dict[str, str]]:
    """Bảng hiển thị, mới nhất lên đầu."""

    return [e.as_row() for e in reversed(events(session))]
