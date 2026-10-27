"""Unit checks cho tài khoản tự đăng ký: validators, client self-service, UI."""
import time
import unicodedata

import pytest
from streamlit.testing.v1 import AppTest

import classroom_packages as cp
import classroom_self as cself
import firebase_classroom as fc

ENABLED = {"enabled": True, "project_id": fc.PROJECT_ID, "api_key": "fake"}


def client():
    return fc.FirebaseClassroom(dict(ENABLED))


def session(uid="uidS"):
    return fc.ClassroomSession(uid, "fake", "fake", time.time() + 3600)


def _btn(at, label):
    hits = [b for b in at.button if b.label == label]
    assert hits, f"thiếu nút {label}"
    return hits[0]


def _widget(widgets, key):
    hits = [w for w in widgets if w.key == key]
    assert hits, f"thiếu widget {key}"
    return hits[0]


# ---------------- validators ----------------


def test_username_is_casefolded_nfc_and_rejects_bad_input():
    assert cself.normalize_username(" AnVan-01 ") == "anvan-01"
    # NFC gộp dấu: chuỗi tổ hợp NFD và chuỗi gộp sẵn cho cùng tên đăng nhập.
    decomposed = unicodedata.normalize("NFD", "NguyễnVănAn")
    assert cself.normalize_username(decomposed) == cself.normalize_username("NguyễnVănAn")
    for bad in ("abc", "a" * 33, "co khoang trang", "  An  Van ", "", "an\u200bvan", "an@van"):
        with pytest.raises(cp.ClassroomPackageError):
            cself.normalize_username(bad)


def test_display_name_block_class_and_password_rules():
    assert cself.normalize_display_name("  Nguyễn An ") == "Nguyễn An"
    with pytest.raises(cp.ClassroomPackageError):
        cself.normalize_display_name("   ")
    for bad in ("9", "13", "khối 10", ""):
        with pytest.raises(cp.ClassroomPackageError):
            cself.normalize_block(bad)
    assert cself.normalize_block(11) == "11"
    assert cself.normalize_class_name(" 11a1 ", block="11") == "11A1"
    with pytest.raises(cp.ClassroomPackageError):
        cself.normalize_class_name("11A1", block="10")
    for bad in ("11-A1", "LỚP 12", "A" * 17, ""):
        with pytest.raises(cp.ClassroomPackageError):
            cself.normalize_class_name(bad)
    assert cself.validate_password("12345678") == "12345678"
    for bad in ("1234567", "a" * 129, None, 12345678):
        with pytest.raises(cp.ClassroomPackageError):
            cself.validate_password(bad)


def test_payloads_and_sort_roster():
    state = cself.student_state_payload(" An ", "10", "10a2")
    assert state == {"display_name": "An", "block": "10", "class_name": "10A2",
                     "teacher_uid": None}
    member = cself.roster_member_payload({"display_name": "An", "block": "10",
                                          "class_name": "10A2", "teacher_uid": "uidT"})
    assert "teacher_uid" not in member
    rows = cself.sort_roster([
        {"block": "12", "class_name": "12B", "display_name": "Chí"},
        {"block": "10", "class_name": "10B", "display_name": "bảo"},
        {"block": "10", "class_name": "10A", "display_name": "An"},
        {"block": "11", "class_name": "11A1", "display_name": "Hà"},
        {"block": "9", "class_name": "9A", "display_name": "Khác"},
    ])
    assert [(r["block"], r["class_name"]) for r in rows] == [
        ("10", "10A"), ("10", "10B"), ("11", "11A1"), ("12", "12B"), ("9", "9A")]


# ---------------- client logic (không mạng) ----------------


def test_self_email_is_stable_and_separate_from_issued_accounts():
    assert fc.self_email(cself.normalize_username("An-01")) == fc.self_email("an-01")
    assert fc.self_email("an") != fc.account_email("student", "LOP", "HS-1")
    assert fc.self_email("an").endswith("@quant-app.invalid")


def test_login_self_rejects_short_password_before_network(monkeypatch):
    c = client()
    monkeypatch.setattr(c, "_auth",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    with pytest.raises(cp.ClassroomPackageError):
        c.login_self("hoc-sinh-01", "ngan")


def test_register_cleans_orphan_auth_account_when_profile_write_fails(monkeypatch):
    c = client()
    deleted = []
    monkeypatch.setattr(c, "_auth", lambda action, data: (
        {"localId": "uidNew", "idToken": "tok", "refreshToken": "r", "expiresIn": "3600"}
        if action == "signUp" else (deleted.append(data["idToken"]), {})[1]))
    # 1. Lỗi từ chối chắc chắn (ví dụ 400 do rules/schema): phải dọn tài khoản Auth mồ côi
    monkeypatch.setattr(c, "_write",
                        lambda *a, **k: (_ for _ in ()).throw(fc.ClassroomConnectionError("Lỗi", status_code=400)))
    with pytest.raises(fc.ClassroomConnectionError):
        c.register_student("hoc-sinh-01", "mat-khau-8", "An", "11", "11A1")
    assert deleted == ["tok"]
    # 2. Lỗi mạng không xác định (không có status_code client 4xx): không vội xóa
    deleted.clear()
    monkeypatch.setattr(c, "_write",
                        lambda *a, **k: (_ for _ in ()).throw(fc.ClassroomConnectionError("Mất mạng")))
    with pytest.raises(fc.ClassroomConnectionError):
        c.register_student("hoc-sinh-02", "mat-khau-8", "An", "11", "11A1")
    assert deleted == []


def test_join_teacher_builds_atomic_commit_and_refuses_self(monkeypatch):
    c = client()
    s = session("uidS")
    state = {"display_name": "An", "block": "11", "class_name": "11A1", "teacher_uid": None}
    monkeypatch.setattr(c, "get", lambda _sess, path: dict(state))
    commits = []
    monkeypatch.setattr(c, "_commit", lambda _sess, writes: commits.append(writes) or {})
    c.join_teacher(s, "uidT1")
    paths = [list(w)[0] + ":" + (w["update"]["name"] if "update" in w
                                 else w["delete"]) for w in commits[0]]
    assert len(commits[0]) == 2
    assert any(p.endswith("rosters/uidT1/members/uidS") for p in paths)
    assert any(p.endswith("student_state/uidS") for p in paths)
    state["teacher_uid"] = "uidT1"
    c.join_teacher(s, "uidT2")
    assert len(commits[1]) == 3  # xóa danh sách cũ + tạo mới + cập nhật con trỏ
    with pytest.raises(fc.ClassroomConnectionError):
        c.join_teacher(s, "uidS")


def test_leave_teacher_requires_current_teacher(monkeypatch):
    c = client()
    s = session("uidS")
    monkeypatch.setattr(c, "get", lambda _sess, path: {
        "display_name": "An", "block": "11", "class_name": "11A1", "teacher_uid": None})
    with pytest.raises(fc.ClassroomConnectionError):
        c.leave_teacher(s)
    monkeypatch.setattr(c, "get", lambda _sess, path: {
        "display_name": "An", "block": "11", "class_name": "11A1", "teacher_uid": "uidT1"})
    commits = []
    monkeypatch.setattr(c, "_commit", lambda _sess, writes: commits.append(writes) or {})
    c.leave_teacher(s)
    assert len(commits[0]) == 2
    update = next(w for w in commits[0] if "update" in w)
    assert fc.document_data(update["update"])["teacher_uid"] is None


def test_roster_parses_uid_and_sorts(monkeypatch):
    c = client()
    s = session("uidT")
    def doc(uid, name, class_name, hour):
        return {"name": f"projects/p/databases/(default)/documents/rosters/uidT/members/{uid}",
                "fields": {"display_name": fc._value(name), "block": fc._value("11"),
                           "class_name": fc._value(class_name),
                           "joined_at": fc._value(f"2026-10-27T0{hour}:00:00Z")}}
    pages = [{"documents": [doc("uidB", "Bình", "11A2", 1), doc("uidA", "An", "11A1", 2)]}]
    monkeypatch.setattr(fc, "_json_request", lambda *a, **k: pages.pop(0))
    rows = c.roster(s)
    assert [r["uid"] for r in rows] == ["uidA", "uidB"]
    assert rows[0]["class_name"] == "11A1"


def test_list_teachers_and_remove_student_and_profile_fallback(monkeypatch):
    c = client()
    s = session("uidS")
    monkeypatch.setattr(fc, "_json_request", lambda *a, **k: {"documents": [
        {"name": "projects/p/databases/(default)/documents/teacher_directory/uidT",
         "fields": {"display_name": fc._value("Cô Hồng")}}]})
    assert c.list_teachers(s) == [{"uid": "uidT", "display_name": "Cô Hồng"}]
    commits = []
    monkeypatch.setattr(c, "_commit", lambda _sess, writes: commits.append(writes) or {})
    c.remove_student(session("uidT"), "uidX")
    assert commits[0][0]["delete"].endswith("rosters/uidT/members/uidX")
    monkeypatch.setattr(c, "get", lambda _sess, path: (
        (_ for _ in ()).throw(fc.ClassroomNotFoundError())
        if path.startswith("student_state") else {"display_name": "Cô Hồng"}))
    assert c.self_profile(s)["kind"] == "teacher"
    monkeypatch.setattr(c, "get", lambda _sess, path: (
        (_ for _ in ()).throw(fc.ClassroomNotFoundError())))
    assert c.self_profile(s) == {"kind": "none"}
    # Lỗi kết nối / lỗi 500 không bị nuốt thành kind=none mà ném ra ngoài
    monkeypatch.setattr(c, "get", lambda _sess, path: (
        (_ for _ in ()).throw(fc.ClassroomConnectionError("Mất mạng", 500))))
    with pytest.raises(fc.ClassroomConnectionError):
        c.self_profile(s)


# ---------------- UI (AppTest, không mạng lúc render) ----------------


def run_self(script):
    return AppTest.from_string(script, default_timeout=30).run()


def test_self_service_disabled_keeps_quiet():
    at = run_self("import classroom_self_ui as ui\n"
                  "ui.render_self_service(config={})")
    assert not at.exception and not at.error
    assert not at.button and not at.text_input
    assert any("chưa bật" in c.value for c in at.caption)


def test_self_entry_boots_without_secrets_or_network():
    at = run_self("import classroom_self_ui as ui\n"
                  f"ui.render_self_service(config={ENABLED})")
    assert not at.exception and not at.error
    assert len(at.text_input) == 9  # 2 đăng nhập + 4 HS + 3 GV, mọi tab đều render
    assert list(at.selectbox[0].options) == ["10", "11", "12"]


def _session_script(profile, uid="uidS"):
    return ("import time, streamlit as st\n"
            "import classroom_self_ui as ui\n"
            "from firebase_classroom import ClassroomSession\n"
            f"st.session_state.update(self_session=ClassroomSession({uid!r},'fake','fake',time.time()+3600),\n"
            f"                        self_profile={profile!r})\n"
            f"ui.render_self_service(config={ENABLED})\n")


def test_student_panel_renders_without_network_and_has_picker():
    at = run_self(_session_script({"kind": "student", "display_name": "An", "block": "11",
                                   "class_name": "11A1", "teacher_uid": None}))
    assert not at.exception and not at.error
    labels = [b.label for b in at.button]
    assert any("Làm mới trạng thái" in label for label in labels)
    assert any("Chọn giáo viên" in label for label in labels)
    assert not any("Rút khỏi" in label for label in labels)  # chưa theo GV nào


def test_teacher_panel_renders_without_network():
    at = run_self(_session_script({"kind": "teacher", "display_name": "Cô Hồng"}, uid="uidT"))
    assert not at.exception and not at.error
    assert any("Tải danh sách học sinh" in b.label for b in at.button)


def test_student_pick_join_flow(monkeypatch):
    monkeypatch.setattr(fc.FirebaseClassroom, "list_teachers",
                        lambda self, _s: [{"uid": "uidT", "display_name": "Cô Hồng"}])
    monkeypatch.setattr(fc.FirebaseClassroom, "join_teacher",
                        lambda self, _s, tuid: (_ for _ in ()).throw(AssertionError(tuid))
                        if tuid != "uidT" else None)
    monkeypatch.setattr(fc.FirebaseClassroom, "self_profile",
                        lambda self, _s: {"kind": "student", "display_name": "An",
                                          "block": "11", "class_name": "11A1",
                                          "teacher_uid": "uidT"})
    at = run_self(_session_script({"kind": "student", "display_name": "An", "block": "11",
                                   "class_name": "11A1", "teacher_uid": None}))
    _btn(at, "Chọn giáo viên hướng dẫn / đổi giáo viên").click().run()
    assert not at.exception and not at.error
    _btn(at, "Tải danh sách giáo viên").click().run()
    assert not at.exception and not at.error
    picker = _widget(at.selectbox, "self_teacher_choice")
    assert picker.value == "uidT"
    _btn(at, "Vào danh sách của giáo viên này").click().run()
    assert not at.exception and not at.error
    assert any("Đã vào danh sách" in s.value for s in at.success)


def test_teacher_roster_remove_flow(monkeypatch):
    rows = [{"uid": "uidA", "display_name": "An", "block": "11", "class_name": "11A1",
             "joined_at": "2026-10-27T01:00:00Z"}]
    monkeypatch.setattr(fc.FirebaseClassroom, "roster", lambda self, _s: list(rows))
    monkeypatch.setattr(fc.FirebaseClassroom, "remove_student", lambda self, _s, uid: None)
    at = run_self(_session_script({"kind": "teacher", "display_name": "Cô Hồng"}, uid="uidT"))
    _btn(at, "Tải danh sách học sinh").click().run()
    assert not at.exception and not at.error
    assert _widget(at.selectbox, "self_remove_choice").value == "uidA"
    _btn(at, "Xóa khỏi danh sách").click().run()
    assert not at.exception and not at.error
    assert any("Đã xóa khỏi danh sách" in s.value for s in at.success)


def test_student_register_form_logs_in_after_success(monkeypatch):
    monkeypatch.setattr(fc.FirebaseClassroom, "register_student",
                        lambda self, *a: fc.ClassroomSession("uidNew", "fake", "fake",
                                                             time.time() + 3600))
    monkeypatch.setattr(fc.FirebaseClassroom, "self_profile",
                        lambda self, _s: {"kind": "student", "display_name": "An",
                                          "block": "11", "class_name": "11A1",
                                          "teacher_uid": None})
    at = run_self("import classroom_self_ui as ui\n"
                  f"ui.render_self_service(config={ENABLED})")
    at.text_input[2].set_value("hoc-sinh-01")       # tên đăng nhập (form HS)
    at.text_input[3].set_value("An")
    at.text_input[4].set_value("11A1")
    at.text_input[5].set_value("mat-khau-8")
    _btn(at, "Đăng ký học sinh").click().run()
    assert not at.exception and not at.error
    assert at.session_state["self_session"].uid == "uidNew"
    labels = [b.label for b in at.button]
    assert any("Chọn giáo viên" in label for label in labels)
