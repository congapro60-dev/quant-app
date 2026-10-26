"""Authenticated submission panel, inside the existing classroom tab."""
import csv
import io
import json
import secrets
import hashlib

import streamlit as st

import classroom_packages as cp
import classroom_submit as cs
from firebase_classroom import FirebaseClassroom, ClassroomConnectionError, PROJECT_ID


def _logout():
    for key in ("classroom_session", "classroom_role", "classroom_login_class",
                "classroom_login_code", "classroom_receipt", "classroom_issued", "classroom_rows"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("classroom_consent_"):
            st.session_state.pop(key, None)


def render_online_classroom(profile, assignment, *, config=None):
    if config is None:
        try:
            config = dict(st.secrets.get("classroom_firebase", {}))
        except Exception:
            config = {}
    if config.get("enabled") is not True:
        st.caption("Nộp trực tuyến chưa bật. Em vẫn tải và gửi gói JSON như bình thường.")
        return
    st.subheader("Nộp bài trực tuyến cho giáo viên")
    st.caption("Dữ liệu tổng hợp được gửi ra ngoài máy học sinh tới Firebase. Chỉ gửi mã lớp/HS, "
               "điểm, số lần làm và số mục nhật ký; không gửi nội dung nhật ký hay danh mục. "
               "Bản học vẫn tự lưu tại trình duyệt; JSON là phương án dự phòng.")
    st.caption("Điểm do hồ sơ học trên máy cung cấp, chưa phải kết quả được giáo viên xác minh.")
    try:
        client = FirebaseClassroom(config)
    except cs.SubmissionNotConfiguredError:
        st.warning("Kênh nộp bài đang được cấu hình. Hãy giữ bản JSON.")
        return
    if "classroom_session" not in st.session_state:
        with st.form("classroom_login_form"):
            role = st.radio("Đăng nhập với vai trò", ["student", "teacher"],
                            format_func=lambda r: "Học sinh" if r == "student" else "Giáo viên")
            class_code = st.text_input("Mã lớp (học sinh)")
            code = st.text_input("Mã tài khoản do giáo viên/chủ project cấp")
            password = st.text_input("Mật khẩu được cấp", type="password")
            login = st.form_submit_button("Đăng nhập kênh nộp bài", type="primary")
        if login:
            try:
                session = client.login(role, class_code.strip(), code.strip(), password)
                if role == "teacher" and not client.is_teacher(session):
                    raise ClassroomConnectionError("Tài khoản chưa được chủ project cấp quyền giáo viên.")
                if role == "student":
                    member = client.get(session, f"classes/{cp._id(class_code.strip(),'class_code').upper()}/students/{cp._student_code(code.strip()).upper()}")
                    if member["uid"] != session.uid:
                        raise ClassroomConnectionError("Mã học sinh không thuộc lớp này.")
                st.session_state.update(classroom_session=session, classroom_role=role,
                                        classroom_login_class=class_code.strip().upper(),
                                        classroom_login_code=code.strip().upper())
                st.rerun()
            except (ClassroomConnectionError, cp.ClassroomPackageError):
                st.warning("Chưa đăng nhập được. Kiểm tra mã lớp, mã tài khoản và mật khẩu được cấp.")
        return
    session = st.session_state.classroom_session
    st.button("Đăng xuất kênh nộp bài", on_click=_logout)
    try:
        if st.session_state.classroom_role == "teacher":
            _teacher(client, session)
        else:
            _student(client, session, profile, assignment)
    except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
        st.warning(str(exc))


def _student(client, session, profile, assignment):
    if assignment is None:
        st.info("Nạp gói giao bài giáo viên gửi ở phần bên dưới trước khi nộp.")
        return
    summary = cs.build_submission(profile, assignment, st.session_state.classroom_login_class,
                                  st.session_state.classroom_login_code)
    st.write(f"Bài giao: **{assignment['title']}** · {len(summary['lesson_results'])} mô-đun")
    with st.expander("Xem dữ liệu sẽ gửi"):
        st.json(summary)
    signature = hashlib.sha256(json.dumps(summary,sort_keys=True).encode()).hexdigest()
    consent = st.checkbox("Em đồng ý gửi bản tổng hợp đang hiển thị cho giáo viên của lớp.", key=f"classroom_consent_{signature}")
    if st.button("Nộp bài lên Firebase", disabled=not consent, type="primary"):
        st.session_state.pop("classroom_receipt", None)
        with st.spinner("Đang gửi và chờ xác nhận lưu..."):
            receipt = cs.submit(summary, client=client, session=session)
        st.session_state.classroom_receipt = {"signature": signature, "receipt": receipt}
    saved = st.session_state.get("classroom_receipt", {})
    receipt = saved.get("receipt")
    if receipt and saved.get("signature") == signature:
        st.success(f"Đã lưu bài · {receipt['received_at']}")
        st.code(receipt["receipt_id"], language=None)
        st.caption("Biên nhận xác nhận đã lưu dữ liệu, không xác nhận điểm đã được giáo viên chấm.")


def _teacher(client, session):
    st.caption("Chỉ những lớp do tài khoản này sở hữu được hiển thị.")
    with st.form("classroom_new_class"):
        class_code = st.text_input("Mã lớp mới", value="LOP-" + session.uid[:6].upper())
        if st.form_submit_button("Tạo lớp"):
            client.create_class(session, class_code.strip())
            st.success("Đã tạo lớp.")
    classes = client.classes(session)
    if not classes:
        st.info("Tạo lớp để cấp tài khoản học sinh và nhận bài.")
        return
    code = st.selectbox("Lớp của tôi", [c["class_code"] for c in classes], key="classroom_selected_class")
    with st.form("classroom_new_student"):
        st.caption("Cấp một mã ngẫu nhiên và mật khẩu riêng. Tải tệp ngay rồi phát riêng cho học sinh.")
        if st.form_submit_button("Cấp tài khoản học sinh"):
            issued = client.issue_student(session, code, "HS-" + secrets.token_hex(6).upper())
            st.session_state.classroom_issued = issued
    issued = st.session_state.get("classroom_issued")
    if issued and issued["class_code"] == code:
        st.download_button("Tải thông tin tài khoản vừa cấp (.json)",
                           json.dumps(issued, ensure_ascii=False).encode(),
                           file_name=f"tai_khoan_{issued['student_code']}.json", mime="application/json")
        st.caption("Mật khẩu không lưu trong hồ sơ học. Nếu tệp bị thất lạc, liên hệ chủ project để cấp lại.")
    if st.button("Tải danh sách bài nộp", type="primary"):
        st.session_state.classroom_rows = {"class_code": code, "items": client.submissions(session, code)}
    loaded = st.session_state.get("classroom_rows", {})
    if loaded.get("class_code") == code:
        docs = loaded["items"]
        rows = [{"Mã học sinh": d["summary"]["student_code"], "Bài giao": d["summary"]["assignment_id"],
                 "Số mô-đun": len(d["summary"]["lesson_results"]), "Thời điểm nộp": d["received_at"]}
                for d in docs]
        st.dataframe(rows, width="stretch")
        if docs:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            st.download_button("Xuất tổng hợp (CSV)", output.getvalue().encode("utf-8-sig"),
                               file_name=f"tong_hop_{code}.csv", mime="text/csv")
            st.download_button("Xuất đầy đủ điểm bài nộp (JSON)", json.dumps(docs,ensure_ascii=False).encode(),
                               file_name=f"bai_nop_{code}.json", mime="application/json")
            chosen = st.selectbox("Đọc bài nộp", range(len(docs)),
                                  format_func=lambda i: f"{rows[i]['Mã học sinh']} · {rows[i]['Bài giao']}")
            st.json(docs[chosen])
