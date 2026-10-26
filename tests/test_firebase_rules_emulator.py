"""Real Rules integration; explicitly run through firebase emulators:exec."""
import os
import time
import secrets
import json
from copy import deepcopy

import pytest

import firebase_classroom as fc
import classroom_submit as cs
import classroom_packages as cp
import progress_profile as pp

pytestmark = pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="Requires Firebase Emulator Suite")


@pytest.fixture
def sandbox(monkeypatch):
    real = fc._json_request
    firestore = os.environ["FIRESTORE_EMULATOR_HOST"]
    auth = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    assert firestore.startswith("127.0.0.1:") and auth.startswith("127.0.0.1:")

    def route(url, *args, **kwargs):
        url = url.replace("https://firestore.googleapis.com/v1/projects/" + fc.PROJECT_ID,
                          f"http://{firestore}/v1/projects/demo-quant-app")
        url = url.replace("https://identitytoolkit.googleapis.com/", f"http://{auth}/identitytoolkit.googleapis.com/")
        url = url.replace("https://securetoken.googleapis.com/", f"http://{auth}/securetoken.googleapis.com/")
        if args:
            args = (json.loads(json.dumps(args[0]).replace("projects/" + fc.PROJECT_ID, "projects/demo-quant-app")),) + args[1:]
        return real(url, *args, **kwargs)

    monkeypatch.setattr(fc, "_json_request", route)
    client = fc.FirebaseClassroom({"project_id": fc.PROJECT_ID, "api_key": "emulator"})
    admin_base = f"http://{firestore}/v1/projects/demo-quant-app/databases/(default)/documents"

    def new_teacher():
        code = "GV-" + secrets.token_hex(5)
        password = secrets.token_urlsafe(20)
        data = client._auth("signUp", {"email": fc.account_email("teacher", "", code),
                                      "password": password, "returnSecureToken": True})
        real(f"{admin_base}/teachers/{data['localId']}", {"fields": {"enabled": {"booleanValue": True}}},
             token="owner", method="PATCH")
        return client.login("teacher", "", code, password)

    return client, new_teacher


def test_rules_full_teaching_flow_and_cross_account_denials(sandbox):
    client, teacher = sandbox
    t1, t2 = teacher(), teacher()
    code = client.create_class(t1, "QA-" + secrets.token_hex(4).upper())
    assert client.classes(t1)
    assert not any(c["class_code"] == code for c in client.classes(t2))
    a = client.issue_student(t1, code, "HS-A1")
    b = client.issue_student(t1, code, "HS-B2")
    sa = client.login("student", code, a["student_code"], a["password"])
    sb = client.login("student", code, b["student_code"], b["password"])
    assignment = cp.make_assignment(assignment_id="QA-01", title="QA", instructions="Dữ liệu giả",
                                    lesson_ids=[f"m{i}" for i in range(1, cs.MAX_ONLINE_LESSONS + 1)])
    data = cs.build_submission(pp.empty_profile(), assignment, code, "HS-A1")
    for row in data['lesson_results']:
        row.update(latest_score=100, best_score=100, attempt_count=100)
    receipt = cs.submit(data, client=client, session=sa)
    assert receipt["received_at"]
    assert len(client.submissions(t1, code)) == 1
    sa.expires_at = 0
    assert client.get(sa, f"classes/{code}/students/HS-A1")["uid"] == sa.uid
    assert client.get(sa, f"classes/{code}/submissions/{receipt['receipt_id']}")["summary"] == data
    lesson_path = f"classes/{code}/submissions/{receipt['receipt_id']}/lessons/0"
    for bad in [{**data['lesson_results'][0], 'email': 'fake@example.com'},
                {**data['lesson_results'][0], 'latest_score': 'fake@example.com'},
                {**data['lesson_results'][0], 'attempt_count': True}]:
        with pytest.raises(fc.ClassroomConnectionError):
            client._write(sa, lesson_path, {'index': 0, 'lesson': bad})
    with pytest.raises(fc.ClassroomConnectionError):
        client.get(sb, lesson_path)
    with pytest.raises(fc.ClassroomConnectionError):
        client._write(sb, lesson_path, {'index': 0, 'lesson': data['lesson_results'][0]})
    # Every denial is enforced by the real Rules interpreter, not a mock.
    for user, path in [(sb, f"classes/{code}/submissions/{receipt['receipt_id']}"),
                       (t2, f"classes/{code}/submissions/{receipt['receipt_id']}"),
                       (sb, f"classes/{code}/students/HS-A1")]:
        with pytest.raises(fc.ClassroomConnectionError):
            client.get(user, path)
    with pytest.raises(fc.ClassroomConnectionError):
        client.submissions(sb, code)
    with pytest.raises(fc.ClassroomConnectionError):
        client.submissions(t2, code)
    with pytest.raises(fc.ClassroomConnectionError):
        client._write(sb, f"classes/{code}/students/HS-A1", {"uid": sb.uid, "student_code": "HS-A1"})
    with pytest.raises(fc.ClassroomConnectionError):
        client._write(sb, f"teachers/{sb.uid}", {"enabled": True})
    with pytest.raises(fc.ClassroomConnectionError):
        client.create_class(sa, "QA-HIJACK")
    with pytest.raises(fc.ClassroomConnectionError):
        client._write(t2, f"classes/{code}", {"owner_uid": t2.uid, "class_code": code})
    # Direct requests bypass Python validation to test Rules schema validation.
    for bad in [{**data, "api_key": "FAKE"},
                {**data, "lesson_results": [{**data["lesson_results"][0], "latest_score": "student@example.com"}]}]:
        with pytest.raises(fc.ClassroomConnectionError):
            client._write(sa, f"classes/{code}/submissions/invalid", {"owner_uid": sa.uid, "summary": bad}, timestamp=True)
    with pytest.raises(fc.ClassroomConnectionError):
        client._write(sb, f"classes/{code}/submissions/{receipt['receipt_id']}",
                      {"owner_uid": sb.uid, "summary": {**data, "student_code": "HS-B2"}}, timestamp=True)
    # Legitimate repeat submission is idempotent; no second receipt document.
    assert cs.submit(data, client=client, session=sa)["receipt_id"] == receipt["receipt_id"]
    assert len(client.submissions(t1, code)) == 1
