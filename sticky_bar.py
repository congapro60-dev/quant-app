"""Ghim nút tài khoản bằng JavaScript, không phụ thuộc một class CSS cụ thể.

``app.py`` đã có CSS ghim (``.st-key-qa_account_bar``). Đây là lớp thứ hai:
một component ẩn đặt style **trực tiếp** lên phần tử và đo chiều cao thanh công
cụ thật, nên nút vẫn ở góc phải trên kể cả khi Streamlit đổi cách đặt tên
class, đổi chiều cao header, hoặc có khối cha tạo "containing block" mới.

Không thêm gói pip nào (dùng ``streamlit.components.v1``). Mọi lỗi đều nuốt
im lặng — CSS trong ``app.py`` vẫn là lớp dự phòng.
"""

from __future__ import annotations

import os

import streamlit.components.v1 as components

BAR_KEY = "qa_account_bar"
DEFAULT_Z = 999980

_component = components.declare_component(
    "qa_sticky_bar",
    path=os.path.join(os.path.dirname(__file__), "components", "qa_sticky_bar"),
)


def stick_account_bar(key: str = BAR_KEY, *, gap: int = 8, offset: int = 16,
                      z: int = DEFAULT_Z, mount_key: str = "qa_sticky_bar") -> bool:
    """Yêu cầu trình duyệt ghim nút tài khoản. Trả False khi không mount được."""

    try:
        _component(payload={"key": key, "gap": gap, "offset": offset, "z": z},
                   key=mount_key)
    except Exception:
        return False
    return True
