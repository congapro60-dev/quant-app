"""Phòng học thống kê: dạy trực tiếp theo kịch bản SGK Toán 10/11/12.

Ba phòng riêng — Toán 10 (mẫu không ghép nhóm), Toán 11 (trung tâm của mẫu
ghép nhóm), Toán 12 (phân tán của mẫu ghép nhóm) — cùng một mạch dạy đã kiểm
chứng trên lớp: đặt câu hỏi → học sinh dự đoán/tính trên giấy → đối chiếu →
đọc biểu đồ → nêu ý nghĩa → phản tư → chốt bằng "Hội đồng tư vấn đầu tư có
trách nhiệm" → exit ticket.

Dữ liệu: bộ giả định theo kịch bản là mặc định khi dạy (để hiện tượng thống kê
rõ ràng); nhập tay và dữ liệu đã nạp là nguồn mở rộng để vận dụng. Mọi số đặc
trưng đều tính từ dataset đang dùng, không dùng AI.

Khác với các công cụ tự do khác, điểm exit ticket được ghi vào bài học SGK
tương ứng (``s2_so_dac_trung`` / ``s3_mau_ghep_nhom`` / ``s4_phan_tan_ghep_nhom``)
nên hội đồng lớp đã tham gia gói bài nộp sẽ nhận được điểm qua Firebase; học
sinh ngoài lớp vẫn lưu điểm trên máy như bài học thường.
"""

from __future__ import annotations

from math import isfinite, isnan
from typing import Any, Callable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import curriculum as cur
import learning_modes as lmode
import progress_profile as pp
import stats_tools as stt
from dataclasses import dataclass
from workspace_ui import navigate_to

ROOM_10 = "lop_10"
ROOM_11 = "lop_11"
ROOM_12 = "lop_12"

ROOM_ORDER = (ROOM_10, ROOM_11, ROOM_12)
ROOM_LABELS = {
    ROOM_10: "Phòng Toán 10 — số đặc trưng mẫu không ghép nhóm",
    ROOM_11: "Phòng Toán 11 — trung tâm của mẫu ghép nhóm",
    ROOM_12: "Phòng Toán 12 — phân tán của mẫu ghép nhóm",
}
# Điểm exit ticket ghi vào đúng bài học SGK để gói bài nộp của hội đồng lớp
# chuyển tới giáo viên qua Firebase (classroom_submit.build_submission).
ROOM_LESSON_IDS = {
    ROOM_10: "s2_so_dac_trung",
    ROOM_11: "s3_mau_ghep_nhom",
    ROOM_12: "s4_phan_tan_ghep_nhom",
}

# ---------------------------------------------------------------------------
# Bộ dữ liệu kịch bản (đã kiểm chứng số bằng Python, khớp giáo án 100%)
# ---------------------------------------------------------------------------

# Kịch bản Toán 10 (B13–B14): lợi suất ngày (%) của hai cổ phiếu A, B, 10 phiên.
SCENARIO_10_A = (-0.2, 0.0, 0.1, 0.1, 0.2, 0.2, 0.2, 0.2, 0.5, 0.7)
SCENARIO_10_B = (-1.8, -1.0, -0.6, -0.2, 0.1, 0.3, 0.3, 1.0, 1.6, 2.3)

# Kịch bản Toán 11/12: bảng tần số 100 phiên, 6 khoảng [-3; 3) rộng 1.
SCENARIO_MIDS = (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)
SCENARIO_11_FREQ_A = (5, 10, 25, 35, 20, 5)
SCENARIO_11_FREQ_B = (5, 10, 40, 10, 25, 10)

SCENARIO_10_A_TEXT = ", ".join(f"{v:g}" for v in SCENARIO_10_A)
SCENARIO_10_B_TEXT = ", ".join(f"{v:g}" for v in SCENARIO_10_B)


def default_room_for_grade(grade_level: str) -> str:
    """Phòng mặc định theo lớp học sinh chọn ở màn hình 'Bạn là ai'."""

    return {ROOM_10: ROOM_10, ROOM_11: ROOM_11, ROOM_12: ROOM_12}.get(
        grade_level, ROOM_10
    )


# ---------------------------------------------------------------------------
# Dữ liệu phòng học: dãy thô (phòng 10) hoặc bảng tần số (phòng 11/12)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoomData:
    """Dữ liệu đang dùng cho một phòng.

    Phòng 10 giữ hai dãy thô; phòng 11/12 giữ bảng tần số (trung điểm cách
    đều + tần số). ``names`` là nhãn hai bộ dữ liệu khi in bảng tổng kết.
    """

    raw_a: tuple[float, ...] = ()
    raw_b: tuple[float, ...] = ()
    mids: tuple[float, ...] = ()
    freqs_a: tuple[float, ...] = ()
    freqs_b: tuple[float, ...] = ()
    names: tuple[str, str] = ("Cổ phiếu A", "Cổ phiếu B")
    source: str = "Bộ A/B theo kịch bản"

    @property
    def is_grouped(self) -> bool:
        return bool(self.mids)


def scenario_data(room: str) -> RoomData:
    """Bộ dữ liệu kịch bản mặc định khi dạy."""

    if room == ROOM_10:
        return RoomData(raw_a=SCENARIO_10_A, raw_b=SCENARIO_10_B,
                        source="Bộ A/B theo kịch bản (10 phiên)")
    return RoomData(mids=SCENARIO_MIDS, freqs_a=SCENARIO_11_FREQ_A,
                    freqs_b=SCENARIO_11_FREQ_B,
                    source="Bảng tần số theo kịch bản (100 phiên, 6 khoảng)")


def room10_manual(text_a: str, text_b: str) -> RoomData:
    """Dãy thô nhập tay cho phòng 10; sai định dạng thì báo lỗi rõ."""

    values_a = stt.parse_values(text_a)
    values_b = stt.parse_values(text_b)
    if len(values_a) < 2 or len(values_b) < 2:
        raise ValueError("Mỗi bộ dữ liệu cần ít nhất hai số.")
    return RoomData(raw_a=tuple(values_a), raw_b=tuple(values_b),
                    source="Nhập tay")


def room11_manual(mids_text: str, freqs_a_text: str, freqs_b_text: str) -> RoomData:
    """Bảng tần số nhập tay cho phòng 11/12 (trung điểm cách đều + tần số)."""

    mids = stt.parse_values(mids_text)
    freqs_a = stt.parse_values(freqs_a_text)
    freqs_b = stt.parse_values(freqs_b_text)
    return RoomData(mids=tuple(mids), freqs_a=tuple(freqs_a),
                    freqs_b=tuple(freqs_b), source="Bảng tần số nhập tay")


def _frequency_counts(values: list[float], lo: float, width: float,
                      k: int) -> tuple[int, ...]:
    """Đếm tần số của ``values`` trên lưới nhóm dựng sẵn (cùng biên cho mọi bộ)."""

    counts = [0] * k
    for v in values:
        idx = min(int((v - lo) / width), k - 1)
        counts[idx] += 1
    return tuple(counts)


def room11_from_prices(prices: pd.DataFrame, market: str, symbol: str,
                       window: int) -> RoomData:
    """Bảng tần số từ dữ liệu đã nạp: chia dãy lợi suất làm hai nửa giai đoạn.

    Cả hai nửa dùng chung lưới nhóm dựng từ toàn bộ dãy (``group_series``) nên
    hai bảng so sánh được cùng nhóm — đúng tinh thần kịch bản Toán 11.
    """

    series = stt.pct_returns(prices, symbol, int(window) * 2)
    clean = [float(v) for v in series.tolist() if isfinite(float(v))]
    if len(clean) < 12:
        raise ValueError("Dữ liệu đã nạp chưa đủ 12 phiên; chọn số phiên lớn hơn hoặc dùng kịch bản.")
    groups = stt.group_series(clean, 6)
    lo = float(groups["boundaries"][0])
    width = float(groups["width"])
    half = len(clean) // 2
    return RoomData(
        mids=tuple(float(m) for m in groups["mids"]),
        freqs_a=_frequency_counts(clean[:half], lo, width, 6),
        freqs_b=_frequency_counts(clean[half:], lo, width, 6),
        names=(f"{symbol} nửa đầu", f"{symbol} nửa sau"),
        source=f"Dữ liệu đã nạp: {symbol}, chia 2 nửa giai đoạn",
    )


def room10_from_prices(prices: pd.DataFrame, market: str, symbol_a: str,
                       symbol_b: str, window: int) -> RoomData:
    """Dãy lợi suất thật của hai mã đã nạp cho phòng 10."""

    raw_a = tuple(float(v) for v in stt.pct_returns(prices, symbol_a, int(window)).tolist())
    raw_b = tuple(float(v) for v in stt.pct_returns(prices, symbol_b, int(window)).tolist())
    if len(raw_a) < 2 or len(raw_b) < 2:
        raise ValueError("Dữ liệu đã nạp chưa đủ hai phiên cho một trong hai mã.")
    return RoomData(raw_a=raw_a, raw_b=raw_b, names=(symbol_a, symbol_b),
                    source=f"Dữ liệu đã nạp: {symbol_a} và {symbol_b}, {window} phiên")


def prepare_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Bổ sung khóa thuận tiện (mode, fence) để bước học tham chiếu thống nhất."""

    out = dict(summary)
    modes = out.get("modes") or ()
    if modes:
        out["mode"] = float(modes[0])
    out.setdefault("mode", float("nan"))
    fences = out.get("fences")
    if fences and isfinite(fences[0]) and isfinite(fences[1]):
        out["fence_low"], out["fence_high"] = float(fences[0]), float(fences[1])
    else:
        out["fence_low"] = out["fence_high"] = float("nan")
    return out


def resolve_summaries(data: RoomData) -> tuple[dict[str, Any], dict[str, Any]]:
    """Tính số đặc trưng cho cả hai bộ dữ liệu của phòng."""

    if data.is_grouped:
        sa = prepare_summary(stt.summarize_grouped_from_freq(data.mids, data.freqs_a))
        sb = prepare_summary(stt.summarize_grouped_from_freq(data.mids, data.freqs_b))
    else:
        sa = prepare_summary(stt.summarize_ungrouped(list(data.raw_a)))
        sb = prepare_summary(stt.summarize_ungrouped(list(data.raw_b)))
    return sa, sb


def fmt(value: Any) -> str:
    """Định dạng số đặc trưng theo SGK (tối đa 4 chữ số có nghĩa); NaN → '—'."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return "—" if isnan(number) else f"{number:,.4g}"


# ---------------------------------------------------------------------------
# Khung chu trình dạy: bước học (đặt câu hỏi → dự đoán → đối chiếu → chốt)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PredictField:
    """Một ô dự đoán: ``answer_key`` trỏ vào dict số đặc trưng của bộ dữ liệu."""

    label: str
    answer_key: str
    series: str  # "a" | "b"


@dataclass(frozen=True)
class StepSpec:
    """Một bước của chu trình dạy; ``reveal`` dựng phần chốt từ số đã tính.

    ``latex``/``latex_note`` là công thức bám SGK kèm chú giải ký hiệu;
    ``casio`` là hướng dẫn bấm máy fx-580VN X / fx-880BTG cho bước đó.
    """

    step_id: str
    title: str
    question: str
    hint: str
    fields: tuple[PredictField, ...]
    reveal: Callable[[dict, dict], str]
    latex: str = ""
    latex_note: str = ""
    casio: str = ""


def field_answer(field: PredictField, sa: dict, sb: dict) -> float:
    """Đáp án của ô dự đoán tính từ dataset đang dùng (không dùng số cứng)."""

    source = sa if field.series == "a" else sb
    return float(source[field.answer_key])


def _r10_reveal_step1(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** x̄ của A = **{fmt(sa['mean'])}**%/phiên; x̄ của B = "
        f"**{fmt(sb['mean'])}**%/phiên. Hai cổ phiếu cùng mức lãi trung bình mỗi phiên.\n\n"
        "**Chốt:** nếu chỉ nhìn số trung bình, A và B không thể phân biệt. "
        "Trung bình chỉ là nửa đầu câu chuyện — cần thêm số đo độ phân tán."
    )


def _r10_reveal_step2(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** Me của A = **{fmt(sa['median'])}**, Mo của A = "
        f"**{fmt(sa['mode'])}** (giá trị xuất hiện nhiều nhất). Me của B = "
        f"**{fmt(sb['median'])}**, Mo của B = **{fmt(sb['mode'])}**.\n\n"
        "**Chốt:** các số trung tâm gần như trùng nhau — vẫn chưa có dấu hiệu "
        "nào để chọn giữa A và B."
    )


def _r10_reveal_step3(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** khoảng biến thiên R: A = **{fmt(sa['range'])}**, B = "
        f"**{fmt(sb['range'])}**; khoảng tứ phân vị ΔQ: A = **{fmt(sa['iqr'])}**, "
        f"B = **{fmt(sb['iqr'])}**.\n\n"
        "**Chốt:** B dao động rộng hơn hẳn A. Cùng trung bình nhưng mỗi phiên "
        "của B lệch khỏi trung bình nhiều hơn — đây là khác biệt quan trọng nhất."
    )


def _r10_reveal_step4(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** s² của A = **{fmt(sa['variance'])}** (s ≈ {fmt(sa['std'])}); "
        f"s² của B = **{fmt(sb['variance'])}** (s ≈ {fmt(sb['std'])}).\n\n"
        "**Chốt:** s của B gấp khoảng " + (f"{float(sb['std']) / float(sa['std']):.1f}" if float(sa["std"]) else "nhiều") +
        " lần s của A. Độ lệch chuẩn chính là con số đứng sau nhãn "
        "“Biến động năm hóa” ở tab Đầu tư."
    )


def _r10_reveal_step5(sa: dict, sb: dict) -> str:
    outliers_a = ", ".join(f"{v:g}" for v in sa["outliers"]) if sa["outliers"] else "không có"
    outliers_b = ", ".join(f"{v:g}" for v in sb["outliers"]) if sb["outliers"] else "không có"
    return (
        f"**Đối chiếu:** ngưỡng 1,5·ΔQ của A là [{fmt(sa['fence_low'])}; {fmt(sa['fence_high'])}] "
        f"→ giá trị bất thường: **{outliers_a}**. Ngưỡng của B là [{fmt(sb['fence_low'])}; "
        f"{fmt(sb['fence_high'])}] → giá trị bất thường: **{outliers_b}**.\n\n"
        "**Chốt:** mẫu càng trải rộng thì càng ít giá trị bị coi là lạ. Giá trị "
        "bất thường là phiên đáng dò tin tức, chưa chắc là dữ liệu lỗi."
    )


# ---------------------------------------------------------------------------
# Hướng dẫn bấm máy Casio fx-580VN X / fx-880BTG (theo hướng dẫn chính thức
# của Casio: fx-580VN X qua OPTN → 1-Variable Calc; fx-880BTG qua TOOLS →
# 1-Var Results; bật cột tần số qua SETUP/TOOLS → Frequency On)
# ---------------------------------------------------------------------------

_CASIO_R10_STEP1 = (
    "**Bấm máy với dãy thô 10 số** (fx-580VN X và fx-880BTG thao tác giống nhau):\n\n"
    "1. Vào ứng dụng **Statistics**: fx-580VN X bấm `MENU` → chọn Statistics; "
    "fx-880BTG bấm `Home` → chọn Statistics. Chọn **1-Variable**.\n"
    "2. Nhập lần lượt 10 lợi suất của A vào cột `x`, mỗi số xong nhấn `=`. "
    "Số âm bấm phím `(-)` trước số; thập phân dùng dấu chấm, ví dụ `0.2`.\n"
    "3. Nhấn `AC`, rồi `OPTN` → `1-Variable Calc` (fx-880BTG: `TOOLS` → "
    "`1-Var Results`). Cuộn bằng `↓` để đọc hết danh sách số đặc trưng.\n"
    "4. Kiểm tra dòng `n` phải bằng 10 — thiếu là nhập thiếu phiên.\n\n"
    "**Ký hiệu SGK và ký hiệu trên máy** (dùng cho mọi bước sau):\n\n"
    "| SGK | Trên máy | Lưu ý |\n"
    "|---|---|---|\n"
    "| x̄ | `x̄` | giống nhau |\n"
    "| s² (chia n) | `σ²x` | máy chia n — đúng công thức SGK |\n"
    "| s | `σx` | |\n"
    "| s′² (chia n − 1) | `s²x` | phương sai hiệu chỉnh (Toán 12) — đừng nhầm |\n"
    "| Me | `Med` | máy viết tắt |\n"
    "| Q₁, Q₃ | `Q1`, `Q3` | máy không in chỉ số dưới |\n"
    "| Mo | — | máy không có mốt: tự đếm giá trị lặp lại |\n"
    "| x_max, x_min | `maxX`, `minX` | dùng tính R |\n\n"
    "**Đọc ở bước này:** dòng `x̄` là số trung bình của A. Sang bộ B: `OPTN` → "
    "`Data` (fx-880BTG: quay về Bộ soạn thảo), chọn ô → `DEL` → nhập số mới."
)

_CASIO_R11_STEP1 = (
    "**Cảnh báo quan trọng:** với mẫu ghép nhóm, máy chỉ tính được x̄g và s_g "
    "(bước 1 và bước 5). Máy **không** nội suy được Me, Mo, Q₁, Q₃ theo công "
    "thức SGK — các bước 2, 3, 4 phải làm tay. Trên màn hình vẫn hiện `Med`, "
    "`Q1`, `Q3`, nhưng đó là số tính từ dãy trung điểm lặp theo tần số, không "
    "phải nội suy theo biên nhóm — lấy vào bài là sai.\n\n"
    "**Ký hiệu SGK và ký hiệu trên máy** (mẫu ghép nhóm):\n\n"
    "| SGK | Trên máy | Lưu ý |\n"
    "|---|---|---|\n"
    "| x̄g | `x̄` | nhập trung điểm + tần số, máy chia N |\n"
    "| s²g (chia N) | `σ²x` | đúng công thức SGK |\n"
    "| s_g | `σx` | |\n"
    "| s′² (chia N − 1) | `s²x` | phương sai hiệu chỉnh — đừng dùng |\n"
    "| Me, Mo, Q₁, Q₃ nội suy | — | máy không tính được: làm tay |\n\n"
    "**Bấm máy cho bộ A:**\n\n"
    "1. Bật cột tần số: fx-580VN X bấm `SHIFT` → `MENU` (SETUP) → `Statistics` "
    "→ `On`; fx-880BTG bấm `TOOLS` → `Frequency` → `On`.\n"
    "2. Vào **Statistics** → **1-Variable**; nhập 6 trung điểm `−2.5, −1.5, "
    "−0.5, 0.5, 1.5, 2.5` vào cột `x` (số âm bấm `(-)`).\n"
    "3. Nhập `5, 10, 25, 35, 20, 5` vào cột `Freq`.\n"
    "4. `AC` → `OPTN` → `1-Variable Calc` (fx-880BTG: `AC` → `TOOLS` → "
    "`1-Var Results`); kiểm tra `n` = 100.\n\n"
    "**Đọc ở bước này:** dòng `x̄` là x̄g của A. Sang bộ B: quay về bảng dữ "
    "liệu, sửa cột `Freq` thành `5, 10, 40, 10, 25, 10`."
)


def room10_steps() -> tuple[StepSpec, ...]:
    """Năm bước dạy Toán 10 (B13–B14), bổ sung mạch sâu từ kịch bản Toán 11."""

    return (
        StepSpec(
            step_id="mean",
            title="Bước 1 — Số trung bình: hai cổ phiếu “thường được bao nhiêu”?",
            question=(
                "Dùng công thức x̄ = (x₁ + … + xₙ)/n, tính số trung bình lợi suất "
                "ngày của A và của B. Hai cổ phiếu khác nhau nhiều không?"
            ),
            hint="Cộng 10 số của từng bộ rồi chia cho n = 10. Dấu âm là phiên lỗ.",
            fields=(PredictField("x̄ của A", "mean", "a"),
                    PredictField("x̄ của B", "mean", "b")),
            reveal=_r10_reveal_step1,
            latex=r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i",
            latex_note="x̄ đọc là “x gạch”; n là cỡ mẫu — ở đây n = 10 phiên.",
            casio=_CASIO_R10_STEP1,
        ),
        StepSpec(
            step_id="center",
            title="Bước 2 — Trung vị và mốt: số đứng giữa và số lặp lại",
            question=(
                "Xếp từng bộ từ nhỏ đến lớn để tìm trung vị Me; đếm giá trị lặp "
                "lại nhiều nhất để tìm mốt Mo. Có gì khác giữa A và B chưa?"
            ),
            hint="Mỗi bộ có 10 số nên Me là trung bình cộng của số thứ 5 và thứ 6.",
            fields=(PredictField("Me của A", "median", "a"),
                    PredictField("Me của B", "median", "b"),
                    PredictField("Mo của A", "mode", "a"),
                    PredictField("Mo của B", "mode", "b")),
            reveal=_r10_reveal_step2,
            latex=(r"\text{Me} = \frac{x_{(n/2)} + x_{(n/2+1)}}{2}"
                   r" \qquad \text{Mo} = \text{giá trị xuất hiện nhiều nhất}"),
            latex_note=(
                "Với n chẵn, Me là trung bình cộng của số thứ n/2 và n/2 + 1 "
                "trong dãy đã xếp thứ tự; Mo là giá trị có tần số xuất hiện lớn nhất."
            ),
            casio=(
                "**Đọc ở bước này:** dòng `Med` trên máy chính là Me — dùng kiểm "
                "tra kết quả làm trên giấy.\n\n"
                "Máy **không có mốt (Mo)**: với dãy 10 số, tự đếm giá trị nào "
                "lặp lại nhiều nhất trên dãy đã xếp thứ tự (với bộ kịch bản A: "
                "0,2 lặp 4 lần → Mo = 0,2)."
            ),
        ),
        StepSpec(
            step_id="spread",
            title="Bước 3 — Khoảng biến thiên và khoảng tứ phân vị",
            question=(
                "Tính R = x_max − x_min và ΔQ = Q₃ − Q₁ cho từng bộ. Bộ nào "
                "“lênh đênh” xa trung bình hơn?"
            ),
            hint="Q₁, Q₃ là trung vị của nửa trái và nửa phải sau khi xếp thứ tự.",
            fields=(PredictField("R của A", "range", "a"),
                    PredictField("R của B", "range", "b"),
                    PredictField("ΔQ của A", "iqr", "a"),
                    PredictField("ΔQ của B", "iqr", "b")),
            reveal=_r10_reveal_step3,
            latex=r"R = x_{\max} - x_{\min} \qquad \Delta_Q = Q_3 - Q_1",
            latex_note="Q₁, Q₃ là tứ phân vị thứ nhất và thứ ba; ΔQ đọc là “đề-ta-Q”.",
            casio=(
                "**Đọc ở bước này:** R = `maxX` − `minX` — hai dòng cuối màn "
                "hình kết quả, trừ trực tiếp trên máy.\n\n"
                "**Chú ý với `Q1`, `Q3`:** máy tính tứ phân vị theo quy tắc "
                "riêng của Casio (tài liệu máy không công bố chi tiết), còn "
                "SGK tính bằng cách lấy trung vị của nửa trái và nửa phải. "
                "Hai cách có thể cho số khác nhau với một số mẫu. Bài theo "
                "SGK — nhất là bước 5 dưới đây — hãy lấy kết quả làm trên "
                "giấy theo SGK làm chuẩn; số trên máy chỉ để tham khảo nhanh."
            ),
        ),
        StepSpec(
            step_id="std",
            title="Bước 4 — Phương sai và độ lệch chuẩn",
            question=(
                "Tính s² và s cho từng bộ. Cặp số này nói gì mà R và ΔQ chưa "
                "nói được?"
            ),
            hint=(r"Dùng $s^2 = \frac{1}{n}\sum(x_i - \bar{x})^2$ rồi "
                  r"$s = \sqrt{s^2}$. Nhớ chia cho n chứ không phải n − 1."),
            fields=(PredictField("s² của A", "variance", "a"),
                    PredictField("s² của B", "variance", "b"),
                    PredictField("s của A", "std", "a"),
                    PredictField("s của B", "std", "b")),
            reveal=_r10_reveal_step4,
            latex=r"s^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2 \qquad s = \sqrt{s^2}",
            latex_note="Công thức SGK chia cho n (không phải n − 1).",
            casio=(
                "**Đọc ở bước này:** `σ²x` chính là s² của SGK, `σx` là s "
                "(máy chia cho n — trùng công thức SGK).\n\n"
                "**Đừng nhầm:** dòng `s²x`, `sx` chia cho n − 1 — đó là phương "
                "sai/độ lệch chuẩn hiệu chỉnh (học ở Toán 12). Lấy nhầm dòng "
                "này là đáp án lệch ngay."
            ),
        ),
        StepSpec(
            step_id="outlier",
            title="Bước 5 — Giá trị bất thường theo quy tắc 1,5·ΔQ",
            question=(
                "Tính hai biên [Q₁ − 1,5ΔQ; Q₃ + 1,5ΔQ] của A. Những phiên nào "
                "của A nằm ngoài biên? Bộ B thì sao?"
            ),
            hint="Dùng ΔQ đã tính ở bước 3; phiên nằm ngoài biên là “đáng dò lại”.",
            fields=(PredictField("biên dưới của A", "fence_low", "a"),
                    PredictField("biên trên của A", "fence_high", "a")),
            reveal=_r10_reveal_step5,
            latex=r"\text{ngoài khoảng } [Q_1 - 1{,}5\,\Delta_Q;\; Q_3 + 1{,}5\,\Delta_Q]",
            latex_note="Giá trị nằm ngoài hai biên gọi là giá trị bất thường.",
            casio=(
                "Máy không có hàm tính ngưỡng. Đã có Q₁, Q₃, ΔQ thì bấm như "
                "phép tính thường:\n"
                "- Biên dưới: `Q1 − 1.5 × (Q3 − Q1)` rồi `=`.\n"
                "- Biên trên: `Q3 + 1.5 × (Q3 − Q1)` rồi `=`.\n\n"
                "So từng phiên với hai biên: nằm ngoài biên là giá trị bất thường."
            ),
        ),
    )


def _r11_reveal_mean(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** x̄g của A = **{fmt(sa['mean'])}**%/phiên; x̄g của B = "
        f"**{fmt(sb['mean'])}**%/phiên — tính từ bảng: x̄g = (n₁c₁ + … + nₖcₖ)/N.\n\n"
        "**Chốt:** ghép nhóm vẫn giữ được trung tâm. Hai mẫu cùng trung bình "
        "— câu chuyện tiếp tục ở các số còn lại."
    )


def _r11_reveal_median(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** Me của A ≈ **{fmt(sa['median'])}** (nội suy trong nhóm "
        f"chứa vị trí N/2 = 50); Me của B ≈ **{fmt(sb['median'])}**.\n\n"
        "**Chốt:** cùng trung bình +0,2 nhưng trung vị của B âm — tức nửa "
        "“giữa” của B nghiêng về phía lỗ. Dãy B có đuôi trái dày hơn."
    )


def _r11_reveal_mode(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** Mo của A ≈ **{fmt(sa['mode'])}** (nhóm có tần số lớn nhất "
        f"n=35: [0;1), nội suy giữa hai nhóm kề); Mo của B ≈ **{fmt(sb['mode'])}** "
        f"(nhóm dày nhất n=40: [−1;0)).\n\n"
        "**Chốt:** đỉnh của A nằm bên phải 0, đỉnh của B nằm bên trái 0. "
        "Mốt nội suy cho biết nhóm nào “dồn” nhiều phiên nhất."
    )


def _r11_reveal_iqr(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** Q₁, Q₃ của A là {fmt(sa['q1'])} và {fmt(sa['q3'])} → "
        f"ΔQ của A = **{fmt(sa['iqr'])}**. Q₁, Q₃ của B là {fmt(sb['q1'])} và "
        f"{fmt(sb['q3'])} → ΔQ của B = **{fmt(sb['iqr'])}**.\n\n"
        "**Chốt:** 50% phiên ở giữa của B trải rộng hơn A — phân tán cao hơn "
        "đã lộ ra từ tứ phân vị."
    )


def _r11_reveal_std(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** s²g của A = **{fmt(sa['variance'])}** (s_g ≈ {fmt(sa['std'])}); "
        f"s²g của B = **{fmt(sb['variance'])}** (s_g ≈ {fmt(sb['std'])}).\n\n"
        "**Chốt:** s_g của B lớn hơn A — cùng trung bình, B rủi ro hơn. "
        "Đây là số nối thẳng sang Toán 12 và nhãn “Biến động” ở tab Đầu tư."
    )


def room11_steps() -> tuple[StepSpec, ...]:
    """Năm bước dạy Toán 11: trung tâm của mẫu ghép nhóm từ bảng tần số."""

    return (
        StepSpec(
            step_id="mean",
            title="Bước 1 — Trung bình cộng có trọng số x̄g",
            question=(
                "Nhân tần số với giá trị đại diện c (trung điểm) của từng nhóm, "
                "cộng lại rồi chia cho N = 100. Tính x̄g của A và của B."
            ),
            hint="Làm trên bảng tần số: 5·(−2,5) + 10·(−1,5) + … rồi chia 100.",
            fields=(PredictField("x̄g của A", "mean", "a"),
                    PredictField("x̄g của B", "mean", "b")),
            reveal=_r11_reveal_mean,
            latex=(r"\bar{x}_g = \frac{n_1 c_1 + n_2 c_2 + \dots + n_k c_k}{N}"
                   r" = \frac{1}{N}\sum_{i=1}^{k} n_i c_i"),
            latex_note=(
                "cᵢ là trung điểm nhóm i; nᵢ là tần số nhóm i; N = n₁ + … + nₖ "
                "là tổng tần số. Chỉ số g ghi nhớ “ghép nhóm”."
            ),
            casio=_CASIO_R11_STEP1,
        ),
        StepSpec(
            step_id="median",
            title="Bước 2 — Trung vị Me nội suy trong nhóm chứa vị trí N/2",
            question=(
                "Tìm nhóm chứa vị trí N/2 = 50 (đọc tần số tích lũy), rồi nội "
                r"suy theo $\text{Me} = u + \frac{\frac{N}{2} - c_f}{n}\cdot w$ "
                "cho A và B."
            ),
            hint="A: tần số tích lũy trước nhóm [0;1) là 40, nhóm đó có n = 35.",
            fields=(PredictField("Me của A", "median", "a"),
                    PredictField("Me của B", "median", "b")),
            reveal=_r11_reveal_median,
            latex=r"\text{Me} = u + \frac{\frac{N}{2} - c_f}{n}\cdot w",
            latex_note=(
                "u: biên dưới nhóm chứa vị trí N/2; c_f: tần số tích lũy của "
                "nhóm liền trước; n: tần số của nhóm chứa N/2; w: độ rộng nhóm "
                "(ở đây w = 1)."
            ),
            casio=(
                "Máy không tính được Me nội suy của mẫu ghép nhóm (dòng `Med` "
                "trên màn hình chỉ dành cho dãy thô). Làm tay: cộng dồn tần số "
                "tích lũy để tìm nhóm chứa vị trí N/2 = 50, rồi thay u, c_f, "
                "n, w vào công thức. Máy giúp phần số học sau khi đã xác định "
                "đủ các số."
            ),
        ),
        StepSpec(
            step_id="mode",
            title="Bước 3 — Mốt Mo nội suy của nhóm dày nhất",
            question=(
                "Nhóm có tần số lớn nhất của A là [0;1) (n=35), của B là [−1;0) "
                "(n=40). Nội suy mốt theo công thức SGK cho từng bộ."
            ),
            hint=(r"Thay số vào $\text{Mo} = u + w \cdot "
                  r"\frac{n - n_-}{(n - n_-) + (n - n_+)}$ với nhóm có tần số lớn nhất."),
            fields=(PredictField("Mo của A", "mode", "a"),
                    PredictField("Mo của B", "mode", "b")),
            reveal=_r11_reveal_mode,
            latex=r"\text{Mo} = u + w \cdot \frac{n - n_-}{(n - n_-) + (n - n_+)}",
            latex_note=(
                "n: tần số nhóm chứa mốt; n₋ / n₊: tần số nhóm liền trước / "
                "liền sau; u: biên dưới nhóm chứa mốt. Áp dụng khi nhóm chứa "
                "mốt có cả hai nhóm kề."
            ),
            casio=(
                "Máy không có mốt. Tìm nhóm có tần số lớn nhất trên bảng (bộ "
                "A: nhóm [0;1) với n = 35), rồi nội suy theo công thức SGK; "
                "dùng máy cho phép nhân/chia sau khi thay số."
            ),
        ),
        StepSpec(
            step_id="iqr",
            title="Bước 4 — Tứ phân vị và khoảng tứ phân vị nội suy",
            question=(
                "Nội suy Q₁ tại vị trí N/4 = 25 và Q₃ tại 3N/4 = 75 cho từng "
                "bộ, rồi tính ΔQ = Q₃ − Q₁."
            ),
            hint="Cùng công thức nội suy với Me, chỉ đổi vị trí cần tìm.",
            fields=(PredictField("ΔQ của A", "iqr", "a"),
                    PredictField("ΔQ của B", "iqr", "b")),
            reveal=_r11_reveal_iqr,
            latex=(r"\begin{gathered}"
                   r"Q_1 = u + \frac{\frac{N}{4} - c_f}{n}\cdot w \qquad "
                   r"Q_3 = u + \frac{\frac{3N}{4} - c_f}{n}\cdot w \\"
                   r"\Delta_Q = Q_3 - Q_1"
                   r"\end{gathered}"),
            latex_note=(
                "Cùng công thức nội suy với Me, thay N/2 bằng N/4 (Q₁) hoặc "
                "3N/4 (Q₃); u, c_f, n tính theo nhóm chứa vị trí tương ứng."
            ),
            casio=(
                "Như Me: máy không nội suy được Q₁, Q₃ của mẫu ghép nhóm. Đọc "
                "tần số tích lũy để tìm nhóm chứa N/4 = 25 và 3N/4 = 75 rồi "
                "thay số vào công thức."
            ),
        ),
        StepSpec(
            step_id="std",
            title="Bước 5 — Phương sai và độ lệch chuẩn của mẫu ghép nhóm",
            question=(
                r"Tính $s_g^2 = \frac{1}{N}\sum n_i (c_i - \bar{x}_g)^2$ rồi "
                r"$s_g = \sqrt{s_g^2}$ cho A và B. Bộ nào phân tán mạnh hơn?"
            ),
            hint="Dùng trung điểm c và tần số n của từng nhóm; chia cho N = 100.",
            fields=(PredictField("s²g của A", "variance", "a"),
                    PredictField("s²g của B", "variance", "b"),
                    PredictField("s_g của A", "std", "a"),
                    PredictField("s_g của B", "std", "b")),
            reveal=_r11_reveal_std,
            latex=(r"\begin{gathered}"
                   r"s_g^2 = \frac{1}{N}\sum_{i=1}^{k} n_i \left(c_i - \bar{x}_g\right)^2 \\"
                   r"s_g = \sqrt{s_g^2}"
                   r"\end{gathered}"),
            latex_note=(
                "Thay xᵢ bằng trung điểm cᵢ, thêm trọng số tần số nᵢ và chia "
                "cho N. s²g mất đơn vị % (bị bình phương); s_g giữ lại đơn vị %."
            ),
            casio=(
                "**Đọc ở bước này** (đã nhập trung điểm + tần số như bước 1): "
                "`σ²x` là s²g và `σx` là s_g; kiểm tra `n` = 100.\n\n"
                "**Đừng nhầm:** dòng `s²x`, `sx` chia cho N − 1 (phương sai "
                "hiệu chỉnh, Toán 12) — không phải công thức SGK."
            ),
        ),
    )


def _r12_reveal_iqr(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** ΔQ của A = **{fmt(sa['iqr'])}** (Q₁ = {fmt(sa['q1'])}, "
        f"Q₃ = {fmt(sa['q3'])}); ΔQ của B = **{fmt(sb['iqr'])}** (Q₁ = {fmt(sb['q1'])}, "
        f"Q₃ = {fmt(sb['q3'])}).\n\n"
        "**Chốt:** khoảng tứ phân vị đo độ rộng của “50% phiên bình thường” — "
        "bỏ qua 25% lớn nhất và 25% nhỏ nhất nên ít bị phiên cực đoan làm lệch."
    )


def _r12_reveal_variance(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** s²g của A = **{fmt(sa['variance'])}**; s²g của B = "
        f"**{fmt(sb['variance'])}**.\n\n"
        "**Chốt:** phương sai lớn nghĩa là các phiên rải xa trung bình hơn. "
        "Vì đã bình phương, đơn vị của s²g không còn là % — đó là lý do cần s_g."
    )


def _r12_reveal_std(sa: dict, sb: dict) -> str:
    return (
        f"**Đối chiếu:** s_g của A ≈ **{fmt(sa['std'])}**; s_g của B ≈ "
        f"**{fmt(sb['std'])}**.\n\n"
        "**Chốt:** s_g cùng đơn vị với lợi suất (%), đọc trực tiếp: mỗi phiên "
        "của B thường lệch khỏi trung bình cỡ 1,35 điểm %, của A cỡ 1,19."
    )


def _r12_reveal_money(sa: dict, sb: dict) -> str:
    money_b = float(sb["std"])
    return (
        f"**Đối chiếu:** trên vốn 100 triệu, 1 điểm % = 1 triệu đồng, nên một "
        f"phiên của B thường lệch khỏi trung bình khoảng **{money_b:,.2f} triệu đồng** "
        f"(và của A khoảng {float(sa['std']):,.2f} triệu).\n\n"
        "**Chốt:** đây chỉ là quy đổi thẳng để cảm nhận độ lớn — không cộng "
        "lãi kép, không phải dự báo. Phiên lỗ có thể lệch nhiều hơn mức này."
    )


def room12_steps() -> tuple[StepSpec, ...]:
    """Bốn bước dạy Toán 12: phân tán của mẫu ghép nhóm và quy đổi cảm nhận."""

    return (
        StepSpec(
            step_id="iqr",
            title="Bước 1 — Khoảng tứ phân vị ΔQ của mẫu ghép nhóm",
            question=(
                "Nội suy Q₁ tại N/4 = 25 và Q₃ tại 3N/4 = 75 cho bảng tần số "
                "của A và B, rồi tính ΔQ."
            ),
            hint="Đọc tần số tích lũy để tìm nhóm chứa vị trí cần tìm.",
            fields=(PredictField("ΔQ của A", "iqr", "a"),
                    PredictField("ΔQ của B", "iqr", "b")),
            reveal=_r12_reveal_iqr,
            latex=(r"\begin{gathered}"
                   r"Q_1 = u + \frac{\frac{N}{4} - c_f}{n}\cdot w \qquad "
                   r"Q_3 = u + \frac{\frac{3N}{4} - c_f}{n}\cdot w \\"
                   r"\Delta_Q = Q_3 - Q_1"
                   r"\end{gathered}"),
            latex_note=(
                "Cùng công thức nội suy với Me, thay N/2 bằng N/4 (Q₁) hoặc "
                "3N/4 (Q₃); u, c_f, n tính theo nhóm chứa vị trí tương ứng."
            ),
            casio=(
                "Như phòng Toán 11: máy không nội suy được Q₁, Q₃ của mẫu ghép "
                "nhóm — làm tay theo công thức SGK, máy dùng cho phần số học."
            ),
        ),
        StepSpec(
            step_id="variance",
            title="Bước 2 — Phương sai s²g của mẫu ghép nhóm",
            question=(
                "Dùng trung điểm c và tần số n của từng nhóm, tính "
                r"$s_g^2 = \frac{1}{N}\sum n_i (c_i - \bar{x}_g)^2$ cho A và B."
            ),
            hint="x̄g đã tính ở phòng Toán 11: cả hai bộ đều là 0,2.",
            fields=(PredictField("s²g của A", "variance", "a"),
                    PredictField("s²g của B", "variance", "b")),
            reveal=_r12_reveal_variance,
            latex=r"s_g^2 = \frac{1}{N}\sum_{i=1}^{k} n_i \left(c_i - \bar{x}_g\right)^2",
            latex_note="x̄g lấy từ phòng Toán 11 (cả hai bộ đều bằng 0,2); chia cho N = 100.",
            casio=(
                "Đã nhập trung điểm + tần số vào máy: dòng `σ²x` là s²g. Đừng "
                "lấy dòng `s²x` (máy chia cho N − 1)."
            ),
        ),
        StepSpec(
            step_id="std",
            title="Bước 3 — Độ lệch chuẩn s_g",
            question="Lấy căn s²g để có s_g của A và B. Cùng đơn vị với gì?",
            hint="s_g = √s²g; cùng đơn vị với lợi suất (%) nên đọc trực tiếp được.",
            fields=(PredictField("s_g của A", "std", "a"),
                    PredictField("s_g của B", "std", "b")),
            reveal=_r12_reveal_std,
            latex=r"s_g = \sqrt{s_g^2}",
            latex_note="s_g cùng đơn vị với lợi suất (%) nên đọc trực tiếp được.",
            casio="Đọc dòng `σx` — đó là s_g, cùng đơn vị %. Dùng số này cho bước 4.",
        ),
        StepSpec(
            step_id="money",
            title="Bước 4 — Quy đổi ra tiền để cảm nhận rủi ro",
            question=(
                "Giả định vốn 100 triệu đồng, quy đổi 1 điểm % = 1 triệu đồng. "
                "Một phiên của B thường lệch khỏi trung bình khoảng bao nhiêu "
                "triệu đồng (dùng s_g của B)?"
            ),
            hint="Nhân s_g của B với 1 triệu đồng/1 điểm %.",
            fields=(PredictField("số triệu đồng/phiên của B", "std", "b"),),
            reveal=_r12_reveal_money,
            latex=(r"\text{tiền lệch mỗi phiên} = s_g \times "
                   r"\frac{1\ \text{triệu đồng}}{1\ \text{điểm \%}}"),
            latex_note="Chỉ đúng khi vốn 100 triệu đồng: 1 điểm % của 100 triệu = 1 triệu đồng.",
            casio=(
                "Bước này chỉ là phép nhân sau khi đọc s_g: dòng `σx` × 1 "
                "(triệu đồng/điểm %). Ví dụ `σx` = 1.35 → mỗi phiên thường lệch "
                "khoảng 1,35 triệu đồng."
            ),
        ),
    )


def steps_for_room(room: str) -> tuple[StepSpec, ...]:
    """Các bước dạy của một phòng."""

    if room == ROOM_10:
        return room10_steps()
    if room == ROOM_11:
        return room11_steps()
    return room12_steps()


# ---------------------------------------------------------------------------
# Biểu đồ và bảng tổng kết
# ---------------------------------------------------------------------------

_SERIES_LABELS = ("A", "B")


def _long_frame_room10(data: RoomData) -> pd.DataFrame:
    rows = []
    for label, raw in zip(_SERIES_LABELS, (data.raw_a, data.raw_b)):
        for i, value in enumerate(raw, start=1):
            rows.append({"Cổ phiếu": label, "Phiên": i, "Lợi suất (%)": float(value)})
    return pd.DataFrame(rows)


def room10_charts(data: RoomData) -> tuple[go.Figure, go.Figure]:
    """Dot plot từng phiên và box plot so sánh hai cổ phiếu (Toán 10)."""

    long = _long_frame_room10(data)
    dots = px.scatter(long, x="Lợi suất (%)", y="Phiên", color="Cổ phiếu",
                      color_discrete_sequence=stt.CHART_COLORS[:2],
                      title="Mỗi phiên là một điểm: lợi suất trải thế nào?")
    dots.update_traces(marker=dict(size=11))
    dots.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    box = px.box(long, x="Cổ phiếu", y="Lợi suất (%)", color="Cổ phiếu",
                 color_discrete_sequence=stt.CHART_COLORS[:2], points="all",
                 title="Box plot: giữa, tứ phân vị và giá trị bất thường")
    box.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10),
                      showlegend=False)
    return dots, box


def _grouped_long(data: RoomData) -> tuple[pd.DataFrame, list[str]]:
    width = float(data.mids[1]) - float(data.mids[0])
    labels = []
    for i, m in enumerate(data.mids):
        lo, hi = float(m) - width / 2.0, float(m) + width / 2.0
        sep = "]" if i == len(data.mids) - 1 else ")"
        labels.append(f"[{lo:.4g}; {hi:.4g}{sep}")
    rows = []
    for label, freqs in zip(_SERIES_LABELS, (data.freqs_a, data.freqs_b)):
        for interval, freq in zip(labels, freqs):
            rows.append({"Khoảng": interval, "Tần số": float(freq), "Bộ dữ liệu": label})
    return pd.DataFrame(rows), labels


def grouped_charts(data: RoomData) -> tuple[go.Figure, go.Figure]:
    """Biểu đồ cột tần số theo nhóm và đường tần số tích lũy (ogive)."""

    long, labels = _grouped_long(data)
    width = float(data.mids[1]) - float(data.mids[0])
    upper = [float(m) + width / 2.0 for m in data.mids]
    rows = []
    for label, freqs in zip(_SERIES_LABELS, (data.freqs_a, data.freqs_b)):
        cumulative = 0
        for x, freq in zip(upper, freqs):
            cumulative += float(freq)
            rows.append({"Biên trên": x, "Tần số tích lũy": cumulative,
                         "Bộ dữ liệu": label})
    cumulative_df = pd.DataFrame(rows)
    bars = px.bar(long, x="Khoảng", y="Tần số", color="Bộ dữ liệu",
                  barmode="group", color_discrete_sequence=stt.CHART_COLORS[:2],
                  title="Tần số theo khoảng: số phiên rơi vào từng vùng lợi suất")
    bars.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    ogive = px.line(cumulative_df, x="Biên trên", y="Tần số tích lũy",
                    color="Bộ dữ liệu", markers=True,
                    color_discrete_sequence=stt.CHART_COLORS[:2],
                    title="Tần số tích lũy: đọc vị trí N/4, N/2, 3N/4")
    ogive.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    return bars, ogive


def summary_table(data: RoomData, sa: dict, sb: dict) -> pd.DataFrame:
    """Bảng tổng kết số đặc trưng của cả hai bộ dữ liệu."""

    if data.is_grouped:
        rows = [
            ("Số phiên N", sa["n_total"], sb["n_total"]),
            ("Trung bình x̄g", sa["mean"], sb["mean"]),
            ("Trung vị Me (nội suy)", sa["median"], sb["median"]),
            ("Mốt Mo (nội suy)", sa["mode"], sb["mode"]),
            ("Tứ phân vị Q₁", sa["q1"], sb["q1"]),
            ("Tứ phân vị Q₃", sa["q3"], sb["q3"]),
            ("Khoảng tứ phân vị ΔQ", sa["iqr"], sb["iqr"]),
            ("Khoảng biến thiên R (biên)", sa["range"], sb["range"]),
            ("Phương sai s²g", sa["variance"], sb["variance"]),
            ("Độ lệch chuẩn s_g", sa["std"], sb["std"]),
        ]
    else:
        def _outliers(summary: dict) -> str:
            return ", ".join(f"{v:g}" for v in summary["outliers"]) if summary["outliers"] else "—"

        rows = [
            ("Số phiên n", sa["n"], sb["n"]),
            ("Trung bình x̄", sa["mean"], sb["mean"]),
            ("Trung vị Me", sa["median"], sb["median"]),
            ("Mốt Mo", sa["mode"], sb["mode"]),
            ("Nhỏ nhất", sa["min"], sb["min"]),
            ("Lớn nhất", sa["max"], sb["max"]),
            ("Khoảng biến thiên R", sa["range"], sb["range"]),
            ("Tứ phân vị Q₁", sa["q1"], sb["q1"]),
            ("Tứ phân vị Q₃", sa["q3"], sb["q3"]),
            ("Khoảng tứ phân vị ΔQ", sa["iqr"], sb["iqr"]),
            ("Phương sai s²", sa["variance"], sb["variance"]),
            ("Độ lệch chuẩn s", sa["std"], sb["std"]),
            ("Giá trị bất thường", _outliers(sa), _outliers(sb)),
        ]
    return pd.DataFrame(rows, columns=("Số đặc trưng", data.names[0], data.names[1]))


# ---------------------------------------------------------------------------
# Exit ticket: 3 câu (1 khái niệm + 2 phép tính từ dataset đang dùng)
# ---------------------------------------------------------------------------

KIND_SINGLE = "single"
KIND_NUMBER = "number"


@dataclass(frozen=True)
class ExitQuestion:
    """Một câu hỏi exit ticket; câu số lấy đáp án từ dataset đang dùng."""

    qid: str
    prompt: str
    kind: str
    options: tuple[str, ...] = ()
    correct_index: int | None = None
    answer_key: str = ""      # khóa trong dict summary của bộ dữ liệu
    series: str = "a"         # "a" | "b" | "" (câu khái niệm)
    tolerance_pct: float = 1.0
    explanation: str = ""

    def answer(self, sa: dict, sb: dict) -> float:
        source = sa if self.series == "a" else sb
        return float(source[self.answer_key])

    def tolerance(self, sa: dict, sb: dict) -> float:
        return max(abs(self.answer(sa, sb)) * self.tolerance_pct / 100.0, 0.005)


def _q_conceptual_no_conclusion() -> ExitQuestion:
    return ExitQuestion(
        qid="q1", kind=KIND_SINGLE,
        prompt="Hai bộ dữ liệu có cùng số trung bình. Kết luận nào ĐÚNG?",
        options=(
            "Nên mua bộ A vì phân tán nhỏ hơn nên an toàn hơn",
            "Nên mua bộ B vì dao động mạnh nên cơ hội lãi lớn hơn",
            "Chưa thể khuyên mua bộ nào — mới chỉ biết hai bộ khác độ phân tán; "
            "quyết định còn phụ thuộc mục tiêu chịu rủi ro và dữ liệu dài hơn",
        ),
        correct_index=2,
        explanation=(
            "Phân tán nhỏ là mô tả thống kê của bộ dữ liệu ngắn, không phải "
            "khuyến nghị mua. Muốn khuyên ai đó mua còn cần mục tiêu, thời gian "
            "nắm giữ và dữ liệu đủ dài — đúng tinh thần Hội đồng tư vấn ở trên."
        ),
    )


def exit_questions(room: str) -> tuple[ExitQuestion, ...]:
    """Exit ticket của một phòng; câu tính lấy đáp án từ dataset đang dùng."""

    if room == ROOM_10:
        return (
            _q_conceptual_no_conclusion(),
            ExitQuestion(
                qid="q2", kind=KIND_NUMBER, answer_key="std", series="a",
                prompt="Độ lệch chuẩn s của bộ A bằng bao nhiêu (%/phiên)?",
                explanation="s = √s²; với bộ A s² = 0,056 nên s ≈ 0,2366.",
            ),
            ExitQuestion(
                qid="q3", kind=KIND_NUMBER, answer_key="iqr", series="b",
                prompt="Khoảng tứ phân vị ΔQ của bộ B bằng bao nhiêu?",
                explanation="ΔQ = Q₃ − Q₁ của B.",
            ),
        )
    if room == ROOM_11:
        return (
            ExitQuestion(
                qid="q1", kind=KIND_SINGLE,
                prompt="Mọi số đặc trưng tính từ bảng ghép nhóm là…",
                options=(
                    "số chính xác như tính từ dãy thô",
                    "số gần đúng, vì ghép nhóm đã bỏ chi tiết trong từng khoảng",
                    "số không dùng được khi báo cáo",
                ),
                correct_index=1,
                explanation=(
                    "Ghép nhóm thay cả khoảng bằng trung điểm nên mất chi tiết "
                    "trong khoảng — mọi số ghép nhóm là ước lượng (nối bài Số "
                    "gần đúng và sai số)."
                ),
            ),
            ExitQuestion(
                qid="q2", kind=KIND_NUMBER, answer_key="median", series="a",
                prompt="Trung vị Me (nội suy) của bộ A bằng bao nhiêu (%/phiên)?",
                explanation="Nội suy trong nhóm chứa vị trí N/2 = 50 của bộ A.",
            ),
            ExitQuestion(
                qid="q3", kind=KIND_NUMBER, answer_key="iqr", series="b",
                prompt="Khoảng tứ phân vị ΔQ (nội suy) của bộ B bằng bao nhiêu?",
                explanation="ΔQ = Q₃ − Q₁ nội suy của bộ B.",
            ),
        )
    return (
        ExitQuestion(
            qid="q1", kind=KIND_SINGLE,
            prompt="s_g của B lớn hơn s_g của A. Điều đó nói lên điều gì?",
            options=(
                "B chắc chắn lãi nhiều hơn A trong phiên sau",
                "Lợi suất của B rải xa trung bình hơn — biến động cao hơn",
                "A không đáng mua vì s_g nhỏ",
            ),
            correct_index=1,
            explanation=(
                "s_g đo mức rải quanh trung bình, không dự báo phiên sau và "
                "không xếp hạng “đáng mua”."
            ),
        ),
        ExitQuestion(
            qid="q2", kind=KIND_NUMBER, answer_key="std", series="a",
            prompt="Độ lệch chuẩn s_g của bộ A bằng bao nhiêu (%/phiên)?",
            explanation="s_g = √s²g của bộ A.",
        ),
        ExitQuestion(
            qid="q3", kind=KIND_NUMBER, answer_key="std", series="b",
            prompt="Trên vốn 100 triệu (1 điểm % = 1 triệu đồng), một phiên của "
                   "B thường lệch khỏi trung bình khoảng bao nhiêu triệu đồng?",
            explanation="Quy đổi thẳng: số triệu ≈ s_g của B (không cộng lãi kép).",
        ),
    )


def grade_exit(questions: tuple[ExitQuestion, ...], responses: dict[str, Any],
               sa: dict, sb: dict) -> tuple[int, dict[str, bool]]:
    """Chấm exit ticket: trả về (điểm 0–100, đúng/sai từng câu)."""

    correct: dict[str, bool] = {}
    for q in questions:
        response = responses.get(q.qid)
        if q.kind == KIND_SINGLE:
            ok = response is not None and response == q.correct_index
        else:
            ok = (
                response is not None
                and abs(float(response) - q.answer(sa, sb)) <= q.tolerance(sa, sb)
            )
        correct[q.qid] = bool(ok)
    score = round(sum(correct.values()) / len(questions) * 100.0)
    return score, correct


# ---------------------------------------------------------------------------
# Hiển thị (Streamlit)
# ---------------------------------------------------------------------------

_KEY_PREFIX = "qa_class"


def _render_data_source(room: str, prices: pd.DataFrame, market: str) -> RoomData | None:
    """Chọn nguồn dữ liệu: kịch bản (mặc định khi dạy), nhập tay, đã nạp."""

    has_data = prices is not None and not prices.empty
    if room == ROOM_10:
        scenario_label = "Bộ A/B theo kịch bản (10 phiên)"
        manual_label = "Nhập tay hai dãy"
    else:
        scenario_label = "Bảng tần số theo kịch bản (100 phiên)"
        manual_label = "Nhập tay bảng tần số"
    options = [scenario_label, manual_label] + (["Lấy từ dữ liệu đã nạp"] if has_data else [])
    source = st.radio(
        "Nguồn dữ liệu", options, index=0, horizontal=True,
        key=f"{_KEY_PREFIX}_source_{room}",
        help="Trong giờ dạy nên dùng bộ giả định để hiện tượng thống kê rõ ràng; "
             "dữ liệu thật dùng để vận dụng sau.",
    )
    try:
        if source == scenario_label:
            return scenario_data(room)
        if source == manual_label:
            if room == ROOM_10:
                left, right = st.columns(2)
                text_a = left.text_area(
                    "Lợi suất cổ phiếu A (%)", key=f"{_KEY_PREFIX}_manual_a_{room}",
                    help="Cách nhau bằng dấu phẩy hoặc xuống dòng.",
                )
                text_b = right.text_area(
                    "Lợi suất cổ phiếu B (%)", key=f"{_KEY_PREFIX}_manual_b_{room}",
                    help="Cách nhau bằng dấu phẩy hoặc xuống dòng.",
                )
                return room10_manual(text_a, text_b)
            left, right = st.columns((2, 1))
            mids_text = left.text_area(
                "Trung điểm các nhóm (cách đều)", key=f"{_KEY_PREFIX}_manual_mids_{room}",
                help="Ví dụ: -2.5, -1.5, -0.5, 0.5, 1.5, 2.5",
            )
            freqs_a = right.text_area("Tần số bộ A", key=f"{_KEY_PREFIX}_manual_fa_{room}")
            freqs_b = right.text_area("Tần số bộ B", key=f"{_KEY_PREFIX}_manual_fb_{room}")
            return room11_manual(mids_text, freqs_a, freqs_b)
        # Lấy từ dữ liệu đã nạp
        assets = [c for c in prices.columns if c != market]
        if room == ROOM_10:
            left, mid, right = st.columns(3)
            symbol_a = left.selectbox("Cổ phiếu A", assets, key=f"{_KEY_PREFIX}_real_a_{room}")
            symbol_b = mid.selectbox("Cổ phiếu B", assets, index=min(1, len(assets) - 1),
                                     key=f"{_KEY_PREFIX}_real_b_{room}")
            window = right.selectbox("Số phiên gần nhất", (10, 15, 20), index=0,
                                     key=f"{_KEY_PREFIX}_real_w_{room}")
            return room10_from_prices(prices, market, symbol_a, symbol_b, window)
        left, right = st.columns(2)
        symbol = left.selectbox("Mã cổ phiếu", assets, key=f"{_KEY_PREFIX}_real_s_{room}")
        window = right.selectbox(
            "Mỗi nửa giai đoạn bao nhiêu phiên", (30, 60, 90), index=0,
            key=f"{_KEY_PREFIX}_real_w_{room}",
            help="Dãy lợi suất được chia làm hai nửa để so sánh hai giai đoạn, "
                 "ghép nhóm với chung một lưới nhóm.",
        )
        return room11_from_prices(prices, market, symbol, window)
    except ValueError as exc:
        st.warning(str(exc))
        return None


def _render_step_controls(room: str, step: StepSpec, sa: dict, sb: dict) -> None:
    """Ô dự đoán + nút đối chiếu + phần chốt của một bước."""

    reveal_key = f"{_KEY_PREFIX}_reveal_{room}_{step.step_id}"
    st.markdown(f"#### {step.title}")
    st.markdown(step.question)
    st.caption(f"Gợi ý: {step.hint}")
    if step.latex:
        with st.expander("Công thức bám SGK"):
            st.latex(step.latex)
            if step.latex_note:
                st.caption(step.latex_note)
    if step.casio:
        with st.expander("Bấm máy Casio fx-580VN X / fx-880BTG"):
            st.markdown(step.casio)
    columns = st.columns(len(step.fields))
    predictions: list[float | None] = []
    for column, field in zip(columns, step.fields):
        with column:
            predictions.append(st.number_input(
                f"Dự đoán {field.label}", value=None, step=0.01,
                key=f"{_KEY_PREFIX}_pred_{room}_{step.step_id}_{field.answer_key}_{field.series}",
                help="Nhập kết quả tự tính trên giấy; để trống nếu chưa tính.",
            ))
    if st.button("Đối chiếu", type="primary",
                 key=f"{_KEY_PREFIX}_check_{room}_{step.step_id}"):
        st.session_state[reveal_key] = True
    if not st.session_state.get(reveal_key):
        return
    st.markdown("**Đối chiếu từng ô dự đoán:**")
    for prediction, field in zip(predictions, step.fields):
        answer = field_answer(field, sa, sb)
        if prediction is None:
            st.markdown(f"- {field.label}: chưa nhập — đáp án **{fmt(answer)}**.")
            continue
        gap = abs(float(prediction) - answer)
        tolerance = max(abs(answer) * 0.01, 0.005)
        if gap <= tolerance:
            st.markdown(f"- ✅ {field.label}: {prediction:,.4g} — khớp đáp án "
                        f"**{fmt(answer)}** (lệch {gap:,.4g}).")
        else:
            st.markdown(f"- ➡️ {field.label}: dự đoán {prediction:,.4g}, đáp án "
                        f"**{fmt(answer)}** (lệch {gap:,.4g}). Kiểm tra lại cách tính "
                        "theo gợi ý phía trên.")
    st.success(step.reveal(sa, sb))


def _render_charts(room: str, data: RoomData) -> None:
    left, right = st.columns(2)
    with left:
        if data.is_grouped:
            fig, _ = grouped_charts(data)
            st.plotly_chart(fig, key=f"{_KEY_PREFIX}_bar_{room}",
                            config={"displayModeBar": False})
        else:
            dots, _ = room10_charts(data)
            st.plotly_chart(dots, key=f"{_KEY_PREFIX}_dots_{room}",
                            config={"displayModeBar": False})
    with right:
        if data.is_grouped:
            _, ogive = grouped_charts(data)
            st.plotly_chart(ogive, key=f"{_KEY_PREFIX}_ogive_{room}",
                            config={"displayModeBar": False})
        else:
            _, box = room10_charts(data)
            st.plotly_chart(box, key=f"{_KEY_PREFIX}_box_{room}",
                            config={"displayModeBar": False})
    if data.is_grouped:
        st.caption("Đường tần số tích lũy giúp đọc nhanh vị trí N/4, N/2, 3N/4 — "
                   "chính là nơi nội suy Q₁, Me, Q₃.")
    else:
        st.caption("Box plot: cạnh hộp là Q₁, Me, Q₃; râu và điểm rơi ngoài râu "
                   "là chỗ giá trị bất thường hiện hình.")


def _render_summary_and_meaning(room: str, data: RoomData, sa: dict, sb: dict) -> None:
    st.markdown("### Bảng tổng kết số đặc trưng")
    st.dataframe(
        summary_table(data, sa, sb), hide_index=True, width="stretch",
        column_config={
            "Số đặc trưng": st.column_config.Column(width=210),
            data.names[0]: st.column_config.NumberColumn(data.names[0], width=130, format="%.4g"),
            data.names[1]: st.column_config.NumberColumn(data.names[1], width=130, format="%.4g"),
        },
    )
    if room == ROOM_10:
        question = ("Viết 2–3 câu so sánh hai cổ phiếu theo khung “trung tâm — "
                    "phân tán — giá trị lạ”, như một nhận xét trong báo cáo của em.")
        model = (
            f"Khung tham khảo: “Hai cổ phiếu đều có lợi suất trung bình "
            f"{fmt(sa['mean'])}%/phiên. Khác biệt nằm ở độ phân tán: s của "
            f"{data.names[0]} là {fmt(sa['std'])}, của {data.names[1]} là "
            f"{fmt(sb['std'])} — bộ sau dao động mạnh hơn hẳn. Nửa số liệu ở giữa "
            f"của {data.names[1]} trải trong [{fmt(sb['q1'])}; {fmt(sb['q3'])}] "
            f"so với [{fmt(sa['q1'])}; {fmt(sa['q3'])}] của {data.names[0]}. "
            f"Giá trị bất thường: {', '.join(f'{v:g}' for v in sa['outliers']) or '—'} "
            f"({data.names[0]}), {', '.join(f'{v:g}' for v in sb['outliers']) or '—'} "
            f"({data.names[1]}).”"
        )
        hint = ("Kể theo thứ tự: trung tâm (x̄, Me) → phân tán (s, ΔQ) → giá trị "
                "bất thường; mỗi ý kèm một nhận xét rủi ro cao hay thấp.")
        frame = ("“Câu 1: Cả hai cổ phiếu có x̄ ≈ ___. Câu 2: s của A = ___, của "
                 "B = ___ nên B dao động mạnh hơn. Câu 3: Giá trị bất thường của "
                 "A là ___, đáng dò tin tức.”")
    elif room == ROOM_11:
        question = ("Viết 2–3 câu so sánh trung tâm của hai mẫu ghép nhóm: vì "
                    "sao cùng x̄g mà trung vị và mốt lại lệch dấu?")
        model = (
            f"Khung tham khảo: “Hai mẫu cùng có x̄g = {fmt(sa['mean'])}%/phiên, "
            f"nhưng Me của {data.names[0]} là {fmt(sa['median'])} còn của "
            f"{data.names[1]} là {fmt(sb['median'])}, và Mo lần lượt {fmt(sa['mode'])} "
            f"và {fmt(sb['mode'])}. Điều đó cho thấy {data.names[1]} dồn phiên về "
            "phía lỗ nhiều hơn dù trung bình giống nhau. Mọi số ghép nhóm đều là "
            "ước lượng vì chi tiết trong từng khoảng đã bị bỏ.”"
        )
        hint = ("Đọc cả ba số trung tâm (x̄g, Me, Mo); nói rõ vì sao Me/Mo lệch "
                "dấu (tần số dồn về nhóm nào).")
        frame = ("“Câu 1: x̄g của hai bộ đều ___. Câu 2: Me của A ≈ ___, của B ≈ "
                 "___ nên ___. Câu 3: Mo của A ≈ ___, của B ≈ ___, nhóm dày nhất "
                 "lần lượt là ___ và ___.”")
    else:
        question = ("Viết 2–3 câu về độ phân tán của hai mẫu ghép nhóm và ý "
                    "nghĩa rủi ro khi quy đổi ra tiền.")
        model = (
            f"Khung tham khảo: “s_g của {data.names[0]} là {fmt(sa['std'])} và "
            f"của {data.names[1]} là {fmt(sb['std'])} điểm %; quy đổi trên vốn "
            f"100 triệu thì một phiên lệch khỏi trung bình cỡ "
            f"{float(sa['std']):,.2f} và {float(sb['std']):,.2f} triệu đồng. "
            "s_g nói về cỡ dao động, không nói phiên sau lên hay xuống; quy đổi "
            "không cộng lãi kép nên không thể hiểu là lãi đều hàng phiên.”"
        )
        hint = ("Tách rõ: s_g nói gì (cỡ dao động) và không nói gì (hướng, dự "
                "báo, lãi đều).")
        frame = ("“Câu 1: s_g của A ≈ ___, của B ≈ ___. Câu 2: Quy đổi ra tiền, "
                 "một phiên lệch cỡ ___ và ___ triệu. Câu 3: Không thể hiểu là "
                 "lãi đều vì ___.”")
    stt.meaning_block(f"{_KEY_PREFIX}_{room}", question, model, hint=hint, frame=frame)


def _render_reflection(room: str, data: RoomData, sa: dict, sb: dict) -> None:
    if room == ROOM_10:
        items = [
            ("Thêm một phiên +5% vào bộ A thì số nào đổi mạnh hơn: x̄ hay Me? Vì sao?",
             "x̄ bị kéo theo giá trị cực đại nên đổi rõ; Me dựa vào vị trí giữa nên "
             "gần như đứng yên. Mẫu có giá trị bất thường thì đọc kèm trung vị."),
            ("Từ s của A ≈ 0,24 và s của B ≈ 1,15, câu “A an toàn hơn nên nên mua A” "
             "sai ở chỗ nào?",
             "“An toàn hơn về phân tán” là mô tả của 10 phiên giả định, không phải "
             "khuyến nghị: còn thiếu mục tiêu người mua, thời gian nắm giữ và dữ "
             "liệu dài hơn. Mô tả ≠ khuyến nghị."),
        ]
    elif room == ROOM_11:
        items = [
            ("Vì sao Me của B âm trong khi x̄g của B là +0,2?",
             "Tần số của B dồn về các nhóm trái (n=40 ở [−1;0)) nên nửa “giữa” của "
             "dãy nằm dưới 0; tổng trung bình được kéo lên nhờ nhóm phải. Dãy lệch "
             "trái: trung bình và trung vị kể hai câu chuyện khác nhau."),
            ("Ghép nhóm làm mất thông tin gì, và khi nào không nên tin số ghép nhóm?",
             "Mất chi tiết các số trong từng khoảng. Nhóm có tần số dồn về một đầu "
             "hoặc khoảng quá rộng thì trung điểm đại diện kém — số ghép nhóm chỉ "
             "đáng tin khi dữ liệu rải tương đối đều trong nhóm."),
        ]
    else:
        items = [
            ("s_g nói gì và KHÔNG nói gì về phiên kế tiếp?",
             "Nói: cỡ dao động quanh trung bình. Không nói: hướng phiên sau, xác "
             "suất lãi/lỗ cụ thể, mức lỗ tối đa. Muốn đo mức lỗ cần học thêm bài "
             "Rủi ro và đa dạng hóa."),
            ("Quy đổi 1 điểm % = 1 triệu đồng trên vốn 100 triệu — sai lầm nếu đọc "
             "thành “lãi đều 1,35 triệu mỗi phiên”?",
             "Dao động là hai chiều: có phiên lệch dương, có phiên lệch âm, và có "
             "phiên lệch xa hơn s_g nhiều. Cộng dồn theo kiểu lãi đều là hiểu sai "
             "cả đơn vị lẫn bản chất của độ lệch chuẩn."),
        ]
    stt.reflection_block(items)


def _render_advice_board(room: str, data: RoomData, sa: dict, sb: dict) -> None:
    """Hội đồng tư vấn đầu tư có trách nhiệm — chốt bằng khung câu có cấu trúc."""

    st.markdown("### 🏛️ Hội đồng tư vấn đầu tư có trách nhiệm")
    st.markdown(
        "Nhiệm vụ của em: viết một đoạn khuyến nghị ngắn cho người mới, dựa "
        "**đúng** vào các số vừa tính và ghi rõ giới hạn của dữ liệu."
    )
    st.text_area(
        "Khuyến nghị của hội đồng (2–3 câu)", key=f"{_KEY_PREFIX}_advice_{room}",
        placeholder="Viết trước, rồi mới mở đáp án mẫu…",
    )
    if room == ROOM_10:
        spread_note = (
            f"s của {data.names[0]} là {fmt(sa['std'])} và của {data.names[1]} là "
            f"{fmt(sb['std'])}"
        )
    else:
        spread_note = (
            f"s_g của {data.names[0]} là {fmt(sa['std'])} và của {data.names[1]} là "
            f"{fmt(sb['std'])}"
        )
    with st.expander("Đối chiếu khuyến nghị mẫu"):
        st.markdown(
            f"“Cả hai bộ dữ liệu có lợi suất trung bình ≈ {fmt(sa['mean'])}%/phiên; "
            f"khác biệt nằm ở độ phân tán: {spread_note}. Với người ngại biến "
            f"động, {data.names[0]} đi êm hơn trên bộ dữ liệu này; người chấp "
            f"nhận dao động để tìm cơ hội thì phải chấp nhận cả những phiên lỗ "
            f"rộng. **Khuyến nghị trên chỉ dựa trên "
            f"{'10 phiên' if not data.is_grouped else '100 phiên'} dữ liệu giả định "
            f"— chưa đủ để khuyên mua hay bán cụ thể.”**"
        )
        st.warning(
            "Tuyệt đối không kết luận “bộ an toàn hơn nên nên mua”: dữ liệu ngắn, "
            "giả định, và “an toàn hơn về thống kê” không bằng “đáng mua hơn”. "
            "Ứng dụng không đưa khuyến nghị đầu tư."
        )


def _render_exit_ticket(room: str, sa: dict, sb: dict) -> None:
    """Exit ticket 3 câu; điểm ghi vào bài học SGK tương ứng của hồ sơ."""

    lesson_id = ROOM_LESSON_IDS[room]
    st.markdown("### 🎫 Exit ticket")
    st.caption(
        "3 câu (1 câu khái niệm + 2 phép tính từ bộ dữ liệu đang dùng). Điểm "
        "lưu vào bài học SGK tương ứng trên máy em; khi em tham gia lớp có gói "
        "bài nộp gồm bài này, giáo viên sẽ nhận điểm khi nộp. Học ngoài lớp vẫn "
        "được lưu như bài học thường."
    )
    questions = exit_questions(room)
    state_key = f"{_KEY_PREFIX}_exit_{room}"
    with st.form(f"{state_key}_form"):
        responses: dict[str, Any] = {}
        for idx, q in enumerate(questions, start=1):
            st.markdown(f"**Câu {idx}.** {q.prompt}")
            if q.kind == KIND_SINGLE:
                responses[q.qid] = st.radio(
                    "Chọn một đáp án:", range(len(q.options)), index=None,
                    format_func=lambda i, opts=q.options: opts[i],
                    key=f"{state_key}_{q.qid}_r", label_visibility="collapsed",
                )
            else:
                responses[q.qid] = st.number_input(
                    "Nhập kết quả:", value=None, step=0.01, placeholder="Nhập số…",
                    key=f"{state_key}_{q.qid}_n", label_visibility="collapsed",
                )
        submitted = st.form_submit_button("Nộp exit ticket", type="primary")

    if submitted:
        score, correct = grade_exit(questions, responses, sa, sb)
        profile = st.session_state.setdefault("progress_profile", pp.empty_profile())
        try:
            pp.record_lesson_attempt(profile, lesson_id, score, correct)
        except ValueError as exc:
            st.warning(f"Không ghi được điểm vào hồ sơ: {exc}")
        st.session_state[state_key] = {"score": score, "correct": correct}

    feedback = st.session_state.get(state_key)
    if not feedback:
        return
    score = float(feedback["score"])
    if score >= cur.UNLOCK_THRESHOLD:
        st.success(f"Bạn được {score:.0f}/100 — đạt yêu cầu (từ {cur.UNLOCK_THRESHOLD:.0f}/100).")
    else:
        st.warning(f"Bạn được {score:.0f}/100 — cần từ {cur.UNLOCK_THRESHOLD:.0f} "
                   "điểm để đạt. Làm lại được, điểm lần nộp gần nhất được lưu.")
    for idx, (q, ok) in enumerate(zip(questions, feedback["correct"].values()), start=1):
        st.markdown(f"{'✅' if ok else '❌'} **Câu {idx}.** {q.explanation}")


def render_stats_classroom(prices: pd.DataFrame, market: str) -> None:
    """Phòng học thống kê: ba phòng riêng theo lớp, dạy theo chu trình kịch bản."""

    st.subheader("Phòng học thống kê")
    learner = lmode.get_learner_profile(st.session_state)
    grade = learner.get("grade_level")
    default_room = default_room_for_grade(grade)
    room = st.selectbox(
        "Phòng học — mỗi lần học một phòng", ROOM_ORDER,
        format_func=ROOM_LABELS.get, index=ROOM_ORDER.index(default_room),
        key=f"{_KEY_PREFIX}_room",
    )
    if grade in ROOM_ORDER:
        st.caption(f"Phòng mặc định theo lớp bạn đã chọn ({lmode.GRADE_LABELS[grade]}). "
                   "Muốn học chéo phòng khác thì đổi ở đây.")
    else:
        st.caption("Bạn chưa chọn lớp Toán cụ thể nên mặc định vào phòng Toán 10; "
                   "đổi phòng phía trên khi cần.")

    data = _render_data_source(room, prices, market)
    if data is None:
        return
    try:
        sa, sb = resolve_summaries(data)
    except ValueError as exc:
        st.warning(str(exc))
        return
    st.caption(f"Nguồn đang dùng: {data.source} — bộ {data.names[0]} và {data.names[1]}.")

    st.markdown(
        "🧭 **Mạch dạy:** đặt câu hỏi → tự tính trên giấy → nhập dự đoán → bấm "
        "**Đối chiếu** → đọc biểu đồ → nêu ý nghĩa → phản tư → chốt bằng Hội đồng "
        "tư vấn → exit ticket."
    )
    steps = steps_for_room(room)
    for step in steps:
        _render_step_controls(room, step, sa, sb)

    revealed_all = all(
        st.session_state.get(f"{_KEY_PREFIX}_reveal_{room}_{s.step_id}")
        for s in steps
    )
    if not revealed_all:
        st.info("Hoàn thành các bước đối chiếu để mở biểu đồ, bảng tổng kết và exit ticket.")
        return

    _render_charts(room, data)
    _render_summary_and_meaning(room, data, sa, sb)
    _render_reflection(room, data, sa, sb)
    _render_advice_board(room, data, sa, sb)
    _render_exit_ticket(room, sa, sb)

    nav_left, nav_right = st.columns(2)
    nav_left.button(
        "Mở Máy tính số đặc trưng", key=f"{_KEY_PREFIX}_nav_calc",
        on_click=navigate_to, args=(lmode.AREA_DATA, lmode.FEATURE_STATS_CALC),
    )
    nav_right.button(
        "Mở Phòng thí nghiệm ghép nhóm", key=f"{_KEY_PREFIX}_nav_lab",
        on_click=navigate_to, args=(lmode.AREA_DATA, lmode.FEATURE_GROUPING_LAB),
    )
    st.caption(
        "Phòng học dùng dữ liệu giả định theo kịch bản hoặc dữ liệu đã nạp phục "
        "vụ bài học thống kê; mọi con số chỉ để học, không phải khuyến nghị đầu tư."
    )



