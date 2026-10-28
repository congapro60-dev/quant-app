"""Unit checks for auth/token handling, config and real receipts."""
import json
import time
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

import classroom_packages as cp
import classroom_submit as cs
import firebase_classroom as fc
import progress_profile as pp


def summary():
    a = cp.make_assignment(assignment_id="QA-01", title="QA", instructions="Giả lập",
                           lesson_ids=["m1"])
    return cs.build_submission(pp.empty_profile(), a, "QA-LOP", "HS-QA1")


def test_auth_uses_synthetic_identifiers_and_never_a_pupil_email():
    assert fc.account_email("student", "qa-lop", "hs-qa1") == fc.account_email("student", "QA-LOP", "HS-QA1")
    assert fc.account_email("student", "QA-LOP", "HS-QA1").endswith("@quant-app.invalid")
    assert fc.account_email("teacher", "", "GV-QA1") != fc.account_email("student", "QA-LOP", "GV-QA1")


def test_credentials_are_not_in_session_repr():
    assert "secret" not in repr(fc.ClassroomSession("u", "secret-id", "secret-refresh", time.time()))


def test_firestore_serialization_preserves_types():
    original = {"null": None, "integer": 7, "float": 3.5, "bool": False,
                "text": "Dữ liệu", "list": [None, 10, {"score": 85}]}
    assert fc.document_data({"fields": {k: fc._value(v) for k, v in original.items()}}) == original


def test_bad_project_is_rejected():
    with pytest.raises(cs.SubmissionNotConfiguredError):
        fc.FirebaseClassroom({"project_id": "someone-else", "api_key": "fake"})


def test_submit_checks_binding_and_requires_server_receipt(monkeypatch):
    client = fc.FirebaseClassroom({"project_id": fc.PROJECT_ID, "api_key": "fake"})
    session = fc.ClassroomSession("uid1", "fake", "fake", time.time()+3600)
    monkeypatch.setattr(client, "get", lambda *_args: {"uid": "uid2"})
    with pytest.raises(fc.ClassroomConnectionError):
        cs.submit(summary(), client=client, session=session)
    monkeypatch.setattr(client, "get", lambda *_args: {"uid": "uid1"})
    monkeypatch.setattr(client, "_commit", lambda *_args, **_kw: {})
    with pytest.raises(fc.ClassroomConnectionError):
        cs.submit(summary(), client=client, session=session)
    monkeypatch.setattr(client, "_commit", lambda *_args, **_kw: {"commitTime": "2026-10-26T12:00:00Z", "writeResults": [{}]})
    result = cs.submit(summary(), client=client, session=session)
    assert len(result["receipt_id"]) == 64
    assert result["received_at"] == "2026-10-26T12:00:00Z"


def test_submit_rejects_edited_outbound_payload_before_network():
    data = summary()
    data["lesson_results"][0]["email"] = "fake@example.com"
    with pytest.raises(cs.SubmissionValidationError):
        cs.validate_submission(data)


def test_roster_submission_uses_uid_and_self_marker():
    """HS tự đăng ký: mã lớp cố định SELF, mã học sinh là uid (không cần chữ số)."""
    profile = pp.empty_profile()
    profile["lesson_scores"]["m1"] = 0.85
    assignment = cp.make_assignment(assignment_id="QA-01", title="QA",
                                    instructions="Giả lập", lesson_ids=["m1"])
    data = cs.build_roster_submission(profile, assignment, "AbCdEfGhIj")
    assert data["class_code"] == "SELF"
    assert data["student_code"] == "AbCdEfGhIj"   # uid không có chữ số vẫn hợp lệ
    cs.validate_submission(data, student_code_check=cs._uid_code)
    # Kênh cũ vẫn từ chối uid này (thiếu chữ số): hai luồng không trộn nhau
    with pytest.raises(cs.SubmissionValidationError):
        cs.validate_submission(data)


def test_submit_roster_requires_membership_and_teacher(monkeypatch):
    client = fc.FirebaseClassroom({"project_id": fc.PROJECT_ID, "api_key": "fake"})
    session = fc.ClassroomSession("uidS", "fake", "fake", time.time() + 3600)
    assignment = cp.make_assignment(assignment_id="QA-01", title="QA",
                                    instructions="Giả lập", lesson_ids=["m1"])
    data = cs.build_roster_submission(pp.empty_profile(), assignment, "uidS")

    # Chưa chọn GV: chặn trước khi gọi mạng
    monkeypatch.setattr(client, "get", lambda _s, path: {"teacher_uid": None})
    with pytest.raises(fc.ClassroomConnectionError):
        client.submit_roster(session, data)

    # Đã chọn GV nhưng vừa bị xóa khỏi danh sách (404): chặn trước khi nộp
    def _get_removed(_s, path):
        if path.startswith("student_state"):
            return {"teacher_uid": "uidT"}
        raise fc.ClassroomNotFoundError()

    monkeypatch.setattr(client, "get", _get_removed)
    with pytest.raises(fc.ClassroomNotFoundError):
        client.submit_roster(session, data)

    # Còn thành viên: 1 commit gồm header + lessons, biên nhận đủ
    commits = []

    def _get_ok(_s, path):
        if path.startswith("student_state"):
            return {"teacher_uid": "uidT"}
        return {"display_name": "An", "block": "11", "class_name": "11A1"}

    monkeypatch.setattr(client, "get", _get_ok)
    monkeypatch.setattr(client, "_commit",
                        lambda _s, writes: commits.append(writes)
                        or {"commitTime": "2026-10-28T01:00:00Z", "writeResults": [{}]})
    receipt = client.submit_roster(session, data)
    assert receipt["receipt_id"] and receipt["teacher_uid"] == "uidT"
    header = commits[0][0]["update"]["fields"]
    assert header["summary"]["mapValue"]["fields"]["class_code"]["stringValue"] == "SELF"
    assert len(commits[0]) == 2  # header + 1 lesson


def test_roster_submissions_hydrates_like_old_channel(monkeypatch):
    client = fc.FirebaseClassroom({"project_id": fc.PROJECT_ID, "api_key": "fake"})
    session = fc.ClassroomSession("uidT", "fake", "fake", time.time() + 3600)
    base = "projects/p/databases/(default)/documents"
    page = {"documents": [{
        "name": f"{base}/rosters/uidT/submissions/doc1",
        "fields": {"owner_uid": fc._value("uidS"),
                   "summary": fc._value({"schema_version": 1, "class_code": "SELF",
                                         "student_code": "uidS", "assignment_id": "QA-01",
                                         "diagnostics": {"pre_test": {"score": None, "attempt_count": 0},
                                                         "post_test": {"score": None, "attempt_count": 0}},
                                         "journal_count": 0}),
                   "lesson_count": fc._value(1),
                   "received_at": fc._value("2026-10-28T01:00:00Z")},
    }]}
    lessons_page = {"documents": [{
        "name": f"{base}/rosters/uidT/submissions/doc1/lessons/0",
        "fields": {"index": fc._value(0),
                   "lesson": fc._value({"lesson_id": "m1", "latest_score": 0.85,
                                        "best_score": 0.85, "attempt_count": 1})},
    }]}
    pages = [page, lessons_page]

    monkeypatch.setattr(fc, "_json_request", lambda *a, **k: pages.pop(0))
    docs = client.roster_submissions(session)
    assert docs[0]["summary"]["lesson_results"][0]["latest_score"] == 0.85


def test_online_limit_matches_existing_package_limit():
    assert cs.MAX_ONLINE_LESSONS == cp.MAX_LESSONS


def test_online_panel_disabled_by_default_keeps_json_path():
    at = AppTest.from_string(
        "import classroom_ui\nclassroom_ui.render_online_classroom({}, None, config={})",
        default_timeout=30,
    ).run()
    assert not at.exception and not at.error
    assert not at.button
    assert any("JSON" in c.value for c in at.caption)


def test_online_login_boots_without_secrets_or_network():
    at = AppTest.from_string(
        "from classroom_ui import render_online_classroom\n"
        "render_online_classroom({},None,config={'enabled':True,'project_id':'quant-app-classroom-20261026','api_key':'fake'})",
        default_timeout=30,
    ).run()
    assert not at.exception and not at.error
    assert at.get("form") and len(at.text_input) == 3


def test_network_errors_do_not_echo_password_or_token(monkeypatch):
    from urllib.error import URLError
    monkeypatch.setattr(fc, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("SECRET_SENTINEL")))
    with pytest.raises(fc.ClassroomConnectionError) as err:
        fc._json_request("https://firebase.example", {"password": "SECRET_SENTINEL"}, token="SECRET_SENTINEL")
    assert "SECRET_SENTINEL" not in str(err.value)


def test_student_panel_requires_consent_then_shows_real_receipt(monkeypatch):
    def save(_client, _session, data):
        return {"receipt_id": "a" * 64, "received_at": "2026-10-26T12:00:00Z", "class_code": data["class_code"]}
    monkeypatch.setattr(fc.FirebaseClassroom, "submit", save)
    at = AppTest.from_string(
        "import time\nimport streamlit as st\nimport classroom_ui as ui\n"
        "import classroom_packages as cp\nimport progress_profile as pp\n"
        "from firebase_classroom import ClassroomSession\n"
        "if 'classroom_session' not in st.session_state:\n"
        " st.session_state.update(classroom_session=ClassroomSession('fake','fake','fake',time.time()+3600),"
        "classroom_role='student',classroom_login_class='QA-LOP',classroom_login_code='HS-QA1')\n"
        "assignment=cp.make_assignment(assignment_id='QA-01',title='QA',instructions='QA',lesson_ids=['m1'])\n"
        "ui.render_online_classroom(pp.empty_profile(),assignment,config={'enabled':True,"
        "'project_id':'quant-app-classroom-20261026','api_key':'fake'})",
        default_timeout=30,
    ).run()
    assert not at.exception and not at.error
    assert at.button[1].disabled
    at.checkbox[0].check().run()
    at.button[1].click().run()
    assert not at.exception and not at.error
    assert any("Đã lưu bài" in item.value for item in at.success)
    assert at.code[0].value == "a" * 64
