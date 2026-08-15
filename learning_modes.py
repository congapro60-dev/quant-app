"""Hai chế độ trình bày dùng chung một bộ máy tính toán.

Ứng dụng không tách làm hai bản. Chế độ chỉ quyết định *hiển thị cái gì* và
*mở khóa tham số nào*; toàn bộ dữ liệu phân tích, sổ danh mục mô phỏng và kết
quả kiểm thử nằm ngoài phạm vi ảnh hưởng của việc đổi chế độ.

Các hàm ở đây nhận vào một ``MutableMapping`` chứ không phụ thuộc
``st.session_state``, để kiểm thử được mà không cần dựng Streamlit.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

MODE_HIGHSCHOOL = "thpt"
MODE_UNIVERSITY = "dai_hoc"

MODE_KEY = "learning_mode"
UNLOCK_KEY = "advanced_unlocked"

MODE_LABELS = {
    MODE_HIGHSCHOOL: "Nền tảng THPT (High-school foundation)",
    MODE_UNIVERSITY: "Chuyên sâu đại học (University advanced)",
}

MODE_DESCRIPTIONS = {
    MODE_HIGHSCHOOL: (
        "Học từ gốc: tiền, giá, rủi ro, đọc biểu đồ và giao dịch mô phỏng "
        "(paper trading). Mở khóa dần công cụ nâng cao sau khi hoàn thành bài học."
    ),
    MODE_UNIVERSITY: (
        "Đầy đủ công cụ định lượng: mô hình chỉ số đơn (SIM), bình phương tối "
        "thiểu (OLS), Markowitz, kiểm thử ngoài mẫu (out-of-sample backtest), "
        "EViews và chẩn đoán mô hình."
    ),
}

VALID_MODES = (MODE_HIGHSCHOOL, MODE_UNIVERSITY)
DEFAULT_MODE = MODE_HIGHSCHOOL

# ---------------------------------------------------------------------------
# Hồ sơ người học: lớp, mức kiến thức, mục tiêu
# ---------------------------------------------------------------------------
#
# Chỉ thu thập thông tin phục vụ việc chọn nội dung. Không hỏi họ tên, ngày sinh
# hay bất kỳ dữ liệu định danh nào — ứng dụng không có nhu cầu và không lưu.

LEARNER_PROFILE_KEY = "learner_profile"

GRADE_LEVELS = ("lop_10", "lop_11", "lop_12", "sinh_vien", "khac")
GRADE_LABELS = {
    "lop_10": "Lớp 10",
    "lop_11": "Lớp 11",
    "lop_12": "Lớp 12",
    "sinh_vien": "Sinh viên đại học",
    "khac": "Khác",
}

KNOWLEDGE_LEVELS = ("moi_bat_dau", "co_ban", "kha", "vung")
KNOWLEDGE_LABELS = {
    "moi_bat_dau": "Mới bắt đầu — chưa từng tìm hiểu",
    "co_ban": "Cơ bản — biết vài khái niệm",
    "kha": "Khá — đã đọc báo cáo và biểu đồ",
    "vung": "Vững — đã học thống kê hoặc kinh tế lượng",
}

GOALS = (
    "hieu_tai_chinh_ca_nhan",
    "on_thi",
    "tap_dau_tu_mo_phong",
    "nghien_cuu_dinh_luong",
)
GOAL_LABELS = {
    "hieu_tai_chinh_ca_nhan": "Hiểu tài chính cá nhân",
    "on_thi": "Ôn thi môn kinh tế lượng",
    "tap_dau_tu_mo_phong": "Tập đầu tư bằng giao dịch mô phỏng (paper trading)",
    "nghien_cuu_dinh_luong": "Nghiên cứu định lượng chuyên sâu",
}

# Gợi ý chế độ theo lớp; người học vẫn có quyền chọn khác.
_GRADE_TO_MODE = {
    "lop_10": MODE_HIGHSCHOOL,
    "lop_11": MODE_HIGHSCHOOL,
    "lop_12": MODE_HIGHSCHOOL,
    "sinh_vien": MODE_UNIVERSITY,
}


def default_learner_profile() -> dict[str, Any]:
    return {"grade_level": "khac", "knowledge_level": "moi_bat_dau", "goals": []}


def normalise_learner_profile(raw: Any) -> dict[str, Any]:
    """Ép hồ sơ về giá trị hợp lệ; bỏ mọi khoá lạ và dữ liệu định danh."""

    if not isinstance(raw, MutableMapping) and not isinstance(raw, dict):
        return default_learner_profile()

    grade = str(raw.get("grade_level", "")).strip().lower()
    knowledge = str(raw.get("knowledge_level", "")).strip().lower()

    goals_in = raw.get("goals") or []
    if isinstance(goals_in, str):
        goals_in = [goals_in]
    goals = [g for g in goals_in if isinstance(g, str) and g in GOALS]

    return {
        "grade_level": grade if grade in GRADE_LEVELS else "khac",
        "knowledge_level": knowledge if knowledge in KNOWLEDGE_LEVELS else "moi_bat_dau",
        "goals": list(dict.fromkeys(goals)),
    }


def store_learner_profile(
    session: MutableMapping[str, Any], raw: Any
) -> dict[str, Any]:
    clean = normalise_learner_profile(raw)
    session[LEARNER_PROFILE_KEY] = clean
    return clean


def get_learner_profile(session: MutableMapping[str, Any] | None) -> dict[str, Any]:
    if session is None:
        return default_learner_profile()
    return normalise_learner_profile(session.get(LEARNER_PROFILE_KEY))


MODE_OVERRIDE_KEY = "mode_override"


def mode_from_grade(learner_profile: Any) -> str:
    """Lộ trình suy ra từ lớp.

    Lớp và lộ trình là **một trục**, không phải hai. Trước đây ứng dụng có hai ô
    chọn riêng và chúng mâu thuẫn được với nhau, khiến người dùng phải đoán ô
    nào mới có tác dụng.
    """

    clean = normalise_learner_profile(learner_profile)
    return _GRADE_TO_MODE.get(clean["grade_level"], DEFAULT_MODE)


def apply_grade_to_mode(session: MutableMapping[str, Any]) -> str:
    """Đồng bộ chế độ theo lớp, trừ khi giáo viên đã đặt thủ công.

    Giữ nguyên dữ liệu phiên: dùng lại :func:`switch_mode` chứ không ghi thẳng.
    """

    if session.get(MODE_OVERRIDE_KEY):
        return get_mode(session)

    target = mode_from_grade(session.get(LEARNER_PROFILE_KEY))
    if target != get_mode(session):
        switch_mode(session, target)
    return target


def area_has_content(area: str, feature_names: list[str]) -> bool:
    """Khu vực có gì để hiện không.

    Lộ trình học và Nhật ký luôn có nội dung riêng, không phụ thuộc danh sách
    chức năng. Ba khu vực còn lại chỉ tồn tại khi có ít nhất một chức năng —
    nếu không sẽ sinh ra một thẻ trống, bấm vào thấy trang trắng.
    """

    if area in (AREA_LEARNING, AREA_JOURNAL):
        return True
    return bool(features_in_area(area, feature_names))


def visible_areas(session: MutableMapping[str, Any] | None = None,
                  feature_names: list[str] | None = None) -> list[str]:
    if feature_names is None:
        feature_names = visible_features(session or {})
    return [a for a in AREA_ORDER if area_has_content(a, feature_names)]

# Trạng thái phân tích/danh mục phải sống sót qua mọi lần đổi chế độ.
# Đây là hợp đồng được kiểm thử khóa lại, không được rút gọn tùy tiện.
PRESERVED_SESSION_KEYS: tuple[str, ...] = (
    "prices_df",
    "returns_df",
    "valid_assets",
    "market_ticker",
    "sim_results_list",
    "opt_res",
    "paper_ledger",
    "paper_trades",
    "trade_plans",
    "backtest_result",
    "eviews_data",
    "intraday_result",
    "last_query",
    "last_update",
    "data_status",
    "data_error",
    "data_last_date",
    "data_source",
    "tickers_val",
    "progress_profile",
    "readiness_state",
    "learner_profile",
    "risk_limits",
    "policy_audit",
)

# ---------------------------------------------------------------------------
# Khu vực giao diện
# ---------------------------------------------------------------------------

AREA_LEARNING = "lo_trinh_hoc"
AREA_DATA = "kham_pha_du_lieu"
AREA_MODEL_LAB = "phong_thi_nghiem_mo_hinh"
AREA_INVEST = "dau_tu"
AREA_JOURNAL = "nhat_ky_tien_do"

AREA_ORDER = (
    AREA_LEARNING,
    AREA_DATA,
    AREA_MODEL_LAB,
    AREA_INVEST,
    AREA_JOURNAL,
)

AREA_LABELS = {
    AREA_LEARNING: "Lộ trình học",
    AREA_DATA: "Khám phá dữ liệu",
    AREA_MODEL_LAB: "Phòng thí nghiệm mô hình",
    AREA_INVEST: "Đầu tư",
    AREA_JOURNAL: "Nhật ký và tiến độ",
}

# Chín chức năng sẵn có, ánh xạ vào năm khu vực.
# `advanced=True` nghĩa là chế độ THPT chỉ thấy sau khi mở khóa.
FEATURE_SIM = "sim"
FEATURE_MARKOWITZ = "markowitz"
FEATURE_EVIEWS = "eviews"
FEATURE_EXAM = "exam"
FEATURE_INTRADAY = "intraday"
FEATURE_INVEST_DESK = "invest_desk"
FEATURE_PAPER = "paper_portfolio"
FEATURE_BACKTEST = "backtest"
FEATURE_ADVISOR = "advisor"

FEATURES: dict[str, dict[str, Any]] = {
    FEATURE_INTRADAY: {
        "label": "Giá trong phiên",
        "area": AREA_DATA,
        "advanced": False,
    },
    FEATURE_EVIEWS: {
        "label": "EViews tiếng Việt",
        "area": AREA_DATA,
        "advanced": True,
    },
    FEATURE_SIM: {
        "label": "Rủi ro chỉ số đơn (SIM)",
        "area": AREA_MODEL_LAB,
        "advanced": True,
    },
    FEATURE_MARKOWITZ: {
        "label": "Danh mục trung bình–phương sai (Markowitz)",
        "area": AREA_MODEL_LAB,
        "advanced": True,
    },
    FEATURE_EXAM: {
        "label": "Ôn thi",
        "area": AREA_MODEL_LAB,
        "advanced": True,
    },
    FEATURE_BACKTEST: {
        "label": "Kiểm thử ngoài mẫu (backtest OOS)",
        "area": AREA_MODEL_LAB,
        "advanced": True,
    },
    FEATURE_INVEST_DESK: {
        "label": "Bàn đầu tư",
        "area": AREA_INVEST,
        "advanced": False,
    },
    FEATURE_PAPER: {
        "label": "Danh mục mô phỏng (paper portfolio)",
        "area": AREA_INVEST,
        "advanced": False,
    },
    FEATURE_ADVISOR: {
        "label": "Trợ lý quyết định",
        "area": AREA_INVEST,
        "advanced": True,
    },
}


def normalise_mode(value: Any) -> str:
    """Đưa giá trị bất kỳ về một chế độ hợp lệ."""

    text = str(value or "").strip().lower()
    return text if text in VALID_MODES else DEFAULT_MODE


def get_mode(session: MutableMapping[str, Any]) -> str:
    return normalise_mode(session.get(MODE_KEY))


def is_advanced_unlocked(session: MutableMapping[str, Any]) -> bool:
    """Chế độ đại học luôn mở; THPT phải mở khóa bằng tiến độ học."""

    if get_mode(session) == MODE_UNIVERSITY:
        return True
    return bool(session.get(UNLOCK_KEY, False))


def switch_mode(session: MutableMapping[str, Any], new_mode: Any) -> str:
    """Đổi chế độ mà không đụng tới dữ liệu phân tích/danh mục.

    Hàm chụp lại các khóa trong ``PRESERVED_SESSION_KEYS`` trước khi ghi chế độ
    mới rồi khôi phục nguyên trạng. Cách viết tường minh này để việc "đổi chế độ
    không mất dữ liệu" là hành vi được khóa bằng kiểm thử, thay vì một tác dụng
    phụ tình cờ của việc chỉ ghi thêm một khóa.
    """

    target = normalise_mode(new_mode)
    snapshot = {
        key: session[key] for key in PRESERVED_SESSION_KEYS if key in session
    }

    session[MODE_KEY] = target

    for key, value in snapshot.items():
        session[key] = value

    return target


def visible_features(
    session: MutableMapping[str, Any] | None = None,
    *,
    mode: str | None = None,
    unlocked: bool | None = None,
) -> list[str]:
    """Danh sách chức năng được phép hiển thị.

    Chế độ đại học thấy đủ chín chức năng. Chế độ THPT chỉ thấy nhóm cơ bản cho
    tới khi mở khóa phần nâng cao.
    """

    if mode is None:
        mode = get_mode(session or {})
    else:
        mode = normalise_mode(mode)

    if unlocked is None:
        unlocked = (
            is_advanced_unlocked(session) if session is not None
            else mode == MODE_UNIVERSITY
        )

    if mode == MODE_UNIVERSITY:
        return list(FEATURES)

    return [
        name for name, meta in FEATURES.items()
        if not meta["advanced"] or unlocked
    ]


def features_in_area(area: str, feature_names: list[str]) -> list[str]:
    """Lọc các chức năng đang hiển thị thuộc một khu vực."""

    return [
        name for name in feature_names
        if FEATURES.get(name, {}).get("area") == area
    ]
