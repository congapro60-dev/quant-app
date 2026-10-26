"""Bounded live canary with fabricated pupils; no real student records."""
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import firebase_classroom as fc
import classroom_packages as cp
import classroom_submit as cs
import progress_profile as pp
from provision_classroom import provision_teacher, enable_teacher


def main():
    output = Path.home() / ".quant-app-classroom"
    config = json.loads((output / "config.json").read_text())
    client = fc.FirebaseClassroom(config)
    teachers = []
    for code in ("GV-QA01", "GV-QA02"):
        record = provision_teacher(config, code, output)
        enable_teacher(record)
        teachers.append(client.login("teacher", "", code, record["password"]))
    t1, t2 = teachers
    class_code = client.create_class(t1, "QA-" + secrets.token_hex(4).upper())
    pupils = [client.issue_student(t1, class_code, code) for code in ("HS-QA01", "HS-QA02")]
    students = [client.login("student", class_code, p["student_code"], p["password"]) for p in pupils]
    assignment = cp.make_assignment(assignment_id="QA-COURSE", title="Kiểm thử giả lập", instructions="Canary",
                                    lesson_ids=["m1_tien_ngan_sach"])
    profile = pp.empty_profile()
    pp.record_lesson(profile, "m1_tien_ngan_sach", 80)
    summary = cs.build_submission(profile, assignment, class_code, "HS-QA01")
    students[0].expires_at = 0  # Exercise actual securetoken refresh, not only the emulator.
    receipt = cs.submit(summary, client=client, session=students[0])
    docs = client.submissions(t1, class_code)
    assert len(docs) == 1 and docs[0]["summary"] == summary
    for session in (students[1], t2):
        try:
            client.get(session, f"classes/{class_code}/submissions/{receipt['receipt_id']}")
        except fc.ClassroomConnectionError:
            pass
        else:
            raise AssertionError("Cross-account read unexpectedly allowed")
    try:
        client._write(students[1], f"classes/{class_code}/submissions/{receipt['receipt_id']}",
                      {"owner_uid": students[1].uid, "summary": {**summary, "student_code": "HS-QA02"}}, timestamp=True)
    except fc.ClassroomConnectionError:
        pass
    else:
        raise AssertionError("Cross-student overwrite unexpectedly allowed")
    evidence = {"class_code": class_code, "student_a_uid": students[0].uid, "student_b_uid": students[1].uid,
                "teacher_uid": t1.uid, "receipt": receipt,
                "checks": ["write/read own", "teacher reads own class", "B read A denied",
                           "other teacher denied", "B overwrite A denied"]}
    (output / "live-canary.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print("Live canary PASS. Evidence: " + str(output / "live-canary.json"))


if __name__ == "__main__":
    main()
