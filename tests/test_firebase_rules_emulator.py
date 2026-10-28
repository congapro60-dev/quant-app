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


def test_rules_self_service_registration_roster_and_denials(sandbox):
    client, _teacher = sandbox
    # GV tự đăng ký; tên vào danh bạ công khai cho HS chọn.
    t1 = client.register_teacher("giao-vien-qa", "mat-khau-gv-1", "Cô QA")
    prof_t = client.self_profile(t1)
    assert prof_t["kind"] == "teacher" and prof_t["display_name"] == "Cô QA"
    assert prof_t.get("created_at")
    # Trùng tên đăng nhập: Auth chặn, không ghi đè tài khoản cũ.
    with pytest.raises(fc.ClassroomConnectionError):
        client.register_teacher("giao-vien-qa", "mat-khau-gv-2", "Cô QA Hai")
    # HS tự đăng ký; khối + tên lớp chuẩn hoá trước khi lên cloud.
    s1 = client.register_student("hs-qa-1", "mat-khau-hs-1", "Nguyễn An", "11", "11a1")
    prof1 = client.self_profile(s1)
    assert (prof1["kind"], prof1["block"], prof1["class_name"]) == ("student", "11", "11A1")
    assert prof1["teacher_uid"] is None
    # Mật khẩu dưới 8 ký tự bị chặn trước khi gọi mạng.
    with pytest.raises(cp.ClassroomPackageError):
        client.register_student("hs-qa-2", "ngan", "Trần Bình", "11", "11A1")
    s2 = client.register_student("hs-qa-2", "mat-khau-hs-2", "Trần Bình", "11", "11A1")
    # Danh bạ GV hiển thị cho HS; vào danh sách = 1 commit nguyên tử.
    assert {t["display_name"] for t in client.list_teachers(s1)} == {"Cô QA"}
    client.join_teacher(s1, t1.uid)
    client.join_teacher(s2, t1.uid)
    rows = client.roster(t1)
    assert [(r["display_name"], r["class_name"]) for r in rows] == [
        ("Nguyễn An", "11A1"), ("Trần Bình", "11A1")]
    # HS tự rút; con trỏ về rỗng, GV không còn thấy HS đó.
    client.leave_teacher(s1)
    assert [r["display_name"] for r in client.roster(t1)] == ["Trần Bình"]
    # HS đổi GV trực tiếp; GV cũ mất HS, GV mới thấy.
    t2 = client.register_teacher("giao-vien-qb", "mat-khau-gv-3", "Thầy QB")
    client.join_teacher(s2, t2.uid)
    assert client.roster(t1) == []
    assert [r["display_name"] for r in client.roster(t2)] == ["Trần Bình"]
    # GV khác không xóa được HS trong danh sách của GV này (403):
    # t1 cố tình xóa trực tiếp tài liệu trong roster của t2
    cross_delete = [client._delete_write(f"rosters/{t2.uid}/members/{s2.uid}")]
    with pytest.raises(fc.ClassroomConnectionError):
        client._commit(t1, cross_delete)
    # GV xóa HS khỏi danh sách của chính mình (hợp lệ).
    client.remove_student(t2, s2.uid)
    assert client.roster(t2) == []
    # Rules chặn HS tự đặt teacher_uid trỏ về chính UID của mình (tự làm GV hướng dẫn).
    self_teacher_write = [client._make_write(
        f"student_state/{s2.uid}",
        {"display_name": "Trần Bình", "block": "11", "class_name": "11A1",
         "teacher_uid": s2.uid}, timestamp=True, timestamp_field="updated_at")]
    with pytest.raises(fc.ClassroomConnectionError):
        client._commit(s2, self_teacher_write)
    # Rules chặn dữ liệu sai schema: khối không hợp lệ, tên lớp quá dài.
    for bad in [{"display_name": "X", "block": "9", "class_name": "11A1"},
                {"display_name": "X", "block": "11", "class_name": "A" * 17}]:
        writes = [client._make_write(f"rosters/{t2.uid}/members/{s2.uid}", bad, create=True,
                                     timestamp=True, timestamp_field="joined_at")]
        with pytest.raises(fc.ClassroomConnectionError):
            client._commit(s2, writes)
    # Tự chọn chính mình làm GV bị rules chặn (tuid == suid).
    writes = [client._make_write(f"rosters/{s2.uid}/members/{s2.uid}",
                                 {"display_name": "X", "block": "11", "class_name": "11A1"},
                                 create=True, timestamp=True, timestamp_field="joined_at")]
    with pytest.raises(fc.ClassroomConnectionError):
        client._commit(s2, writes)


def test_rules_roster_submissions_flow_and_denials(sandbox):
    client, _teacher = sandbox
    t1 = client.register_teacher("giao-vien-nop", "mat-khau-gv-1", "Cô Nộp")
    s1 = client.register_student("hs-nop-1", "mat-khau-hs-1", "Nguyễn An", "11", "11A1")
    client.join_teacher(s1, t1.uid)
    # HS nộp thẳng vào danh sách: mã lớp SELF, mã HS là uid của chính em.
    assignment = cp.make_assignment(assignment_id="QA-02", title="QA nộp",
                                    instructions="Giả lập", lesson_ids=["m1"])
    profile = pp.empty_profile()
    profile["lesson_scores"]["m1"] = 0.85
    data = cs.build_roster_submission(profile, assignment, s1.uid)
    receipt = client.submit_roster(s1, data)
    assert receipt["teacher_uid"] == t1.uid
    # GV đọc lại bài nộp của học sinh trong danh sách mình.
    docs = client.roster_submissions(t1)
    assert len(docs) == 1
    hydrated = docs[0]
    assert hydrated["summary"]["student_code"] == s1.uid
    assert hydrated["summary"]["lesson_results"][0]["latest_score"] == 0.85
    # Nộp lại cùng bài là ghi đè có kiểm soát (cùng assignment + cùng người gửi).
    assert client.submit_roster(s1, data)["receipt_id"] == receipt["receipt_id"]
    # HS chưa vào danh sách thì không nộp được.
    s2 = client.register_student("hs-nop-2", "mat-khau-hs-2", "Trần Bình", "11", "11A1")
    data2 = cs.build_roster_submission(pp.empty_profile(), assignment, s2.uid)
    with pytest.raises(fc.ClassroomConnectionError):
        client.submit_roster(s2, data2)
    # GV thứ hai không đọc được bài nộp trong danh sách của GV này.
    t2 = client.register_teacher("giao-vien-nop-b", "mat-khau-gv-4", "Thầy Nộp B")
    with pytest.raises(fc.ClassroomConnectionError):
        client.get(t2, f"rosters/{t1.uid}/submissions/{receipt['receipt_id']}")
    # HS tự sửa student_code thành uid người khác bị rules chặn.
    tampered = {**data, "student_code": s2.uid}
    bad = [client._make_write(f"rosters/{t1.uid}/submissions/fake{secrets.token_hex(4)}",
                              {"owner_uid": s1.uid, "summary": tampered,
                               "lesson_count": 1}, timestamp=True)]
    with pytest.raises(fc.ClassroomConnectionError):
        client._commit(s1, bad)
    # Rút khỏi danh sách rồi nộp: bị chặn ngay ở rules (không còn là thành viên).
    client.leave_teacher(s1)
    orphan = [client._make_write(f"rosters/{t1.uid}/submissions/orphan{secrets.token_hex(4)}",
                                 {"owner_uid": s1.uid, "summary": {k: v for k, v in data.items()
                                                                   if k != "lesson_results"},
                                  "lesson_count": 1}, timestamp=True)]
    with pytest.raises(fc.ClassroomConnectionError):
        client._commit(s1, orphan)
