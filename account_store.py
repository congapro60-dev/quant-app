"""Nhớ đăng nhập tài khoản tự đăng ký trong localStorage của trình duyệt.

Cùng khuôn với ``progress_store``: component ẩn (height 0) nói chuyện với
trình duyệt qua postMessage, không thêm gói pip nào.

Vì sao phải có: ``st.session_state`` của Streamlit bị xoá khi mở tab mới hoặc
tải lại trang. Muốn "đăng nhập nhớ lâu" như hộp thư, phải để lại một dấu trong
trình duyệt rồi tự đổi lấy phiên mới khi mở lại app. Dấu đó là **refresh token**
của Firebase, kèm tên đăng nhập để hiển thị đúng người đang đăng nhập.

An toàn: dữ liệu đọc từ localStorage là **không đáng tin**, đi qua
:func:`sanitize` (đúng bộ khoá, đúng kiểu, độ dài hợp lý); sai một điểm là bỏ
hẳn. Dấu cũ hơn ``MAX_AGE_DAYS`` cũng bị bỏ, buộc đăng nhập lại. Refresh token
được Firebase luân chuyển mỗi lần làm mới phiên, nên phải ghi lại sau mỗi lần
refresh — việc này do hook ``on_refresh`` của ``FirebaseClassroom`` gọi.
"""

from __future__ import annotations

import os
import time
from typing import Any

import streamlit.components.v1 as components

ACCOUNT_KEY = "quantapp.account.v1"

# Dấu cũ hơn ngần này thì buộc đăng nhập lại: máy dùng chung ở lớp không giữ
# quyền truy cập tài khoản của người học trước mãi mãi.
MAX_AGE_DAYS = 30
MAX_AGE_SECONDS = MAX_AGE_DAYS * 24 * 3600

MAX_TOKEN_LEN = 4096
MAX_FIELD_LEN = 120

STORED_KEYS = ("version", "username", "uid", "kind", "display_name",
               "refresh_token", "saved_at")
KINDS = ("student", "teacher")

_component = components.declare_component(
    "qa_account_store",
    path=os.path.join(os.path.dirname(__file__), "components", "qa_account_store"),
)


def _text(value: Any, limit: int = MAX_FIELD_LEN) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if 0 < len(text) <= limit else None


def sanitize(raw: Any) -> dict[str, Any] | None:
    """Dấu trong trình duyệt có hợp lệ để dùng lại hay không."""

    if not isinstance(raw, dict):
        return None
    if set(raw) - set(STORED_KEYS):
        return None
    username = _text(raw.get("username"))
    uid = _text(raw.get("uid"), 256)
    kind = raw.get("kind")
    display_name = _text(raw.get("display_name"))
    refresh_token = raw.get("refresh_token")
    saved_at = raw.get("saved_at")
    if not username or not uid or kind not in KINDS:
        return None
    if not display_name or not isinstance(refresh_token, str):
        return None
    if not 10 < len(refresh_token) <= MAX_TOKEN_LEN:
        return None
    if isinstance(saved_at, bool) or not isinstance(saved_at, (int, float)):
        return None
    return {
        "version": 1,
        "username": username,
        "uid": uid,
        "kind": kind,
        "display_name": display_name,
        "refresh_token": refresh_token,
        "saved_at": float(saved_at),
    }


def payload_from_session(session: Any, profile: dict[str, Any] | None,
                         username: str, *, now: float | None = None) -> dict[str, Any] | None:
    """Gói dấu để ghi xuống trình duyệt từ phiên đang đăng nhập."""

    profile = profile if isinstance(profile, dict) else {}
    name = _text(profile.get("display_name"))
    kind = profile.get("kind")
    username = _text(username)
    token = getattr(session, "refresh_token", None)
    uid = getattr(session, "uid", None)
    if not (name and kind in KINDS and username and isinstance(token, str) and uid):
        return None
    return sanitize({
        "version": 1,
        "username": username,
        "uid": uid,
        "kind": kind,
        "display_name": name,
        "refresh_token": token,
        "saved_at": time.time() if now is None else float(now),
    })


def is_fresh(payload: dict[str, Any], *, now: float | None = None) -> bool:
    stamp = payload.get("saved_at") if isinstance(payload, dict) else None
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return False
    current = time.time() if now is None else float(now)
    return 0 <= current - float(stamp) <= MAX_AGE_SECONDS


def read_remembered() -> dict[str, Any] | None:
    """Đọc dấu từ trình duyệt; chưa có hoặc hỏng đều trả None."""

    try:
        value = _component(mode="restore", payload=None, key="qa_account_restore")
    except Exception:
        return None
    return sanitize(value)


def remember(payload: dict[str, Any] | None) -> bool:
    """Ghi dấu xuống trình duyệt; im lặng khi dữ liệu không hợp lệ."""

    clean = sanitize(payload)
    if clean is None:
        return False
    try:
        _component(mode="save", payload=clean, key="qa_account_save")
    except Exception:
        return False
    return True


def forget() -> bool:
    """Xoá dấu: dùng khi đăng xuất hoặc khi dấu đã quá hạn / không còn hiệu lực."""

    try:
        _component(mode="clear", payload=None, key="qa_account_clear")
    except Exception:
        return False
    return True
