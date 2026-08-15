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


def test_first_load_shows_no_red_error_at_all():
    """Trang vừa mở không được có hộp đỏ nào.

    Học sinh mở link mà thấy chữ đỏ sẽ tưởng phần mềm hỏng. Trạng thái "chỉ
    dùng mô phỏng" là mặc định an toàn nên hiện dạng thông tin, không phải lỗi.
    """

    at = _run(**{lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL})
    assert not at.exception
    assert [e.value for e in at.error] == []


def test_learner_sees_no_red_error_when_data_providers_fail():
    """Đúng tình huống trên máy chủ ngoài Việt Nam: mọi nguồn dữ liệu bị chặn."""

    at = _run(**{
        lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL,
        "data_status": "error",
        "data_error": (
            "Không tải được dữ liệu: Market-data validation failed after trying "
            "sources KBS, VCI, MSN (CTG:PROVIDER_ERROR; request:INCOMPLETE_PORTFOLIO)."
        ),
    })
    assert not at.exception
    assert [e.value for e in at.error] == []

    # Và phải nói rõ đường học vẫn dùng được.
    infos = " ".join(i.value for i in at.info)
    assert "Lộ trình học" in infos


def test_learner_never_sees_raw_provider_error_codes():
    at = _run(**{
        lmode.MODE_KEY: lmode.MODE_HIGHSCHOOL,
        "data_status": "error",
        "data_error": "PROVIDER_ERROR; INCOMPLETE_PORTFOLIO; HTTP 403",
    })
    shown = " ".join(
        [i.value for i in at.info] + [w.value for w in at.warning]
        + [e.value for e in at.error]
    )
    for jargon in ("PROVIDER_ERROR", "INCOMPLETE_PORTFOLIO", "403"):
        assert jargon not in shown, jargon


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


def test_changing_grade_switches_track_without_crashing():
    """Đường người dùng thật: mở app rồi đổi lớp sang sinh viên.

    Bản trước sập ở đây vì switch_mode ghi đè khoá widget `tickers_val` sau khi
    ô nhập đã được tạo, ném StreamlitAPIException và làm trắng trang.
    """

    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    # Mặc định là THPT; đặt lớp sinh viên để buộc đổi lộ trình trong lúc chạy.
    at.session_state[lmode.LEARNER_PROFILE_KEY] = {
        "grade_level": "sinh_vien", "knowledge_level": "co_ban", "goals": [],
    }
    at.run()

    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state[lmode.MODE_KEY] == lmode.MODE_UNIVERSITY
    assert at.tabs, "Đổi lộ trình xong vẫn phải dựng được các khu vực."


def test_widget_keys_are_not_restored_by_switch_mode():
    """Khoá widget nằm trong danh sách giữ lại sẽ làm sập trang khi đổi chế độ."""

    assert "tickers_val" not in lmode.PRESERVED_SESSION_KEYS


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
