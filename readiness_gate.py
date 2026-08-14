"""Cổng kiểm soát trước khi người học chuyển từ mô phỏng sang vốn thật.

Nguyên tắc thiết kế
-------------------
1. **Luôn tính lại, không tin cờ đã lưu.** Quyết định được suy ra từ các đầu
   vào thô mỗi lần gọi. Người dùng có sửa ``session_state`` hay thêm tham số
   URL cũng không tạo ra được quyền mới, vì không có cờ "đã qua cổng" nào được
   đọc để ra quyết định.
2. **Sai thì nghiêng về phía chặt.** Giá trị lạ, thiếu hoặc hỏng đều bị quy về
   nhóm tuổi hạn chế nhất.
3. **Không lưu giấy tờ định danh.** Ứng dụng chỉ nhận *nhóm tuổi*, không nhận
   ngày sinh, căn cước, giấy khai sinh hay bất kỳ dữ liệu định danh nào.
4. **Không đặt lệnh thật.** Cổng chỉ mở phần lập kế hoạch; việc mở tài khoản và
   đặt lệnh diễn ra ngoài ứng dụng, do người dùng hoặc người đại diện thực hiện.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Nhóm tuổi (thu thập theo nhóm, không theo ngày sinh)
# ---------------------------------------------------------------------------

AGE_UNDER_15 = "duoi_15"
AGE_15_17 = "tu_15_den_duoi_18"
AGE_18_PLUS = "tu_18_tro_len"
AGE_UNKNOWN = "chua_khai_bao"

AGE_BANDS = (AGE_UNDER_15, AGE_15_17, AGE_18_PLUS)

AGE_LABELS = {
    AGE_UNDER_15: "Dưới 15 tuổi",
    AGE_15_17: "Từ 15 đến dưới 18 tuổi",
    AGE_18_PLUS: "Từ 18 tuổi trở lên",
    AGE_UNKNOWN: "Chưa khai báo",
}

# ---------------------------------------------------------------------------
# Nhóm sản phẩm
# ---------------------------------------------------------------------------

PRODUCT_STOCK = "co_phieu"
PRODUCT_FUND = "chung_chi_quy"
PRODUCT_DERIVATIVE = "phai_sinh"
PRODUCT_MARGIN = "ky_quy"
PRODUCT_SHORT = "ban_khong"
PRODUCT_CFD = "cfd"
PRODUCT_CRYPTO = "tai_san_ma_hoa"

PRODUCT_LABELS = {
    PRODUCT_STOCK: "Cổ phiếu cơ sở",
    PRODUCT_FUND: "Chứng chỉ quỹ",
    PRODUCT_DERIVATIVE: "Chứng khoán phái sinh (derivatives)",
    PRODUCT_MARGIN: "Giao dịch ký quỹ (margin)",
    PRODUCT_SHORT: "Bán khống (short selling)",
    PRODUCT_CFD: "Hợp đồng chênh lệch (CFD)",
    PRODUCT_CRYPTO: "Tài sản mã hóa (crypto)",
}

# Bị khóa cứng với mọi người dưới 18 tuổi.
MINOR_HARD_BLOCKED = (
    PRODUCT_DERIVATIVE,
    PRODUCT_MARGIN,
    PRODUCT_SHORT,
    PRODUCT_CFD,
    PRODUCT_CRYPTO,
)

# Ứng dụng là công cụ nghiên cứu chứng khoán Việt Nam, không hỗ trợ hai nhóm
# này cho bất kỳ độ tuổi nào.
OUT_OF_SCOPE_PRODUCTS = (PRODUCT_CFD, PRODUCT_CRYPTO)

# Khóa đầu vào hợp lệ của cổng. Mọi khóa khác bị loại bỏ khi làm sạch.
GATE_INPUT_KEYS = (
    "age_band",
    "guardian_confirmed",
    "broker_policy_confirmed",
    "paper_first_completed",
    "risk_check_passed",
)

# Dấu hiệu dữ liệu định danh — không bao giờ được lưu.
_PII_MARKERS = (
    "cccd", "cmnd", "cmt", "can_cuc", "cancuoc", "citizen", "national_id",
    "passport", "ho_chieu", "khai_sinh", "birth_cert", "birthdate", "dob",
    "ngay_sinh", "kyc", "id_number", "so_gcn", "tax_code", "ma_so_thue",
    "selfie", "anh_chan_dung", "so_tai_khoan", "bank_account",
)


@dataclass(frozen=True)
class ReadinessDecision:
    """Kết quả cổng. Bất biến để không bị sửa sau khi tính."""

    age_band: str
    real_capital_allowed: bool
    paper_only: bool
    allowed_products: tuple[str, ...] = ()
    blocked_products: tuple[str, ...] = ()
    block_reasons: Mapping[str, str] = field(default_factory=dict)
    outstanding: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def requires_guardian(self) -> bool:
        return self.age_band in (AGE_UNDER_15, AGE_15_17)

    def is_product_allowed(self, product: str) -> bool:
        return product in self.allowed_products


def normalise_age_band(value: Any) -> str:
    """Giá trị lạ/thiếu đều rơi về nhóm chưa khai báo (hạn chế nhất)."""

    text = str(value or "").strip().lower()
    return text if text in AGE_BANDS else AGE_UNKNOWN


def sanitise_gate_inputs(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Chỉ giữ đúng các khóa cổng cần, loại bỏ mọi dữ liệu định danh.

    Đây là hàng rào để dữ liệu căn cước/khai sinh/KYC không bao giờ đi vào
    trạng thái phiên, kể cả khi tầng gọi vô tình truyền vào.
    """

    if not isinstance(raw, Mapping):
        return {}

    clean: dict[str, Any] = {}
    for key, value in raw.items():
        name = str(key).strip().lower()
        if any(marker in name for marker in _PII_MARKERS):
            continue
        if name not in GATE_INPUT_KEYS:
            continue
        clean[name] = value

    if "age_band" in clean:
        clean["age_band"] = normalise_age_band(clean["age_band"])
    for flag in GATE_INPUT_KEYS[1:]:
        if flag in clean:
            clean[flag] = bool(clean[flag])
    return clean


def contains_identity_data(raw: Mapping[str, Any] | None) -> bool:
    """Phát hiện dữ liệu định danh trong một mapping bất kỳ."""

    if not isinstance(raw, Mapping):
        return False
    return any(
        any(marker in str(key).strip().lower() for marker in _PII_MARKERS)
        for key in raw
    )


def evaluate(raw_inputs: Mapping[str, Any] | None) -> ReadinessDecision:
    """Tính quyết định cổng từ đầu vào thô.

    Hàm này không đọc bất kỳ cờ "đã qua cổng" nào. Muốn được phép dùng vốn
    thật thì phải thỏa đủ điều kiện ngay tại lần gọi này.
    """

    data = sanitise_gate_inputs(raw_inputs)
    band = normalise_age_band(data.get("age_band"))

    guardian = bool(data.get("guardian_confirmed", False))
    broker_ok = bool(data.get("broker_policy_confirmed", False))
    paper_done = bool(data.get("paper_first_completed", False))
    risk_ok = bool(data.get("risk_check_passed", False))

    blocked: dict[str, str] = {}
    notes: list[str] = []
    outstanding: list[str] = []

    for product in OUT_OF_SCOPE_PRODUCTS:
        blocked[product] = (
            "Ứng dụng không hỗ trợ nhóm sản phẩm này ở mọi độ tuổi."
        )

    # ---- Chưa khai báo: khóa toàn bộ vốn thật ----
    if band == AGE_UNKNOWN:
        for product in MINOR_HARD_BLOCKED:
            blocked.setdefault(
                product, "Chưa khai báo nhóm tuổi nên chưa mở bất kỳ sản phẩm nào."
            )
        return ReadinessDecision(
            age_band=band,
            real_capital_allowed=False,
            paper_only=True,
            allowed_products=(),
            blocked_products=tuple(sorted(blocked)),
            block_reasons=blocked,
            outstanding=("Chọn nhóm tuổi để tiếp tục.",),
            notes=("Chỉ dùng giao dịch mô phỏng (paper trading) trong ứng dụng.",),
        )

    # ---- Dưới 15: chỉ mô phỏng ----
    if band == AGE_UNDER_15:
        for product in MINOR_HARD_BLOCKED:
            blocked.setdefault(
                product, "Khóa cứng với người dưới 18 tuổi theo chính sách an toàn sản phẩm."
            )
        for product in (PRODUCT_STOCK, PRODUCT_FUND):
            blocked.setdefault(
                product,
                "Dưới 15 tuổi: mọi giao dịch thật do người đại diện thực hiện ngoài ứng dụng.",
            )
        return ReadinessDecision(
            age_band=band,
            real_capital_allowed=False,
            paper_only=True,
            allowed_products=(),
            blocked_products=tuple(sorted(blocked)),
            block_reasons=blocked,
            outstanding=(),
            notes=(
                "Trong ứng dụng chỉ dùng giao dịch mô phỏng (paper trading).",
                "Người đại diện thực hiện mọi giao dịch thật, bên ngoài ứng dụng.",
            ),
        )

    # ---- 15 đến dưới 18: mô phỏng trước, tiền có sẵn, cần người đại diện ----
    if band == AGE_15_17:
        for product in MINOR_HARD_BLOCKED:
            blocked.setdefault(
                product, "Khóa cứng với người dưới 18 tuổi theo chính sách an toàn sản phẩm."
            )
        if not paper_done:
            outstanding.append("Hoàn thành giai đoạn giao dịch mô phỏng bắt buộc.")
        if not guardian:
            outstanding.append("Có xác nhận của người đại diện theo pháp luật.")
        if not broker_ok:
            outstanding.append(
                "Nhận xác nhận bằng văn bản của công ty chứng khoán về chính sách "
                "cho người chưa đủ 18 tuổi."
            )
        if not risk_ok:
            outstanding.append("Đạt bài kiểm tra kiến thức và rủi ro.")

        ready = not outstanding
        allowed = (PRODUCT_STOCK, PRODUCT_FUND) if ready else ()
        if not ready:
            for product in (PRODUCT_STOCK, PRODUCT_FUND):
                blocked.setdefault(product, "Chưa đủ điều kiện của nhóm 15–dưới 18 tuổi.")

        return ReadinessDecision(
            age_band=band,
            real_capital_allowed=ready,
            paper_only=not ready,
            allowed_products=allowed,
            blocked_products=tuple(sorted(blocked)),
            block_reasons=blocked,
            outstanding=tuple(outstanding),
            notes=(
                "Chỉ mua bằng tiền có sẵn (cash-only), không dùng đòn bẩy.",
                "Ứng dụng không gửi lệnh; người đại diện xác nhận và đặt lệnh.",
            ),
        )

    # ---- Từ 18 tuổi: chế độ thông thường sau kiểm tra rủi ro ----
    if not risk_ok:
        outstanding.append("Đạt bài kiểm tra rủi ro trước khi dùng vốn thật.")

    ready = not outstanding
    if ready:
        allowed = (PRODUCT_STOCK, PRODUCT_FUND, PRODUCT_DERIVATIVE,
                   PRODUCT_MARGIN, PRODUCT_SHORT)
    else:
        allowed = ()
        for product in (PRODUCT_STOCK, PRODUCT_FUND, PRODUCT_DERIVATIVE,
                        PRODUCT_MARGIN, PRODUCT_SHORT):
            blocked.setdefault(product, "Chưa đạt bài kiểm tra rủi ro.")

    notes.append("Ứng dụng không đặt lệnh thay bạn; mọi lệnh do bạn tự xác nhận.")
    notes.append(
        "Sản phẩm có đòn bẩy làm khuếch đại lỗ; hãy đọc kỹ điều khoản của công ty "
        "chứng khoán trước khi dùng."
    )

    return ReadinessDecision(
        age_band=band,
        real_capital_allowed=ready,
        paper_only=not ready,
        allowed_products=allowed,
        blocked_products=tuple(sorted(blocked)),
        block_reasons=blocked,
        outstanding=tuple(outstanding),
        notes=tuple(notes),
    )


def evaluate_session(session: MutableMapping[str, Any] | None) -> ReadinessDecision:
    """Tính lại quyết định từ trạng thái phiên, bỏ qua mọi cờ đã lưu.

    Kể cả khi phiên chứa ``real_capital_allowed=True`` do bị sửa tay hay do
    tham số URL, hàm vẫn chỉ đọc các khóa đầu vào hợp lệ trong
    ``readiness_state`` và tính lại từ đầu.
    """

    if session is None:
        return evaluate(None)
    return evaluate(session.get("readiness_state"))


def store_gate_inputs(
    session: MutableMapping[str, Any], raw_inputs: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Ghi đầu vào cổng đã làm sạch vào phiên. Không ghi dữ liệu định danh."""

    clean = sanitise_gate_inputs(raw_inputs)
    session["readiness_state"] = clean
    return clean
