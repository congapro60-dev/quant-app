"""Giao diện sáng và tối: một bộ CSS, hai bảng màu.

Màu nền chính của Streamlit nằm ở ``[theme.light]`` / ``[theme.dark]`` trong
``.streamlit/config.toml``; người dùng đổi ở menu ⋮ → Settings → Theme, mặc định
theo thiết bị. Module này lo phần CSS riêng của ứng dụng, chọn bảng màu theo
``st.context.theme.type``.

Thêm màu mới thì thêm vào cả hai bảng: ``tests/test_theme_ui.py`` đo độ tương
phản và chặn việc gắn cứng màu trong CSS.
"""

from __future__ import annotations

import streamlit as st

LIGHT = "light"
DARK = "dark"

PALETTES = {
    DARK: {
        "primary": "#1D4ED8", "primary-soft": "#172554", "accent": "#D97706",
        "app-bg": "#0B1220", "app-glow": "#142D3B", "surface": "#111827",
        "surface-2": "#172033", "border": "#334155", "sidebar-border": "#273547",
        "text": "#F8FAFC", "muted": "#CBD5E1", "danger": "#EF4444", "success": "#10B981",
        "eyebrow": "#5EEAD4", "tab-active-bg": "#134E4A", "tab-active-border": "#5EEAD4",
        "tab-active-text": "#F0FDFA", "hero-strong": "#BFDBFE", "focus": "#F59E0B",
        "shadow": "rgba(0,0,0,.16)", "bar-bg": "rgba(17,24,39,.92)",
        "bar-shadow": "rgba(0,0,0,.35)",
    },
    LIGHT: {
        "primary": "#1D4ED8", "primary-soft": "#DBEAFE", "accent": "#B45309",
        "app-bg": "#F8FAFC", "app-glow": "#E0F2FE", "surface": "#FFFFFF",
        "surface-2": "#F1F5F9", "border": "#CBD5E1", "sidebar-border": "#E2E8F0",
        "text": "#0F172A", "muted": "#475569", "danger": "#B91C1C", "success": "#047857",
        "eyebrow": "#0F766E", "tab-active-bg": "#CCFBF1", "tab-active-border": "#0F766E",
        "tab-active-text": "#134E4A", "hero-strong": "#1D4ED8", "focus": "#B45309",
        "shadow": "rgba(15,23,42,.08)", "bar-bg": "rgba(255,255,255,.95)",
        "bar-shadow": "rgba(15,23,42,.15)",
    },
}

_CSS = """
    .stApp { background: radial-gradient(ellipse at 90% 0%, var(--qa-app-glow) 0%, transparent 45%), var(--qa-app-bg); }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    h2 { font-size: 1.9rem !important; }
    h3 { font-size: 1.2rem !important; }
    .qa-eyebrow { color: var(--qa-eyebrow); font-size: .75rem; letter-spacing: .13em; font-weight: 700; }
    [data-testid="stSidebar"] { border-right: 1px solid var(--qa-sidebar-border); }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
    button { min-height: 44px; }
    p, label { overflow-wrap: anywhere; }
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, var(--qa-surface) 0%, var(--qa-surface-2) 100%);
        border: 1px solid var(--qa-border); border-radius: 12px; padding: 14px 16px;
        box-shadow: 0 8px 24px var(--qa-shadow);
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stTabs [role="tablist"] { gap: 6px; flex-wrap: wrap; height: auto; overflow: visible; }
    .stTabs [role="tab"] {
        background-color: var(--qa-surface); border: 1px solid var(--qa-border);
        border-radius: 8px; padding: 10px 14px; min-height: 44px; height: auto; white-space: normal;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--qa-tab-active-bg); border-color: var(--qa-tab-active-border);
        color: var(--qa-tab-active-text);
    }
    .stTabs .react-aria-SelectionIndicator { display: none; }
    .stTabs [role="tab"]:focus-visible,
    button:focus-visible, input:focus-visible, textarea:focus-visible {
        outline: 3px solid var(--qa-focus) !important; outline-offset: 2px;
    }
    .qa-hero {
        padding: 8px 0 18px; border-bottom: 1px solid var(--qa-border); margin-bottom: 4px;
    }
    .qa-hero h1 { font-size: 2rem; line-height: 1.16; }
    .qa-hero strong { color: var(--qa-hero-strong); }
    .qa-safety {
        padding: 8px 0; color: var(--qa-muted); font-size: .86rem;
    }
    @media (max-width: 768px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .stTabs [role="tab"] { padding: 8px 10px; flex: 1 1 40%; }
        .qa-hero { padding: 8px 0 14px; }
        .qa-hero h1 { font-size: 1.75rem; line-height: 1.2; }
    }
    @media (prefers-reduced-motion: no-preference) {
        .qa-hero { animation: qa-reveal .35s ease-out; }
        @keyframes qa-reveal { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }
    }
    /* Nút tài khoản: ghim góc phải trên, đặt ngay dưới thanh công cụ của
       Streamlit để không đè lên nút Fork/GitHub/menu. z-index cố ý nằm DƯỚI
       lớp hộp thoại (tour, st.dialog) để hộp thoại vẫn che trên đúng thứ tự.
       Màn hẹp thì trả về dòng thường cho khỏi che nội dung. */
    .st-key-qa_account_bar {
        position: fixed; top: 3.4rem; right: 1rem; z-index: 999980;
        width: fit-content; max-width: calc(100vw - 2rem);
    }
    .st-key-qa_account_bar [data-testid="stPopover"] button {
        background: var(--qa-bar-bg); border: 1px solid var(--qa-border);
        box-shadow: 0 6px 18px var(--qa-bar-shadow); min-width: 10rem;
    }
    [data-testid="stPopoverBody"] { min-width: 17rem; }
    @media (max-width: 640px) { .st-key-qa_account_bar { position: static; } }
"""


def current_theme() -> str:
    """Giao diện đang dùng; không đọc được thì coi là tối như trước đây."""

    try:
        return LIGHT if st.context.theme.type == LIGHT else DARK
    except Exception:
        return DARK


def build_css(theme: str) -> str:
    palette = PALETTES[theme if theme in PALETTES else DARK]
    variables = "\n".join(f"        --qa-{name}: {value};" for name, value in palette.items())
    return f"<style>\n    :root {{\n{variables}\n    }}\n{_CSS}</style>"


def apply_theme() -> None:
    st.markdown(build_css(current_theme()), unsafe_allow_html=True)
