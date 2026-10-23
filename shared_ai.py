"""AI dùng chung do trang cấp — luồng mặc định để học sinh không cần key riêng.

Thứ tự ưu tiên mọi hoạt động AI trong app:

1. Key riêng học sinh nhập ở thanh bên → dùng luồng của em ấy (đã có sẵn).
2. Không nhập thì dùng cấu hình dùng chung đọc từ ``[shared_ai]`` trong Secrets
   của Streamlit Cloud. Bí mật chỉ nằm ở dashboard của chủ app, KHÔNG dán vào
   mã nguồn (repo là công khai), và ``.streamlit/secrets.toml`` đã nằm trong
   ``.gitignore``.
3. Chưa cấu hình được thì giao diện hiển thị trạng thái lịch sự, không vỡ.

Cấu hình ``[shared_ai]`` cần ba trường: ``base_url`` (máy chủ tương thích
OpenAI, ví dụ ``https://example.com/v1``), ``model`` (mã mô hình) và
``api_key`` (khóa của chủ app). ``display_name`` tùy chọn, dùng để hiển thị
tên thân thiện ở thanh bên.
"""

from __future__ import annotations

from collections.abc import Mapping

from analytics import OPENAI_COMPATIBLE_PROVIDER

SECTION = "shared_ai"
SHARED_PROVIDER_OPTION = "AI dùng chung (cấp sẵn của trang)"
PERSONAL_ROUTER_OPTION = "Router riêng của em (key riêng)"

_REQUIRED = (
    ("api_key", "khóa API (api_key)"),
    ("base_url", "địa chỉ máy chủ (base_url)"),
    ("model", "mã mô hình (model)"),
)

_NOT_CONFIGURED_NOTICE = (
    "Trang chưa cài AI dùng chung: cần mục [{section}] trong Secrets của app "
    "(chỉ chủ app nhập). Bạn vẫn dùng được AI bằng key riêng."
)


def _read_section(secrets_source):
    """Đọc mục ``[shared_ai]`` từ nguồn Secrets được cung cấp (hoặc Streamlit).

    Trả ``None`` một cách an toàn khi: chưa có file secrets, thiếu mục, hoặc
    chạy ngoài môi trường Streamlit (ví dụ khi chạy pytest).
    """

    try:
        if secrets_source is not None:
            return secrets_source.get(SECTION)
        import streamlit as st

        return st.secrets.get(SECTION)
    except Exception:
        return None


def shared_ai_config(secrets_source=None):
    """Trả về ``(config, thông_điệp)``; ``config`` là ``None`` khi chưa dùng được.

    ``secrets_source`` là mapping thay thế cho ``st.secrets`` — phục vụ kiểm
    thử đơn vị mà không cần môi trường Streamlit.
    """

    raw = _read_section(secrets_source)
    if not raw or not isinstance(raw, Mapping):
        return None, _NOT_CONFIGURED_NOTICE.format(section=SECTION)

    values = {
        "api_key": str(raw.get("api_key", "")).strip(),
        "base_url": str(raw.get("base_url", "")).strip(),
        "model": str(raw.get("model", "")).strip(),
        "display_name": str(raw.get("display_name", "")).strip()
        or "AI dùng chung của trang",
    }
    missing = [label for field, label in _REQUIRED if not values[field]]
    if missing:
        return None, (
            f"{values['display_name']} chưa dùng được vì thiếu: "
            f"{', '.join(missing)} trong Secrets (mục [{SECTION}])."
        )
    config = {
        "provider": OPENAI_COMPATIBLE_PROVIDER,
        "api_key": values["api_key"],
        "base_url": values["base_url"],
        "model": values["model"],
        "display_name": values["display_name"],
    }
    return config, ""
