"""Kiểm tra nút tài khoản góc phải trên, trang riêng và nhớ đăng nhập.

Nguyên tắc: render tự nhiên **không gọi mạng** — mọi lời gọi Firebase nằm sau
nút bấm hoặc form. Nhờ vậy AppTest với api key giả vẫn chạy được.
"""
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import account_store as store
import firebase_classroom as fc

ROOT = Path(__file__).resolve().parents[1]
ENABLED_LITERAL = ("{'enabled':True,'project_id':'quant-app-classroom-20261026',"
                   "'api_key':'fake'}")


def _run(script: str) -> AppTest:
    return AppTest.from_string(script, default_timeout=40).run()


def _bar_script(extra: str = "") -> str:
    return ("import streamlit as st, account_ui as a\n"
            "from firebase_classroom import ClassroomSession\n"
            + extra +
            "a.render_account_bar(config=" + ENABLED_LITERAL + ")\n")


def _member_state() -> str:
    return ("if 'seeded' not in st.session_state:\n"
            "    st.session_state.seeded = True\n"
            "    st.session_state.update(self_session=ClassroomSession('uid-me','it','rt',9e9),"
            " self_profile={'kind':'teacher','display_name':'Cô Hồng'}, self_username='co-hong')\n")


def _button(at: AppTest, label: str):
    hits = [b for b in at.button if b.label == label]
    assert hits, f"thiếu nút {label}: {[b.label for b in at.button]}"
    return hits[0]


# ---------------- nút tài khoản ----------------


def test_bar_disabled_keeps_caption_and_no_widgets():
    at = _run("import account_ui as a\na.render_account_bar(config={})")
    assert not at.exception and not at.error
    assert not at.button
    assert any("chưa bật" in c.value for c in at.caption)


def test_bar_guest_offers_login_and_registration_without_network():
    at = _run(_bar_script())
    assert not at.exception and not at.error
    assert not at.text_input, "form đăng nhập nằm ở trang riêng, không nhét vào nút"
    assert [b.label for b in at.button] == ["Đăng nhập", "Đăng ký tài khoản"]


def test_bar_guest_buttons_open_the_dedicated_pages():
    at = _run(_bar_script())
    _button(at, "Đăng nhập").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["_account_page"] == "login"


def test_login_page_has_the_forms_and_queues_the_marker(monkeypatch):
    saved = []
    monkeypatch.setattr(store, "remember", lambda payload: saved.append(payload) or True)
    monkeypatch.setattr(fc.FirebaseClassroom, "login_self",
                        lambda self, u, p: fc.ClassroomSession("uid-me", "it", "t" * 40,
                                                               time.time() + 3600))
    monkeypatch.setattr(fc.FirebaseClassroom, "self_profile",
                        lambda self, s: {"kind": "student", "display_name": "An",
                                         "block": "11", "class_name": "11A1",
                                         "teacher_uid": None})
    at = _run("import streamlit as st, account_ui as a\n"
              "a.render_account_page(config=" + ENABLED_LITERAL + ")\n")
    at.query_params["account"] = "login"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.text_input) == 9
    at.text_input[0].set_value("hoc-sinh-01")
    at.text_input[1].set_value("mat-khau-8")
    _button(at, "Đăng nhập").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["self_session"].uid == "uid-me"
    # Dấu được xếp hàng ở lượt đăng nhập (chưa kịp ghi: có st.rerun ngay sau đó).
    pending = at.session_state["_account_pending_marker"]
    assert (pending["username"], pending["kind"]) == ("hoc-sinh-01", "student")


def test_marker_is_written_on_the_next_run_after_login(monkeypatch):
    """Component localStorage chỉ tới được trình duyệt khi lượt chạy kết thúc.

    Đăng nhập xong là ``st.rerun()`` ngay, nên dấu phải được ghi ở lượt kế tiếp
    — nếu ghi ngay trong lượt đăng nhập thì trình duyệt không bao giờ nhận.
    """

    saved = []
    monkeypatch.setattr(store, "remember", lambda payload: saved.append(payload) or True)
    at = _run("import streamlit as st, account_ui as a\n"
              "from firebase_classroom import ClassroomSession\n"
              "if 'seeded' not in st.session_state:\n"
              "    st.session_state.seeded = True\n"
              "    st.session_state.update(self_session=ClassroomSession('uid-me','it','t'*40,9e9),"
              " self_profile={'kind':'student','display_name':'An','block':'11',"
              "'class_name':'11A1','teacher_uid':None}, self_username='hoc-sinh-01',"
              " _account_pending_marker={'version':1,'username':'hoc-sinh-01','uid':'uid-me',"
              "'kind':'student','display_name':'An','refresh_token':'t'*40,'saved_at':" 
              + str(time.time()) + "})\n"
              "a.render_account_bar(config=" + ENABLED_LITERAL + ")\n")
    assert not at.exception, [str(e) for e in at.exception]
    assert [p["username"] for p in saved] == ["hoc-sinh-01"]
    assert at.session_state["_account_remembered"] is True
    assert "_account_pending_marker" not in at.session_state


def test_bar_member_shows_who_is_signed_in_and_role_tools():
    at = _run(_bar_script(_member_state()))
    assert not at.exception and not at.error
    assert any("Cô Hồng" in m.value for m in at.markdown)
    labels = [b.label for b in at.button]
    assert "Trang giáo viên" in labels and "Đăng xuất" in labels


def test_bar_and_account_page_do_not_share_widget_keys():
    """Nút tài khoản và trang tài khoản cùng hiện trên một màn hình.

    Trùng khoá widget từng làm trắng trang (StreamlitDuplicateElementKey) nên
    đây là bài kiểm chống tái phát.
    """

    script = (_bar_script(_member_state())
              + "if a.render_account_page(config=" + ENABLED_LITERAL + "):\n"
                "    st.write('PAGE-RENDERED')\n")
    at = _run(script)
    at.query_params["account"] = "teacher"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]


def test_logout_clears_session_and_browser_marker(monkeypatch):
    forgotten = []
    monkeypatch.setattr(store, "forget", lambda: forgotten.append(1) or True)
    at = _run(_bar_script(_member_state()))
    _button(at, "Đăng xuất").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert forgotten, "đăng xuất phải xoá dấu nhớ đăng nhập trong trình duyệt"
    assert "self_session" not in at.session_state
    assert "self_profile" not in at.session_state


def test_forget_button_keeps_session_but_drops_marker(monkeypatch):
    forgotten = []
    monkeypatch.setattr(store, "forget", lambda: forgotten.append(1) or True)
    at = _run(_bar_script(_member_state()
                          + "st.session_state['_account_remembered'] = True\n"))
    _button(at, "Quên tài khoản trên máy này").click().run()
    assert forgotten
    assert "self_session" in at.session_state


# ---------------- nhớ đăng nhập ----------------


def test_bootstrap_restores_session_from_browser_marker(monkeypatch):
    monkeypatch.setattr(store, "read_remembered", lambda: {
        "version": 1, "username": "co-hong", "uid": "uid-t", "kind": "teacher",
        "display_name": "Cô Hồng", "refresh_token": "t" * 40, "saved_at": time.time()})
    monkeypatch.setattr(fc.FirebaseClassroom, "session_from_refresh",
                        lambda self, token: fc.ClassroomSession("uid-t", "it", "t2" * 20,
                                                               time.time() + 3600))
    monkeypatch.setattr(fc.FirebaseClassroom, "self_profile",
                        lambda self, s: {"kind": "teacher", "display_name": "Cô Hồng"})
    at = _run("import account_ui as a\na.bootstrap(config=" + ENABLED_LITERAL + ")")
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["self_session"].uid == "uid-t"
    assert at.session_state["self_profile"]["kind"] == "teacher"
    assert at.session_state["_account_remembered"] is True


def test_bootstrap_drops_expired_marker(monkeypatch):
    forgotten = []
    monkeypatch.setattr(store, "forget", lambda: forgotten.append(1) or True)
    monkeypatch.setattr(store, "read_remembered", lambda: {
        "version": 1, "username": "co-hong", "uid": "uid-t", "kind": "teacher",
        "display_name": "Cô Hồng", "refresh_token": "t" * 40,
        "saved_at": time.time() - 40 * 24 * 3600})
    at = _run("import account_ui as a\na.bootstrap(config=" + ENABLED_LITERAL + ")")
    assert not at.exception and forgotten
    assert "self_session" not in at.session_state


def test_bootstrap_keeps_marker_when_network_fails(monkeypatch):
    forgotten = []
    monkeypatch.setattr(store, "forget", lambda: forgotten.append(1) or True)
    monkeypatch.setattr(store, "read_remembered", lambda: {
        "version": 1, "username": "co-hong", "uid": "uid-t", "kind": "teacher",
        "display_name": "Cô Hồng", "refresh_token": "t" * 40, "saved_at": time.time()})

    def _boom(self, token):
        raise fc.ClassroomConnectionError("Mất kết nối Firebase.", status_code=503)

    monkeypatch.setattr(fc.FirebaseClassroom, "session_from_refresh", _boom)
    at = _run("import account_ui as a\na.bootstrap(config=" + ENABLED_LITERAL + ")")
    assert not at.exception
    assert "self_session" not in at.session_state
    assert not forgotten, "lỗi mạng thì giữ dấu để lần sau thử lại"


def test_bootstrap_does_nothing_when_feature_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(store, "read_remembered", lambda: calls.append(1) or None)
    at = _run("import account_ui as a\na.bootstrap(config={})")
    assert not at.exception and not calls
    assert at.session_state["_account_restore_done"] is True


# ---------------- trang riêng ----------------


@pytest.mark.parametrize("page", ["login", "register", "student", "teacher"])
def test_account_pages_render_without_exception(page):
    at = _run("import streamlit as st, account_ui as a\n"
              "if a.render_account_page(config=" + ENABLED_LITERAL + "):\n"
              "    st.write('PAGE-RENDERED')\n")
    at.query_params["account"] = page
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert any("PAGE-RENDERED" in m.value for m in at.markdown)
    assert "← Quay lại ứng dụng" in [b.label for b in at.button]


def test_teacher_page_lists_roster_button_only_after_click(monkeypatch):
    monkeypatch.setattr(fc.FirebaseClassroom, "roster", lambda self, s: [])
    at = _run("import streamlit as st, account_ui as a\n"
              "from firebase_classroom import ClassroomSession\n" + _member_state()
              + "a.render_account_page(config=" + ENABLED_LITERAL + ")\n")
    at.query_params["account"] = "teacher"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert "Tải danh sách học sinh" in [b.label for b in at.button]
    _button(at, "Tải danh sách học sinh").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert any("Chưa có học sinh nào chọn thầy/cô" in i.value for i in at.info)


def test_student_page_warns_when_wrong_role_is_signed_in():
    at = _run("import streamlit as st, account_ui as a\n"
              "from firebase_classroom import ClassroomSession\n" + _member_state()
              + "a.render_account_page(config=" + ENABLED_LITERAL + ")\n")
    at.query_params["account"] = "student"
    at.run()
    assert not at.exception
    assert any("không mở được" in w.value for w in at.warning)


# ---------------- nối vào app ----------------


def test_app_boots_with_account_bar_and_no_hidden_duplicate_entry():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert any("chưa bật" in c.value for c in at.caption)


def test_classroom_tab_no_longer_mounts_self_service():
    """Khối đăng nhập cũ đã dời hẳn ra nút tài khoản: chỉ còn một cửa vào."""

    source = (ROOT / "learning_ui.py").read_text(encoding="utf-8")
    assert "render_self_service" not in source
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "account_ui.render_account_bar()" in app_source
    assert "account_ui.render_account_page()" in app_source
