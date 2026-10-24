"""Lưu và khôi phục hồ sơ tiến độ vào localStorage của trình duyệt.

Nấc 1 của kế hoạch lưu trữ: không tài khoản, không máy chủ. Hồ sơ chỉ nằm ở
trình duyệt của người học (key ``quantapp.progress.v1``) và tự khôi phục khi
mở lại ứng dụng. Tệp JSON xuất tay ở tab "Nhật ký và tiến độ" vẫn giữ nguyên
vai trò sao lưu chính thức — hai cơ chế không mâu thuẫn nhau.

An toàn: dữ liệu đọc từ localStorage được coi là **không đáng tin** và đi qua
đúng :func:`progress_profile.import_json`, tức cùng bộ kiểm tra kích thước,
độ sâu, khóa, kiểu và miền giá trị như nạp tệp. Sai một điểm là bỏ qua cả hồ
sơ, không cố sửa. Component chạy ẩn (height 0) trong iframe, dùng giao thức
postMessage chuẩn của Streamlit Components nên không thêm gói pip nào.
"""

from __future__ import annotations

import json
import os
from typing import Any

import streamlit.components.v1 as components

import progress_profile as pp

STORAGE_KEY = "quantapp.progress.v1"

# Ngưỡng "bài đã đạt" khớp dòng mô tả trong lộ trình học: đạt từ 70/100 điểm.
PASS_SCORE = 70.0

# Cờ phiên: khôi phục đúng một lần, banner chỉ hiện đúng lần render có nạp.
RESTORED_FLAG = "_progress_restored"
RESTORE_BANNER = "_progress_restore_banner"

_component = components.declare_component(
    "qa_progress_store",
    path=os.path.join(os.path.dirname(__file__), "components", "qa_progress_store"),
)


def read_stored_progress() -> dict[str, Any] | None:
    """Đọc hồ sơ từ localStorage; mọi lỗi đều trả None, không cố sửa."""

    try:
        value = _component(mode="restore", payload=None, key="qa_progress_restore")
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def payload_from_state(state: dict[str, Any]) -> dict[str, Any] | None:
    """Hồ sơ của phiên hiện tại dưới dạng dict sạch để ghi vào localStorage."""

    profile = state.get("progress_profile")
    if not isinstance(profile, dict):
        return None
    try:
        data = json.loads(pp.export_json(profile))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def passed_lesson_count(profile: dict[str, Any] | None) -> int:
    """Số bài đã đạt (điểm >= PASS_SCORE) trong hồ sơ."""

    if not isinstance(profile, dict):
        return 0
    count = 0
    for value in (profile.get("lesson_scores") or {}).values():
        try:
            if float(value) >= PASS_SCORE:
                count += 1
        except (TypeError, ValueError):
            continue
    return count


def restore_progress(state: dict[str, Any]) -> int:
    """Khôi phục hồ sơ từ localStorage, đúng một lần mỗi phiên.

    Chỉ nạp khi hồ sơ phiên còn trống, để không đè dữ liệu học sinh vừa làm
    trong phiên này. Trả về số bài đạt được khôi phục (0 nếu không nạp gì).
    """

    if state.get(RESTORED_FLAG):
        return 0
    state[RESTORED_FLAG] = True
    data = read_stored_progress()
    if not isinstance(data, dict):
        return 0
    try:
        profile = pp.import_json(json.dumps(data, ensure_ascii=False))
    except Exception:
        # Dữ liệu hỏng hoặc bị từ chối kiểm tra an toàn: bỏ qua cả hồ sơ.
        return 0
    current = state.get("progress_profile")
    if not isinstance(current, dict):
        current = pp.empty_profile()
    if current.get("lesson_scores") or current.get("lesson_attempts"):
        return 0
    state["progress_profile"] = profile
    passed = passed_lesson_count(profile)
    if passed:
        state[RESTORE_BANNER] = passed
    return passed


def persist_progress(state: dict[str, Any]) -> bool:
    """Ghi hồ sơ phiên vào localStorage; im lặng khi không có gì để ghi."""

    payload = payload_from_state(state)
    if payload is None:
        return False
    try:
        _component(mode="save", payload=payload, key="qa_progress_save")
    except Exception:
        return False
    return True
