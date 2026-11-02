"""Trang "Hướng dẫn": học sinh và giáo viên đọc để biết web có gì, dùng thế nào.

Khác với hộp "Chức năng này là gì" nằm trong từng thẻ (``feature_guides``), trang
này trả lời câu hỏi của người mới: bắt đầu từ đâu, đi theo thứ tự nào.

Danh sách chức năng sinh từ ``lmode.FEATURES`` và ``feature_guides.GUIDES``, nên
thêm chức năng mới là tự có mặt ở đây. Mọi tên nút nhắc tới được
``tests/test_user_guide.py`` đối chiếu với mã nguồn: hướng dẫn chỉ nói về thứ có thật.
"""

from __future__ import annotations

import streamlit as st

import account_help
import curriculum as cur
import feature_guides as fg
import learning_modes as lmode
from workspace_ui import HISTORY_LABEL, MUSE_LABEL, PROGRESS_TAB_LABEL, TAB_MAP

GUIDE_LABEL = "Hướng dẫn"

STUDENT_STEPS = (
    ("Chọn lớp của em",
     "Ở thanh bên, mở **Lộ trình và trình độ** rồi chọn lớp. Bài học và công cụ sẽ khớp theo lớp."),
    ("Làm bài chẩn đoán Đầu vào",
     f"Vào **Nhật ký và tiến độ → {PROGRESS_TAB_LABEL}**, làm phần **Đầu vào (pre-test)**. "
     "Điểm này là mốc để cuối khóa so xem em tiến bộ bao nhiêu."),
    ("Học trong Lộ trình học",
     "Mỗi bài có giải thích, ví dụ, câu hỏi tự chấm. Đạt từ "
     f"{cur.UNLOCK_THRESHOLD:.0f} điểm là qua bài."),
    ("Tập đầu tư bằng tiền ảo",
     "Vào **Đầu tư → Danh mục mô phỏng**, chọn vốn ảo đúng bằng số tiền em định dùng thật. "
     "Trước mỗi lệnh, ghi lý do vào **Nhật ký quyết định**."),
    ("Nộp bài cho giáo viên (nếu thầy cô giao)",
     "Đăng ký tài khoản ở nút góc phải trên và chọn giáo viên. Nạp gói thầy cô gửi ở **Nhật ký "
     "và tiến độ → Gói lớp học → Học sinh: nạp gói và xuất kết quả**, làm bài, rồi vào "
     "**Lớp học của em** để nộp."),
    ("Kết thúc và giữ lại kết quả",
     "Làm phần **Đầu ra (post-test)** để so với đầu vào. Ở mục **Sao lưu hồ sơ**, tải hồ sơ về máy."),
)

TEACHER_STEPS = (
    ("Xin mã mời giáo viên",
     "Liên hệ quản trị viên của trang. Mỗi mã dùng một lần; nhờ vậy không ai tự xưng là giáo viên."),
    ("Tạo tài khoản",
     "Bấm nút tài khoản góc phải trên → **Đăng ký tài khoản** → **Em là giáo viên**, nhập mã mời. "
     "Tên hiển thị của thầy/cô sẽ hiện trong danh sách cho học sinh chọn."),
    ("Mời học sinh vào lớp",
     "Gửi link web cho lớp, dặn các em đăng ký rồi chọn đúng tên thầy/cô. Xem danh sách ở "
     "**Lớp học của tôi → Tải danh sách học sinh**; danh sách xếp theo khối rồi tên lớp."),
    ("Giao bài",
     "Vào **Nhật ký và tiến độ → Gói lớp học → Giáo viên: tạo gói giao bài**, bấm **Tạo gói giao "
     "bài** rồi **Tải gói giao bài (.json)**. Gửi tệp đó cho học sinh qua nhóm lớp."),
    ("Xem kết quả",
     "Vào **Lớp học của tôi → Tải danh sách và bài nộp**. Có thể xuất CSV để mở bằng Excel. "
     "Điểm do máy của học sinh cung cấp, chưa phải điểm đã xác minh, nên chỉ dùng để theo dõi."),
)

TEACHER_NOTE = (
    "Thầy/cô chỉ thấy học sinh đã chọn mình. Học sinh nhận được thông báo khi bị xóa khỏi "
    "danh sách và có thể chọn lại. Ứng dụng không đặt lệnh thật và không mở tài khoản chứng khoán."
)

# Chức năng không nằm trong FEATURES nhưng người dùng vẫn thấy trên thẻ.
EXTRA_ITEMS = {
    lmode.AREA_LEARNING: (
        ("Bài học và thực hành", "Bài học theo lớp, có ví dụ và câu hỏi tự chấm."),
        (MUSE_LABEL, "Soạn sẵn yêu cầu để nhờ AI bên ngoài làm hình, video minh họa cho bài học."),
    ),
    lmode.AREA_DATA: (
        (HISTORY_LABEL, "Nạp mã cổ phiếu, xem giá cuối ngày, so sánh biến động giữa các mã."),
    ),
    lmode.AREA_INVEST: (
        ("Sẵn sàng dùng vốn thật", fg.GUIDES[fg.PANEL_READINESS].what),
        ("Nơi mở tài khoản", fg.GUIDES[fg.PANEL_PROVIDERS].what),
        ("Chứng khoán trên MoMo",
         "Giới thiệu dịch vụ, điều kiện tuổi, phí và cảnh báo pháp lý, kèm nguồn chính chủ."),
    ),
    lmode.AREA_JOURNAL: (
        (PROGRESS_TAB_LABEL, fg.GUIDES[fg.PANEL_PROGRESS].what),
        ("Nhật ký quyết định", fg.GUIDES[fg.PANEL_JOURNAL].what),
        ("Gói lớp học", "Giáo viên tạo gói giao bài; học sinh nạp gói và xuất kết quả."),
        ("Lịch sử thiết lập", fg.GUIDES[fg.PANEL_POLICY].what),
    ),
}

FAQ = (
    ("Có bắt buộc đăng nhập không?",
     "Không. Khách vẫn dùng được toàn bộ bài học và công cụ. Tài khoản chỉ cần khi em muốn nộp "
     "bài cho giáo viên."),
    ("Điểm và bài làm của em lưu ở đâu?",
     "Lưu trong trình duyệt trên máy đang dùng, không gắn với tài khoản. Đổi máy hoặc xóa dữ liệu "
     "trình duyệt thì mất, nên hãy tải hồ sơ ở mục **Sao lưu hồ sơ** và dùng **Nạp lại hồ sơ đã "
     "lưu** khi cần."),
    ("Em quên mật khẩu thì sao?", "\n".join(
        f"{i}. {step}" for i, step in enumerate(account_help.FORGOT_PASSWORD_STEPS, start=1))),
    ("Thầy/cô quên mật khẩu thì sao?",
     "Xin quản trị viên một mã mời mới rồi đăng ký tài khoản khác. Học sinh cần chọn lại tên "
     "thầy/cô; bài nộp cũ nằm ở tài khoản cũ."),
    ("Vì sao có công cụ không thấy trong thẻ?",
     f"Ở lộ trình THPT, công cụ nâng cao mở sau khi em đạt {cur.UNLOCK_REQUIRED_LESSONS} bài từ "
     f"{cur.UNLOCK_THRESHOLD:.0f} điểm. Lộ trình đại học thấy đủ ngay."),
    ("Vì sao chưa tải được giá cổ phiếu?",
     "Nguồn giá có lúc không phản hồi. Lộ trình học và danh mục mô phỏng vẫn dùng được; thử lại sau."),
    ("Mở link thấy màn hình \"Zzzz\" là lỗi à?",
     "Không. Trang tự ngủ khi lâu không có ai vào. Bấm nút xanh, đợi khoảng nửa phút là trang mở lại."),
    ("Đổi sang giao diện nền sáng hoặc nền tối ở đâu?",
     "Bấm dấu ba chấm ở góc phải trên → Settings → Theme. Mặc định web theo cài đặt của thiết bị."),
    ("Web này có đặt lệnh mua bán thật không?",
     "Không. Mọi giao dịch trong web đều bằng tiền ảo. Kết quả ở đây không cam kết lợi nhuận và "
     "không phải lời khuyên đầu tư."),
)


def _render_steps(steps) -> None:
    for number, (title, body) in enumerate(steps, start=1):
        st.markdown(f"**Bước {number}. {title}**")
        st.write(body)


def _render_feature_map() -> None:
    st.caption("Vào thẻ nào cũng có hộp **Chức năng này là gì và dùng thế nào?** để xem chi tiết.")
    uses = {area: use for area, use, _when in TAB_MAP}
    whens = {area: when for area, _use, when in TAB_MAP}
    for area in lmode.AREA_ORDER:
        with st.expander(lmode.AREA_LABELS[area]):
            st.write(f"**Dùng để:** {uses.get(area, '')}. **Khi nào:** {whens.get(area, '')}.")
            for name, what in EXTRA_ITEMS.get(area, ()):
                st.markdown(f"- **{name}** — {what}")
            for key in lmode.features_in_area(area, list(lmode.FEATURES)):
                meta = lmode.FEATURES[key]
                lock = " 🔒" if meta["advanced"] else ""
                guide = fg.get_guide(key)
                st.markdown(f"- **{meta['label']}**{lock} — {guide.what if guide else ''}")
    st.caption("🔒 là công cụ nâng cao, ở lộ trình THPT mở sau khi đạt đủ bài.")


def render_user_guide() -> None:
    st.header(GUIDE_LABEL)
    st.caption("Đọc phần dành cho em hoặc thầy/cô, làm lần lượt từng bước. Không cần nhớ hết: "
               "trang này luôn ở trên thanh thẻ.")
    student, teacher, features, faq = st.tabs(
        ["Học sinh", "Giáo viên", "Tất cả chức năng", "Câu hỏi thường gặp"])
    with student:
        _render_steps(STUDENT_STEPS)
    with teacher:
        _render_steps(TEACHER_STEPS)
        st.info(TEACHER_NOTE)
    with features:
        _render_feature_map()
    with faq:
        for question, answer in FAQ:
            with st.expander(question):
                st.markdown(answer)
