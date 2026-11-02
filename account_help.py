"""Nội dung trợ giúp tài khoản, dùng chung cho form đăng nhập và trang Hướng dẫn.

Cố ý là module riêng: Streamlit Cloud kéo code mới mà không khởi động lại tiến
trình, nên module cũ vẫn nằm trong bộ nhớ. Thêm hằng số vào module đang có rồi
đọc nó lúc import từ module mới sẽ làm sập cả app cho tới khi Reboot.
"""

# Tài khoản dùng định danh giả, không có email, và ứng dụng cố ý không giữ khoá
# quản trị, nên không ai đặt lại được mật khẩu. Dùng ở form đăng nhập và trang
# Hướng dẫn; điểm học nằm trong trình duyệt nên không mất theo tài khoản.
FORGOT_PASSWORD_STEPS = (
    "Không ai lấy lại được mật khẩu cũ, kể cả giáo viên. Hãy đăng ký tài khoản mới với tên đăng nhập khác.",
    "Dùng đúng máy và trình duyệt cũ: điểm và bài làm lưu trên máy nên vẫn còn nguyên.",
    "Chọn lại giáo viên hướng dẫn, rồi báo thầy/cô xóa tên cũ trong danh sách.",
    "Nộp lại bài nếu cần. Bài đã nộp từ tài khoản cũ vẫn nằm ở chỗ thầy/cô, "
    "ghi là \"không còn trong danh sách\".",
)
