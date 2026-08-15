"""Phân loại và trình bày trạng thái dữ liệu cho đúng người đọc.

Vì sao cần tệp này
------------------
Trên máy chủ đặt ngoài Việt Nam, các nguồn dữ liệu chứng khoán chặn dải địa chỉ
trung tâm dữ liệu, nên mọi mã đều trả về lỗi nhà cung cấp. Trước đây ứng dụng
đổ nguyên chuỗi lỗi kỹ thuật ra màn hình đỏ, khiến học sinh mở link tưởng phần
mềm hỏng — trong khi **toàn bộ đường học vẫn chạy được** vì bài học không cần
dữ liệu.

Hai loại lỗi cần tách bạch:

- **Hạ tầng**: nguồn dữ liệu không với tới được. Người dùng không làm gì sai và
  cũng không sửa được. Với người học, đây chỉ là thông tin.
- **Nhập liệu**: mã sai, khoảng ngày sai. Người dùng sửa được, nên phải nói rõ.
"""

from __future__ import annotations

KIND_PROVIDER = "ha_tang"
KIND_INPUT = "nhap_lieu"
KIND_NONE = "khong_loi"

# Dấu hiệu lỗi đến từ phía nhà cung cấp chứ không phải từ người dùng.
_PROVIDER_MARKERS = (
    "provider_error",
    "incomplete_portfolio",
    "market-data validation failed",
    "không tải được dữ liệu",
    "circuit",
    "timeout",
    "connection",
    "403",
    "429",
)

# Dấu hiệu người dùng nhập sai và có thể tự sửa.
_INPUT_MARKERS = (
    "ngày bắt đầu phải trước",
    "cần ít nhất một mã",
    "giới hạn 12 mã",
    "không hợp lệ",
)


def classify(error_text: str | None) -> str:
    """Xếp loại một chuỗi lỗi. Không rõ thì coi là hạ tầng.

    Nghiêng về phía hạ tầng vì đó là phía người dùng không sửa được; gán nhầm
    thành lỗi nhập liệu sẽ khiến họ loay hoay sửa thứ vốn không sai.
    """

    text = str(error_text or "").strip().lower()
    if not text:
        return KIND_NONE
    for marker in _INPUT_MARKERS:
        if marker in text:
            return KIND_INPUT
    for marker in _PROVIDER_MARKERS:
        if marker in text:
            return KIND_PROVIDER
    return KIND_PROVIDER


def message_for(kind: str, *, is_learner: bool) -> str:
    """Câu chữ hiển thị, khác nhau theo người đọc.

    Người học cần biết mình vẫn học được. Người nghiên cứu cần biết vì sao dữ
    liệu không về và làm gì tiếp.
    """

    if kind == KIND_INPUT:
        return (
            "Thông tin nhập vào chưa hợp lệ. Hãy kiểm tra lại mã cổ phiếu và "
            "khoảng ngày ở thanh bên."
        )

    if kind == KIND_PROVIDER:
        if is_learner:
            return (
                "**Chưa lấy được giá thị trường lúc này.** Không sao — toàn bộ "
                "phần **Lộ trình học** vẫn dùng được bình thường, vì bài học "
                "không cần dữ liệu trực tuyến. Hãy bắt đầu từ đó."
            )
        return (
            "**Nguồn dữ liệu đang không phản hồi.** Thường gặp khi ứng dụng chạy "
            "trên máy chủ đặt ngoài Việt Nam: các nguồn chặn dải địa chỉ trung "
            "tâm dữ liệu. Chạy ứng dụng từ máy có địa chỉ mạng tại Việt Nam thì "
            "dữ liệu về bình thường."
        )

    return ""


def should_show_technical_detail(kind: str, *, is_learner: bool) -> bool:
    """Chuỗi lỗi kỹ thuật chỉ hữu ích cho người nghiên cứu."""

    return kind != KIND_NONE and not is_learner
