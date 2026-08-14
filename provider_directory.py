"""Danh bạ nơi mở tài khoản, trung lập và không tiếp thị liên kết.

Nguyên tắc
----------
- **Không xếp hạng, không mã giới thiệu.** Danh sách theo thứ tự bảng chữ cái;
  liên kết là tên miền chính chủ, không gắn tham số theo dõi hay hoa hồng.
- **Không suy diễn chính sách tuổi.** Ứng dụng chỉ ghi lại điều đã có nguồn.
  Mục nào chưa được xác minh sẽ hiển thị "Chưa xác minh — liên hệ nhà cung cấp"
  thay vì đoán, vì điều kiện cho người chưa đủ 18 tuổi khác nhau theo từng công
  ty và từng nhóm sản phẩm.
- **Tách nhóm sản phẩm.** Môi giới cổ phiếu cơ sở, chứng chỉ quỹ và phái sinh là
  ba việc khác nhau; một chính sách tuổi không áp dụng cho mọi sản phẩm.

Ngày triển khai phải xác minh lại với văn bản hiện hành và với chính nhà cung
cấp. Tệp này không phải ý kiến pháp lý.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

UNVERIFIED_NOTICE = "Chưa xác minh — liên hệ nhà cung cấp"

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUS_EXPIRED = "expired"

VALID_STATUSES = (STATUS_VERIFIED, STATUS_UNVERIFIED, STATUS_EXPIRED)

# Nhãn hiển thị: giá trị nội bộ là tiếng Anh, nhưng thứ đưa ra giao diện phải
# có tiếng Việt kèm theo.
STATUS_LABELS = {
    STATUS_VERIFIED: "Đã xác minh (verified)",
    STATUS_UNVERIFIED: "Chưa xác minh (unverified)",
    STATUS_EXPIRED: "Đã hết hạn (expired)",
}


def status_display(status: str) -> str:
    return STATUS_LABELS.get(status, STATUS_LABELS[STATUS_UNVERIFIED])

# Nguồn tra cứu tư cách thành viên lưu ký/bù trừ.
VSDC_MEMBER_LIST = "https://vsd.vn/vi/ms"

# Nhóm sản phẩm
P_STOCK = "Cổ phiếu cơ sở"
P_FUND = "Chứng chỉ quỹ"
P_DERIVATIVE = "Chứng khoán phái sinh (derivatives)"

# Dấu hiệu liên kết tiếp thị — không được xuất hiện trong danh bạ.
_AFFILIATE_MARKERS = (
    "ref=", "referral", "aff=", "affiliate", "utm_", "invite",
    "promo=", "partner=", "campaign", "?r=", "&r=", "clickid",
)


@dataclass(frozen=True)
class Provider:
    """Một bản ghi nhà cung cấp.

    ``age_policy`` để ``None`` nghĩa là chưa xác minh; tầng hiển thị phải dùng
    :meth:`age_policy_display` chứ không đọc thẳng trường này.
    """

    key: str
    legal_name: str
    official_url: str
    products: tuple[str, ...]
    membership_source: str
    age_policy: str | None = None
    age_policy_source: str | None = None
    verified_at: str | None = None
    verification_status: str = STATUS_UNVERIFIED
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_verified(self) -> bool:
        return (
            self.verification_status == STATUS_VERIFIED
            and bool(self.age_policy)
            and bool(self.age_policy_source)
        )

    def age_policy_display(self) -> str:
        """Chuỗi hiển thị cho chính sách tuổi. Chưa xác minh thì nói rõ."""

        if not self.is_verified:
            return UNVERIFIED_NOTICE
        return str(self.age_policy)

    def age_policy_source_display(self) -> str:
        if not self.is_verified or not self.age_policy_source:
            return UNVERIFIED_NOTICE
        return self.age_policy_source


# ---------------------------------------------------------------------------
# Danh sách khởi tạo, xếp theo bảng chữ cái, không xếp hạng
# ---------------------------------------------------------------------------
#
# Chính sách tuổi của sáu công ty môi giới lớn để trạng thái "chưa xác minh":
# tài liệu công khai không nêu điều kiện cho người dưới 18 tuổi một cách nhất
# quán theo từng sản phẩm, nên người dùng phải hỏi và nhận xác nhận trực tiếp.
# Ghi "từ đủ 18 tuổi" ở đây sẽ là suy diễn, nên không ghi.

PROVIDERS: tuple[Provider, ...] = (
    Provider(
        key="dragonx",
        legal_name="Công ty Cổ phần Quản lý quỹ Đầu tư Dragon Capital Việt Nam (DragonX)",
        official_url="https://dautu.dragoncapital.com.vn/",
        products=(P_FUND,),
        membership_source=VSDC_MEMBER_LIST,
        age_policy=None,
        age_policy_source="https://dautu.dragoncapital.com.vn/kien-thuc/huong-dan-tao-tai-khoan-cho-con-dragonx",
        verified_at=None,
        verification_status=STATUS_UNVERIFIED,
        notes=(
            "Kênh chứng chỉ quỹ, không phải tài khoản môi giới cổ phiếu cơ sở.",
            "Nhà cung cấp có công bố hướng dẫn mở tài khoản cho người dưới 18 tuổi "
            "cùng cha/mẹ hoặc người giám hộ; cần đọc và xác nhận lại trước khi mở.",
        ),
    ),
    Provider(
        key="hsc",
        legal_name="Công ty Cổ phần Chứng khoán Thành phố Hồ Chí Minh (HSC)",
        official_url="https://www.hsc.com.vn/vi/tai-khoan",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="mbs",
        legal_name="Công ty Cổ phần Chứng khoán MB (MBS)",
        official_url="https://www.mbs.com.vn/huong-dan-mo-tai-khoan/",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="ssi",
        legal_name="Công ty Cổ phần Chứng khoán SSI",
        official_url="https://iboard.ssi.com.vn/",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="tcbs",
        legal_name="Công ty Cổ phần Chứng khoán Kỹ Thương (TCBS – TCInvest)",
        official_url="https://help.tcbs.com.vn/tai-khoan-chung-khoan-va-tieu-khoan-giao-dich/",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="vietcap",
        legal_name="Công ty Cổ phần Chứng khoán Vietcap",
        official_url="https://www.vietcap.com.vn/mo-tai-khoan",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="vndirect",
        legal_name="Công ty Cổ phần Chứng khoán VNDIRECT (DStock)",
        official_url="https://dstock.vndirect.com.vn/",
        products=(P_STOCK, P_FUND, P_DERIVATIVE),
        membership_source=VSDC_MEMBER_LIST,
        verification_status=STATUS_UNVERIFIED,
        notes=("Hỏi trực tiếp nhà cung cấp về điều kiện cho người dưới 18 tuổi.",),
    ),
    Provider(
        key="vnsc",
        legal_name="Công ty Cổ phần Chứng khoán VINA (VNSC by Finhay)",
        official_url="https://invest.vnsc.vn/",
        products=(P_STOCK, P_FUND),
        membership_source=VSDC_MEMBER_LIST,
        age_policy=None,
        age_policy_source="https://invest.vnsc.vn/",
        verified_at=None,
        verification_status=STATUS_UNVERIFIED,
        notes=(
            "Tài liệu tham chiếu nêu điều khoản công bố có hiệu lực 01/01/2026 "
            "yêu cầu khách hàng cá nhân từ đủ 18 tuổi; cần đọc lại điều khoản "
            "đang hiệu lực tại thời điểm mở tài khoản.",
        ),
    ),
)


def all_providers() -> tuple[Provider, ...]:
    """Trả về danh bạ theo thứ tự bảng chữ cái, không xếp hạng."""

    return tuple(sorted(PROVIDERS, key=lambda p: p.key))


def get_provider(key: str) -> Provider | None:
    wanted = str(key or "").strip().lower()
    for provider in PROVIDERS:
        if provider.key == wanted:
            return provider
    return None


def providers_for_product(product: str) -> tuple[Provider, ...]:
    return tuple(p for p in all_providers() if product in p.products)


def has_affiliate_marker(url: str) -> bool:
    """Phát hiện tham số tiếp thị liên kết trong một liên kết."""

    text = str(url or "").lower()
    return any(marker in text for marker in _AFFILIATE_MARKERS)


def as_row(provider: Provider) -> dict[str, Any]:
    """Chuyển sang dạng bảng để hiển thị, đã áp quy tắc chưa xác minh."""

    return {
        "Tên pháp nhân": provider.legal_name,
        "Trang chính chủ": provider.official_url,
        "Nhóm sản phẩm": ", ".join(provider.products),
        "Nguồn tra tư cách thành viên": provider.membership_source,
        "Chính sách tuổi": provider.age_policy_display(),
        "Nguồn chính sách tuổi": provider.age_policy_source_display(),
        "Ngày xác minh": provider.verified_at or UNVERIFIED_NOTICE,
        "Trạng thái xác minh": status_display(provider.verification_status),
    }


def directory_rows() -> list[dict[str, Any]]:
    return [as_row(p) for p in all_providers()]


_URL_RE = re.compile(r"^https://[a-z0-9.-]+\.[a-z]{2,}(/[^\s]*)?$", re.IGNORECASE)


def is_official_https_url(url: str) -> bool:
    return bool(_URL_RE.match(str(url or "").strip()))
