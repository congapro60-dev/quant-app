"""Chạy thật ứng dụng Streamlit bằng AppTest để bắt lỗi dựng giao diện.

Kiểm thử đơn vị không chứng minh được trang có dựng nổi. Nhóm này chạy toàn bộ
``app.py`` trong cả hai chế độ và khẳng định không có ngoại lệ nào thoát ra.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

import learning_modes as lmode

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = 120


# Lớp quyết định lộ trình, nên muốn dựng một chế độ thì phải đặt lớp tương ứng.
# Đặt mỗi MODE_KEY sẽ bị đồng bộ lại theo lớp mặc định.
_GRADE_FOR_MODE = {
    lmode.MODE_HIGHSCHOOL: "lop_11",
    lmode.MODE_UNIVERSITY: "sinh_vien",
}


def _run(**session) -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)

    mode = session.get(lmode.MODE_KEY)
    if mode in _GRADE_FOR_MODE and lmode.LEARNER_PROFILE_KEY not in session:
        session[lmode.LEARNER_PROFILE_KEY] = {
            "grade_level": _GRADE_FOR_MODE[mode],
            "knowledge_level": "co_ban",
            "goals": [],
        }

    for key, value in session.items():
        at.session_state[key] = value
    return at.run()


def test_app_boots_without_exception_in_highschool_mode():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL})
    assert not at.exception, [str(e) for e in at.exception]


def test_app_boots_without_exception_in_university_mode():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_UNIVERSITY})
    assert not at.exception, [str(e) for e in at.exception]


def test_app_reports_no_unexpected_error_on_first_load():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL})
    assert not at.exception

    # Cổng vốn thật cố ý báo đỏ khi chưa khai báo tuổi: đó là kết luận đúng
    # ("chỉ dùng mô phỏng"), không phải sự cố. Mọi thông báo lỗi khác thì không
    # được xuất hiện trên một trang vừa mở.
    unexpected = [
        e.value for e in at.error
        if "chỉ dùng giao dịch mô phỏng" not in e.value
    ]
    assert unexpected == [], unexpected


def test_university_renders_all_five_areas():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_UNIVERSITY})
    assert not at.exception
    labels = {t.label for t in at.tabs}
    for area in lmode.AREA_ORDER:
        assert lmode.AREA_LABELS[area] in labels, area


def test_locked_highschool_does_not_render_an_empty_model_lab():
    """Thẻ trắng làm người dùng tưởng ứng dụng hỏng."""

    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL, lmode.UNLOCK_KEY: False})
    assert not at.exception
    labels = {t.label for t in at.tabs}
    assert lmode.AREA_LABELS[lmode.AREA_MODEL_LAB] not in labels
    assert lmode.AREA_LABELS[lmode.AREA_LEARNING] in labels


def test_learning_area_content_differs_between_tracks():
    """Đổi lộ trình phải thấy khác, không chỉ ẩn vài thẻ con."""

    hs = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL})
    uni = _run(**{lmode.MODE_KEY: lmode.MODE_UNIVERSITY})
    assert not hs.exception and not uni.exception

    def _headers(at):
        return " ".join(h.value for h in at.header)

    assert "Lộ trình định lượng" in _headers(uni)
    assert "Lộ trình định lượng" not in _headers(hs)
    assert _headers(hs) != _headers(uni)


def test_university_mode_exposes_all_nine_features():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_UNIVERSITY})
    assert not at.exception
    labels = {t.label for t in at.tabs}
    for meta in lmode.FEATURES.values():
        assert meta["label"] in labels, meta["label"]


def test_highschool_hides_advanced_feature_tabs_until_unlocked():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL, lmode.UNLOCK_KEY: False})
    assert not at.exception
    labels = {t.label for t in at.tabs}

    for feature in (lmode.FEATURE_SIM, lmode.FEATURE_MARKOWITZ,
                    lmode.FEATURE_EVIEWS, lmode.FEATURE_BACKTEST):
        assert lmode.FEATURES[feature]["label"] not in labels, feature

    # Nhóm cơ bản vẫn phải dùng được ngay từ đầu.
    assert lmode.FEATURES[lmode.FEATURE_PAPER]["label"] in labels


def test_highschool_shows_advanced_tabs_after_unlock():
    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL, lmode.UNLOCK_KEY: True})
    assert not at.exception
    labels = {t.label for t in at.tabs}
    assert lmode.FEATURES[lmode.FEATURE_SIM]["label"] in labels


@pytest.mark.parametrize("mode", list(lmode.VALID_MODES))
def test_learning_area_renders_module_list(mode):
    at = _run(**{lmode.MODE_KEY: mode})
    assert not at.exception
    assert at.selectbox, "Khu vực Lộ trình học phải có bộ chọn mô-đun."
