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
