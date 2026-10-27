"""Thuật toán thuần cho tài khoản tự đăng ký (không mạng, không Streamlit).

Tách khỏi ``firebase_classroom`` để kiểm được từng quy tắc bằng unit test:
tên đăng nhập, tên hiển thị, khối + tên lớp, mật khẩu và thứ tự sắp xếp
danh sách học sinh theo lớp. Thông điệp lỗi viết thẳng cho học sinh đọc.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping

import classroom_packages as cp

USERNAME_MIN = 4
USERNAME_MAX = 32
DISPLAY_NAME_MAX = 60
CLASS_NAME_MAX = 16
PASSWORD_MIN = 8
PASSWORD_MAX = 128
BLOCKS = ("10", "11", "12")

_CLASS_NAME_RE = re.compile(r"^[A-Z0-9]{1,16}$")


def normalize_username(value) -> str:
    """Chuẩn hoá tên đăng nhập: NFC, bỏ khoảng trắng hai đầu, chữ thường ổn định.

    Chỉ cho phép chữ (kể cả tiếng Việt), số, gạch ngang, gạch dưới, chấm.
    Chặn hoàn toàn khoảng trắng, ký tự tàng hình (U+200B) và ký tự điều khiển.
    """
    text = unicodedata.normalize("NFC", str(value or "")).strip().casefold()
    if len(text) < USERNAME_MIN or len(text) > USERNAME_MAX:
        raise cp.ClassroomPackageError(
            f"Tên đăng nhập cần {USERNAME_MIN}-{USERNAME_MAX} ký tự.")
    for char in text:
        if unicodedata.category(char).startswith("C") or char.isspace():
            raise cp.ClassroomPackageError("Tên đăng nhập không được chứa khoảng trắng hoặc ký tự ẩn.")
        if not (char.isalnum() or char in ("-", "_", ".")):
            raise cp.ClassroomPackageError("Tên đăng nhập chỉ gồm chữ, số, dấu chấm, gạch ngang hoặc gạch dưới.")
    return text


def normalize_display_name(value) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    if not text:
        raise cp.ClassroomPackageError("Cần nhập tên hiển thị.")
    if len(text) > DISPLAY_NAME_MAX:
        raise cp.ClassroomPackageError(
            f"Tên hiển thị tối đa {DISPLAY_NAME_MAX} ký tự.")
    return text


def normalize_block(value) -> str:
    text = str(value or "").strip()
    if text not in BLOCKS:
        raise cp.ClassroomPackageError("Khối phải là 10, 11 hoặc 12.")
    return text


def normalize_class_name(value, block=None) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip().upper()
    if not _CLASS_NAME_RE.fullmatch(text):
        raise cp.ClassroomPackageError(
            f"Tên lớp chỉ gồm chữ và số (tối đa {CLASS_NAME_MAX} ký tự), ví dụ 11A1.")
    if block is not None:
        block_str = str(block).strip()
        m = re.match(r"^(\d+)", text)
        if m and m.group(1) in BLOCKS and m.group(1) != block_str:
            raise cp.ClassroomPackageError(
                f"Tên lớp {text} không khớp với khối {block_str} đã chọn.")
    return text


def validate_password(value) -> str:
    if not isinstance(value, str) or not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        raise cp.ClassroomPackageError(
            f"Mật khẩu cần {PASSWORD_MIN}-{PASSWORD_MAX} ký tự.")
    return value


def username_digest(username: str) -> str:
    """Định danh giả cho Auth, không lộ tên đăng nhập gốc trong email."""
    return hashlib.sha256(f"self:{username}".encode()).hexdigest()


def student_state_payload(display_name, block, class_name, teacher_uid=None) -> dict:
    """Đúng bộ trường rules yêu cầu cho ``student_state/{uid}``."""
    b = normalize_block(block)
    return {
        "display_name": normalize_display_name(display_name),
        "block": b,
        "class_name": normalize_class_name(class_name, block=b),
        "teacher_uid": teacher_uid,
    }


def teacher_directory_payload(display_name) -> dict:
    return {"display_name": normalize_display_name(display_name)}


def roster_member_payload(state: Mapping) -> dict:
    """Dữ liệu dòng danh sách của GV, lấy từ hồ sơ HS; không kèm con trỏ GV."""
    return {
        "display_name": normalize_display_name(state.get("display_name")),
        "block": normalize_block(state.get("block")),
        "class_name": normalize_class_name(state.get("class_name")),
    }


def _block_key(block) -> int:
    try:
        return BLOCKS.index(str(block))
    except ValueError:
        return len(BLOCKS)


def sort_roster(rows) -> list:
    """Sắp xếp theo khối 10→11→12, rồi tên lớp, rồi tên học sinh."""
    ordered = sorted(
        rows,
        key=lambda row: (
            _block_key(row.get("block")),
            str(row.get("class_name", "")),
            unicodedata.normalize("NFC", str(row.get("display_name", ""))).casefold(),
        ),
    )
    return ordered
