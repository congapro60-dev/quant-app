"""Lớp ghim nút tài khoản bằng JavaScript (không phụ thuộc một class CSS)."""
from pathlib import Path

import pytest

import sticky_bar

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "qa_sticky_bar" / "index.html"


def test_component_file_exists_and_is_wired():
    assert COMPONENT.is_file(), "component ghim nút phải tồn tại trong repo"
    assert sticky_bar.BAR_KEY == "qa_account_bar"


def test_stick_account_bar_mounts_component(monkeypatch):
    calls = []

    def _fake(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(sticky_bar, "_component", _fake)
    assert sticky_bar.stick_account_bar() is True
    payload = calls[0]["payload"]
    assert payload["key"] == "qa_account_bar"
    assert payload["z"] < 1_000_000          # dưới lớp hộp thoại
    assert calls[0]["key"] == "qa_sticky_bar"


def test_stick_account_bar_never_raises_when_component_fails(monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("component chết")

    monkeypatch.setattr(sticky_bar, "_component", _boom)
    assert sticky_bar.stick_account_bar() is False


def test_component_matches_bar_by_class_fragment_and_sets_inline_style():
    """Khoá hợp đồng với trình duyệt: khớp một phần class + style trực tiếp.

    Nếu ai sửa component thành khớp class tuyệt đối, hoặc bỏ ``important``,
    nút sẽ rơi về dòng thường khi Streamlit đổi tiền tố class — chính là lỗi
    mà lớp ghim này sinh ra để chống.
    """

    html = COMPONENT.read_text(encoding="utf-8")
    assert 'class*="st-key-' in html, "phải khớp một phần class, không khớp tuyệt đối"
    assert "setProperty(\"position\", \"fixed\", \"important\")" in html
    assert "stAppToolbar" in html or "stHeader" in html, "phải đo thanh công cụ thật"
    assert "MutationObserver" in html, "phải ghim lại sau mỗi lần Streamlit rerun"
    assert "try {" in html, "lỗi phải nuốt im lặng, CSS vẫn là lớp dự phòng"


def test_app_calls_sticky_bar_after_account_bar():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "account_ui.render_account_bar()" in source
    assert "sticky_bar.stick_account_bar()" in source
    assert source.index("account_ui.render_account_bar()") < source.index(
        "sticky_bar.stick_account_bar()")
    assert "import sticky_bar" in source


@pytest.mark.parametrize("key", ["qa_account_bar", "custom_bar"])
def test_payload_accepts_custom_key(key):
    calls = []
    sticky_bar.stick_account_bar(key=key, gap=12, offset=24, z=999000,
                                 mount_key="probe")
    # Không mount thật trong pytest: chỉ khẳng định không ném lỗi.
    assert sticky_bar.BAR_KEY == "qa_account_bar"
