"""Tài khoản tự đăng ký: HS/GV tự tạo tài khoản, chọn GV, quản lý danh sách.

Độc lập với kênh nộp bài "mã cấp sẵn" trong ``classroom_ui``. Quy tắc AppTest:
mọi lời gọi mạng chỉ chạy khi người dùng bấm nút hoặc gửi form — render tự
nhiên không gọi mạng, nên AppTest với key giả vẫn chạy được.
"""
import streamlit as st

import classroom_packages as cp
from firebase_classroom import (
    FirebaseClassroom,
    ClassroomConnectionError,
    ClassroomNotFoundError,
)


def _logout():
    for key in ("self_session", "self_profile", "self_teachers", "self_roster",
                "self_status", "self_pick"):
        st.session_state.pop(key, None)


def render_self_service(config=None):
    if config is None:
        try:
            config = dict(st.secrets.get("classroom_firebase", {}))
        except Exception:
            config = {}
    if config.get("enabled") is not True:
        st.caption("Tự đăng ký tài khoản chưa bật. Em vẫn dùng mã tài khoản do giáo viên cấp ở phần nộp bài bên dưới.")
        return
    st.subheader("Tài khoản tự đăng ký — học sinh và giáo viên")
    st.caption("Tự chọn tên đăng nhập và mật khẩu, không cần email. Một người có thể mở nhiều tài khoản. "
               "Chưa có khôi phục mật khẩu qua email: quên mật khẩu thì đăng ký tài khoản mới rồi chọn lại "
               "giáo viên, giáo viên xóa bản cũ trong danh sách.")
    try:
        client = FirebaseClassroom(config)
    except Exception:
        st.warning("Kênh tài khoản đang được cấu hình. Hãy quay lại sau.")
        return
    if "self_session" not in st.session_state:
        _entry(client)
        return
    session = st.session_state.self_session
    st.button("Đăng xuất tài khoản tự đăng ký", on_click=_logout)
    profile = st.session_state.get("self_profile") or {}
    try:
        if profile.get("kind") == "student":
            _student_panel(client, session, profile)
        elif profile.get("kind") == "teacher":
            _teacher_panel(client, session)
        else:
            st.warning("Tài khoản này chưa có hồ sơ tự đăng ký. Hãy đăng ký lại bằng tên khác.")
    except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
        st.warning(str(exc))


def _entry(client, on_login=None):
    login_tab, register_tab = st.tabs(["Đăng nhập", "Đăng ký tài khoản mới"])
    with login_tab:
        with st.form("self_login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            login = st.form_submit_button("Đăng nhập", type="primary")
        if login:
            try:
                session = client.login_self(username, password)
                profile = client.self_profile(session)
                st.session_state.update(self_session=session, self_profile=profile)
                if on_login is not None:
                    on_login(session, profile, username)
                st.rerun()
            except (ClassroomConnectionError, cp.ClassroomPackageError):
                st.warning("Chưa đăng nhập được. Kiểm tra tên đăng nhập và mật khẩu.")
    with register_tab:
        student_tab, teacher_tab = st.tabs(["Em là học sinh", "Em là giáo viên"])
        with student_tab:
            _register_student(client, on_login)
        with teacher_tab:
            _register_teacher(client, on_login)


def _register_student(client, on_login=None):
    st.caption("Sau khi đăng ký, em chọn giáo viên hướng dẫn; tên hiển thị và lớp của em sẽ hiện "
               "trong danh sách của giáo viên đó.")
    st.info("🔒 **Quyền riêng tư:** Em có thể dùng biệt danh hoặc tên viết tắt nếu không muốn để lộ họ tên thật. "
            "Thông tin lớp và tên chỉ chia sẻ với giáo viên em chọn.")
    with st.form("self_register_student"):
        username = st.text_input("Tên đăng nhập (4-32 ký tự, không khoảng trắng)")
        display = st.text_input("Tên hiển thị (hiện trong danh sách lớp)")
        cols = st.columns(2)
        block = cols[0].selectbox("Khối", ["10", "11", "12"])
        class_name = cols[1].text_input("Tên lớp (ví dụ 11A1)")
        password = st.text_input("Mật khẩu (tối thiểu 8 ký tự)", type="password")
        submit = st.form_submit_button("Đăng ký học sinh", type="primary")
    if submit:
        try:
            session = client.register_student(username, password, display, block, class_name)
            profile = client.self_profile(session)
            st.session_state.update(self_session=session, self_profile=profile)
            if on_login is not None:
                on_login(session, profile, username)
            st.rerun()
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))


def _register_teacher(client, on_login=None):
    st.caption("Sau khi đăng ký, tên của thầy/cô sẽ hiện ngay trong danh sách giáo viên "
               "cho học sinh chọn.")
    with st.form("self_register_teacher"):
        username = st.text_input("Tên đăng nhập (4-32 ký tự, không khoảng trắng)",
                                 key="self_teacher_username")
        display = st.text_input("Tên hiển thị (học sinh sẽ thấy)", key="self_teacher_display")
        password = st.text_input("Mật khẩu (tối thiểu 8 ký tự)", type="password",
                                 key="self_teacher_password")
        submit = st.form_submit_button("Đăng ký giáo viên", type="primary")
    if submit:
        try:
            session = client.register_teacher(username, password, display)
            profile = client.self_profile(session)
            st.session_state.update(self_session=session, self_profile=profile)
            if on_login is not None:
                on_login(session, profile, username)
            st.rerun()
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))


def _member_ok(client, session, tuid):
    """Kiểm tra học sinh còn trong danh sách GV không.
    
    Chỉ trả về False khi nhận đúng mã 404 (document không tồn tại).
    Lỗi mạng / lỗi máy chủ sẽ ném ra để UI báo đúng trạng thái kết nối.
    """
    try:
        client.get(session, f"rosters/{tuid}/members/{session.uid}")
        return True
    except ClassroomNotFoundError:
        return False


def _student_panel(client, session, profile):
    st.write(f"Xin chào **{profile.get('display_name', '')}** — khối {profile.get('block')}, "
             f"lớp {profile.get('class_name')}.")
    if st.button("Làm mới trạng thái", key="self_student_refresh"):
        try:
            profile = client.self_profile(session)
            st.session_state.self_profile = profile
            tuid = profile.get("teacher_uid")
            st.session_state.self_status = {
                "tuid": tuid if isinstance(tuid, str) else None,
                "member_ok": _member_ok(client, session, tuid) if isinstance(tuid, str) else None,
            }
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))
    status = st.session_state.get("self_status") or {}
    if status.get("tuid") and status.get("member_ok") is False:
        st.warning("Giáo viên đã xóa em khỏi danh sách (hoặc danh sách không còn). "
                   "Chọn lại giáo viên bên dưới nhé.")
    if st.button("Chọn giáo viên hướng dẫn / đổi giáo viên", key="self_student_pick"):
        st.session_state.self_pick = not st.session_state.get("self_pick", False)
    if st.session_state.get("self_pick"):
        _pick_teacher(client, session)
    tuid = profile.get("teacher_uid")
    if isinstance(tuid, str) and tuid and st.button("Rút khỏi danh sách giáo viên hiện tại",
                                                    key="self_student_leave"):
        try:
            client.leave_teacher(session)
            st.session_state.self_profile = client.self_profile(session)
            st.session_state.pop("self_status", None)
            st.success("Đã rút khỏi danh sách. Em có thể chọn lại giáo viên bất cứ lúc nào.")
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))


def _pick_teacher(client, session):
    if st.button("Tải danh sách giáo viên", key="self_teacher_reload"):
        st.session_state.self_teachers = client.list_teachers(session)
    teachers = st.session_state.get("self_teachers") or []
    if not teachers:
        st.caption("Bấm \"Tải danh sách giáo viên\" để xem các thầy cô đã đăng ký.")
        return
    options = {t["uid"]: f"{t.get('display_name', '(không tên)')} (mã: {t['uid'][:8]})" for t in teachers}
    chosen = st.selectbox("Giáo viên hướng dẫn", list(options),
                          format_func=lambda uid: options[uid], key="self_teacher_choice")
    if st.button("Vào danh sách của giáo viên này", type="primary", key="self_join"):
        try:
            client.join_teacher(session, chosen)
            st.session_state.self_profile = client.self_profile(session)
            st.session_state.pop("self_teachers", None)
            st.session_state.pop("self_status", None)
            st.success("Đã vào danh sách của giáo viên. Chúc em học tốt!")
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))


def _teacher_panel(client, session):
    st.caption("Danh sách gồm học sinh đã tự chọn thầy/cô, xếp theo khối rồi tên lớp. "
               "Xóa một học sinh chỉ đưa em ấy ra khỏi danh sách này; em ấy vẫn có thể "
               "chọn lại hoặc chọn giáo viên khác.")
    if st.button("Tải danh sách học sinh", type="primary", key="self_roster_reload"):
        st.session_state.self_roster = client.roster(session)
    rows = st.session_state.get("self_roster")
    if rows is None:
        st.caption("Bấm tải để xem học sinh đã chọn thầy/cô.")
        return
    if not rows:
        st.info("Chưa có học sinh nào chọn thầy/cô.")
        return
    st.dataframe([{"Họ và tên": r.get("display_name", ""), "Khối": r.get("block", ""),
                   "Lớp": r.get("class_name", ""),
                   "Ngày vào": str(r.get("joined_at", ""))[:16].replace("T", " ")}
                  for r in rows], width="stretch")
    chosen = st.selectbox("Học sinh cần xóa", [r["uid"] for r in rows],
                          format_func=lambda uid: next(
                              (f"{r.get('display_name', '')} — khối {r.get('block', '')} "
                               f"lớp {r.get('class_name', '')}" for r in rows if r["uid"] == uid),
                              uid),
                          key="self_remove_choice")
    if st.button("Xóa khỏi danh sách", key="self_remove"):
        try:
            client.remove_student(session, chosen)
            st.session_state.self_roster = client.roster(session)
            st.success("Đã xóa khỏi danh sách. Học sinh sẽ thấy cảnh báo và có thể chọn lại.")
        except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
            st.warning(str(exc))


# Tên công khai cho nút tài khoản toàn cục (``account_ui``) dùng lại: một nguồn
# duy nhất cho giao diện đăng nhập/đăng ký và hai bảng quản lý. Tab "Gói lớp học"
# không còn mount khối này nữa; ``render_self_service`` giữ lại cho test cũ.
entry = _entry
student_panel = _student_panel
teacher_panel = _teacher_panel
