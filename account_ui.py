"""Nút tài khoản góc phải trên, dùng chung cho mọi màn hình.

Ba việc của module này:

1. **Nút tài khoản** (``render_account_bar``): một hộp cố định ở góc phải trên,
   luôn hiện, cho biết ai đang đăng nhập. Bấm vào thì hiện đúng tuỳ chọn theo
   vai trò — khách thì form đăng nhập/đăng ký, học sinh thì lối vào trang học
   sinh, giáo viên thì lối vào trang giáo viên.
2. **Trang riêng** (``render_account_page``): ``app.py`` gọi trước khi vẽ nội
   dung chính; có yêu cầu trang thì vẽ trang tài khoản rồi dừng, không dựng
   các tab của ứng dụng.
3. **Nhớ đăng nhập** (``bootstrap``): đọc dấu trong localStorage rồi tự đổi lấy
   phiên mới, nên mở tab khác hay tải lại trang vẫn còn đăng nhập.

Giao diện đăng nhập/đăng ký và hai bảng quản lý nằm ở ``classroom_self_ui`` —
module này chỉ bọc lấy, không viết lại, để chỉ có một nguồn duy nhất.
"""

from __future__ import annotations

import streamlit as st

import account_store as store
import classroom_packages as cp
import classroom_self_ui as panels
from firebase_classroom import ClassroomConnectionError, FirebaseClassroom

BAR_KEY = "qa_account_bar"
PAGE_PARAM = "account"
PAGE_KEY = "_account_page"
RESTORE_KEY = "_account_restore_done"
REMEMBER_KEY = "_account_remembered"
PENDING_KEY = "_account_pending_marker"

PAGES = {
    "student": ("Trang học sinh", "Chọn, đổi hoặc rút giáo viên hướng dẫn của em."),
    "teacher": ("Trang giáo viên", "Danh sách học sinh đã chọn thầy/cô, xếp theo lớp."),
    "login": ("Đăng nhập", "Đăng nhập tài khoản tự đăng ký."),
    "register": ("Đăng ký tài khoản", "Tự chọn tên đăng nhập và mật khẩu, không cần email."),
}

SESSION_KEYS = ("self_session", "self_profile", "self_teachers", "self_roster",
                "self_status", "self_pick", "self_username", "self_login_open")


def config_from_secrets() -> dict:
    try:
        return dict(st.secrets.get("classroom_firebase", {}))
    except Exception:
        return {}


def _resolved(config) -> dict:
    return config_from_secrets() if config is None else dict(config or {})


def _remember(session, profile, username: str) -> None:
    """Xếp dấu nhớ đăng nhập vào hàng đợi.

    Không ghi ngay: component localStorage chỉ tới được trình duyệt khi lượt
    chạy kết thúc, mà ngay sau khi đăng nhập lại có ``st.rerun()``. Vì vậy chỉ
    ghi dấu ở lượt kế tiếp (xem ``flush_marker``).
    """

    payload = store.payload_from_session(session, profile, username)
    if payload is None:
        return
    st.session_state[PENDING_KEY] = payload
    st.session_state["self_username"] = payload["username"]


def flush_marker() -> None:
    """Ghi dấu đang chờ xuống trình duyệt, đúng một lần mỗi lượt."""

    payload = st.session_state.pop(PENDING_KEY, None)
    if not isinstance(payload, dict):
        return
    if store.remember(payload):
        st.session_state[REMEMBER_KEY] = True


def client_for(config: dict, username: str | None = None) -> FirebaseClassroom:
    """Client Firebase có móc ghi lại refresh token sau mỗi lần làm mới phiên."""

    def _persist(session) -> None:
        name = username or st.session_state.get("self_username") or ""
        current = st.session_state.get("self_profile") or {}
        _remember(session, current, name)

    return FirebaseClassroom(config, on_refresh=_persist)


def bootstrap(config=None) -> None:
    """Khôi phục phiên từ dấu trong trình duyệt, đúng một lần mỗi phiên."""

    if st.session_state.get(RESTORE_KEY):
        return
    if st.session_state.get("self_session") is not None:
        st.session_state[RESTORE_KEY] = True
        return
    cfg = _resolved(config)
    if cfg.get("enabled") is not True:
        st.session_state[RESTORE_KEY] = True
        return
    saved = store.read_remembered()
    if not isinstance(saved, dict):
        # Chưa có dấu, hoặc component chưa kịp trả về — lần rerun sau thử lại.
        return
    st.session_state[RESTORE_KEY] = True
    if not store.is_fresh(saved):
        store.forget()
        return
    try:
        client = client_for(cfg, saved["username"])
        session = client.session_from_refresh(saved["refresh_token"])
        profile = client.self_profile(session)
    except (ClassroomConnectionError, cp.ClassroomPackageError):
        # Mạng lỗi hoặc token chưa dùng được: giữ dấu để lần sau thử lại.
        return
    if profile.get("kind") not in ("student", "teacher"):
        store.forget()
        return
    st.session_state.update(self_session=session, self_profile=profile,
                            self_username=saved["username"])
    st.session_state[REMEMBER_KEY] = True


def _role_label(profile: dict) -> str:
    return "GV" if profile.get("kind") == "teacher" else "HS"


def _label(profile: dict, logged_in: bool) -> str:
    if not logged_in:
        return "👤 Khách"
    name = (profile.get("display_name") or "").strip()
    role = _role_label(profile)
    return f"👤 {name} · {role}" if name else f"👤 {role}"


def _goto(page: str):
    def _callback() -> None:
        st.session_state[PAGE_KEY] = page
        try:
            st.query_params[PAGE_PARAM] = page
        except Exception:
            pass
    return _callback


def _back() -> None:
    st.session_state.pop(PAGE_KEY, None)
    try:
        st.query_params.clear()
    except Exception:
        pass


def _logout() -> None:
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    store.forget()
    st.session_state.pop(REMEMBER_KEY, None)
    _back()


def _forget_remembered() -> None:
    store.forget()
    st.session_state.pop(REMEMBER_KEY, None)


def _requested_page() -> str | None:
    page = st.session_state.get(PAGE_KEY)
    if page is None:
        try:
            page = st.query_params.get(PAGE_PARAM)
        except Exception:
            page = None
    return page if page in PAGES else None


def _summary(profile: dict) -> None:
    name = profile.get("display_name") or "(chưa có tên)"
    if profile.get("kind") == "teacher":
        st.markdown(f"**{name}** · giáo viên")
    else:
        st.markdown(f"**{name}** · khối {profile.get('block', '?')}, "
                    f"lớp {profile.get('class_name', '?')}")
    username = st.session_state.get("self_username")
    if username:
        st.caption(f"Tên đăng nhập: {username}")


def _member_tools(profile: dict, scope: str = "bar") -> None:
    """Nút điều hướng của người đã đăng nhập.

    ``scope`` tách khoá widget: nút tài khoản và trang tài khoản cùng hiện trên
    một màn hình, trùng khoá là Streamlit báo lỗi và trắng trang.
    """
    kind = profile.get("kind")
    if kind == "teacher":
        st.button("Trang giáo viên", key=f"account_{scope}_open_teacher", width="stretch",
                  type="primary", on_click=_goto("teacher"))
    elif kind == "student":
        st.button("Trang học sinh", key=f"account_{scope}_open_student", width="stretch",
                  type="primary", on_click=_goto("student"))
    if st.session_state.get(REMEMBER_KEY):
        st.caption("🔓 Đang nhớ đăng nhập trên máy này. Chỉ bật khi dùng máy của em.")
        st.button("Quên tài khoản trên máy này", key=f"account_{scope}_forget",
                  width="stretch", on_click=_forget_remembered)
    st.button("Đăng xuất", key=f"account_{scope}_logout", width="stretch", on_click=_logout)


def render_account_bar(config=None) -> None:
    """Hộp tài khoản cố định góc phải trên; an toàn khi chưa cấu hình Firebase."""

    cfg = _resolved(config)
    profile = st.session_state.get("self_profile") or {}
    logged_in = st.session_state.get("self_session") is not None and bool(profile.get("kind"))
    flush_marker()
    with st.container(key=BAR_KEY):
        with st.popover(_label(profile, logged_in)):
            if cfg.get("enabled") is not True:
                st.caption("Tự đăng ký tài khoản chưa bật trên bản này. Em vẫn dùng mã tài khoản "
                           "do giáo viên cấp ở phần nộp bài trong tab **Nhật ký và tiến độ**.")
                return
            try:
                FirebaseClassroom(cfg)          # kiểm cấu hình, không gọi mạng
            except Exception:
                st.warning("Kênh tài khoản đang được cấu hình. Hãy quay lại sau.")
                return
            if logged_in:
                _summary(profile)
                _member_tools(profile, "bar")
            else:
                # Nút tài khoản chỉ để chọn lối đi; form nằm ở trang riêng cho
                # rộng rãi và để mỗi việc chỉ có một cửa.
                st.caption("Em chưa đăng nhập.")
                st.button("Đăng nhập", key="account_bar_go_login", width="stretch",
                          type="primary", on_click=_goto("login"))
                st.button("Đăng ký tài khoản", key="account_bar_go_register",
                          width="stretch", on_click=_goto("register"))


def render_account_page(config=None) -> bool:
    """Vẽ trang tài khoản nếu URL/phiên yêu cầu. Trả True để ``app.py`` dừng."""

    page = _requested_page()
    if page is None:
        return False
    title, subtitle = PAGES[page]
    cfg = _resolved(config)
    st.markdown('<div class="qa-eyebrow">TÀI KHOẢN</div>', unsafe_allow_html=True)
    st.subheader(title)
    st.caption(subtitle)
    st.button("← Quay lại ứng dụng", key="account_back", on_click=_back)
    if cfg.get("enabled") is not True:
        st.info("Tự đăng ký tài khoản chưa bật trên bản này.")
        return True
    try:
        client = client_for(cfg)
    except Exception:
        st.warning("Kênh tài khoản đang được cấu hình. Hãy quay lại sau.")
        return True
    profile = st.session_state.get("self_profile") or {}
    logged_in = st.session_state.get("self_session") is not None and bool(profile.get("kind"))
    if page in ("login", "register"):
        panels.entry(client, on_login=_remember)
        return True
    if not logged_in:
        st.info("Em cần đăng nhập trước. Dùng ô tài khoản ở góc phải trên, hoặc ngay bên dưới.")
        panels.entry(client, on_login=_remember)
        return True
    _summary(profile)
    st.divider()
    kind = profile.get("kind")
    try:
        if page == "student" and kind == "student":
            panels.student_panel(client, st.session_state.self_session, profile)
        elif page == "teacher" and kind == "teacher":
            panels.teacher_panel(client, st.session_state.self_session)
        else:
            st.warning(f"Tài khoản đang đăng nhập là **{_role_label(profile)}**, "
                       f"không mở được {title.lower()}. Đăng xuất rồi đăng nhập đúng vai trò.")
    except (ClassroomConnectionError, cp.ClassroomPackageError) as exc:
        st.warning(str(exc))
    st.divider()
    _member_tools(profile, "page")
    return True
