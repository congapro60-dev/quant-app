"""Công cụ thống kê phổ thông (lớp 10–12): số đặc trưng, ghép nhóm, tần suất.

Tính toán tách khỏi hiển thị: các hàm ``approx_error``, ``summarize_ungrouped``,
``summarize_grouped``, ``compare_grouping``, ``updown_tally`` thuần dữ liệu và
được kiểm thử đơn vị không cần Streamlit.

Thuật ngữ bám SGK Kết nối tri thức theo Chương trình 2018:
số gần đúng, sai số tuyệt đối, độ chính xác, sai số tương đối, số quy tròn;
số trung bình, trung vị, tứ phân vị, mốt; khoảng biến thiên, khoảng tứ phân vị,
phương sai, độ lệch chuẩn; giá trị đại diện (trung điểm) của nhóm ghép.
"""

from __future__ import annotations

from math import isfinite, sqrt

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Bài 1: số gần đúng và sai số (lớp 10)
# ---------------------------------------------------------------------------

def approx_error(actual: float, assumed: float) -> dict[str, float]:
    """Sai số tuyệt đối Δa = |a − ā| và sai số tương đối δ = Δa/|ā| (×100%).

    Trong đó ``a`` là giá trị thật (đóng cửa thực tế) còn ``ā`` là số gần đúng
    (giá dự báo/đã quy tròn) đang được đánh giá.
    """

    a = float(actual)
    a_hat = float(assumed)
    if not (isfinite(a) and isfinite(a_hat)):
        raise ValueError("Cần hai số hữu hạn.")
    absolute = abs(a - a_hat)
    relative = absolute / abs(a_hat) * 100.0 if a_hat != 0 else float("nan")
    return {"abs_error": absolute, "rel_error_pct": relative}


# ---------------------------------------------------------------------------
# Bài 2: số đặc trưng của mẫu KHÔNG ghép nhóm (lớp 10)
# ---------------------------------------------------------------------------

def _median_of_sorted(sorted_vals: list[float]) -> float:
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_vals[mid])
    return (float(sorted_vals[mid - 1]) + float(sorted_vals[mid])) / 2.0


def _split_halves(sorted_vals: list[float]) -> tuple[list[float], list[float]]:
    """Nửa trái/phải để tính tứ phân vị; với n lẻ, trung vị không thuộc nửa nào."""

    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[:mid], sorted_vals[mid + 1:]
    return sorted_vals[:mid], sorted_vals[mid:]


def parse_values(text: str) -> list[float]:
    """Đọc chuỗi số nhập tay: ngăn cách bằng dấu chấm phẩy, phẩy, trống hoặc dòng.

    Chấp nhận cả hai kiểu kiểu viết số (số thập phân có hoặc không có phần lẻ).
    Phần trăm (%) đi kèm bị bỏ qua. Số không đọc được bị bỏ; chuỗi rỗng là lỗi.
    """

    raw = str(text or "").replace("\n", ";").replace("\t", ";").replace(";", ",")
    tokens = [t.strip().rstrip("%") for t in raw.split(",")]
    values: list[float] = []
    for token in tokens:
        if not token or token in ("-", "+", "."):
            continue
        try:
            value = float(token)
        except ValueError:
            continue
        if isfinite(value):
            values.append(value)
    if not values:
        raise ValueError("Chưa đọc được số hợp lệ nào.")
    return values


def summarize_ungrouped(values: list[float]) -> dict[str, object]:
    """Số đặc trưng của mẫu không ghép nhóm theo SGK Toán 10.

    Tứ phân vị tính theo cách trung vị của nửa trái/nửa phải (trung vị của
    cả mẫu, khi n lẻ, không thuộc nửa nào). Phương sai chia cho n.
    """

    clean = [float(v) for v in values if isfinite(float(v))]
    n = len(clean)
    if n < 2:
        raise ValueError("Cần ít nhất hai giá trị.")
    ordered = sorted(clean)
    mean = sum(ordered) / n
    median = _median_of_sorted(ordered)
    frequencies: dict[float, int] = {}
    for v in clean:
        frequencies[v] = frequencies.get(v, 0) + 1
    highest = max(frequencies.values())
    modes = tuple(sorted(v for v, c in frequencies.items() if c == highest)) if highest > 1 else ()
    half_left, half_right = _split_halves(ordered)
    q1 = _median_of_sorted(half_left) if half_left else ordered[0]
    q3 = _median_of_sorted(half_right) if half_right else ordered[-1]
    variance = sum((v - mean) ** 2 for v in ordered) / n
    iqr = q3 - q1
    if iqr > 0:
        low_fence = q1 - 1.5 * iqr
        high_fence = q3 + 1.5 * iqr
        outliers = tuple(sorted(v for v in ordered if v < low_fence or v > high_fence))
        fences = (low_fence, high_fence)
    else:
        outliers = ()
        fences = (float("nan"), float("nan"))
    return {
        "n": n,
        "mean": mean,
        "median": median,
        "modes": modes,
        "min": ordered[0],
        "max": ordered[-1],
        "range": ordered[-1] - ordered[0],
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "variance": variance,
        "std": sqrt(variance),
        "outliers": outliers,
        "fences": fences,
    }


# ---------------------------------------------------------------------------
# Bài 3: mẫu số liệu ghép nhóm (lớp 11)
# ---------------------------------------------------------------------------

def group_series(values: list[float], num_groups: int) -> dict[str, object]:
    """Chia mẫu thành các khoảng bằng nhau, đếm tần suất, lấy giá trị đại diện."""

    clean = [float(v) for v in values if isfinite(float(v))]
    n_total = len(clean)
    if n_total < 2:
        raise ValueError("Cần ít nhất hai giá trị.")
    if num_groups < 1:
        raise ValueError("Số nhóm phải từ 1 trở lên.")
    lo, hi = min(clean), max(clean)
    if hi <= lo:
        width, boundaries = 1.0, [lo - 0.5, lo + 0.5]
        counts = [n_total]
    else:
        width = (hi - lo) / num_groups
        boundaries = [lo + i * width for i in range(num_groups + 1)]
        counts = [0] * num_groups
        for v in clean:
            idx = min(int((v - lo) / width), num_groups - 1)
            counts[idx] += 1
    labels = [
        f"[{boundaries[i]:.4g}; {boundaries[i + 1]:.4g})"
        if i < len(counts) - 1 else
        f"[{boundaries[i]:.4g}; {boundaries[i + 1]:.4g}]"
        for i in range(len(counts))
    ]
    mids = [(boundaries[i] + boundaries[i + 1]) / 2.0 for i in range(len(counts))]
    return {"boundaries": boundaries, "counts": counts, "labels": labels,
            "mids": mids, "width": width, "n_total": n_total}


def _grouped_percentile(boundaries, counts, width: float, position: float) -> float:
    """Nội suy phân vị của mẫu ghép nhóm tại vị trí ``position`` (ví dụ N/2)."""

    cumulative = 0
    for i, c in enumerate(counts):
        prev = cumulative
        cumulative += c
        if cumulative >= position:
            if prev == position and i > 0:  # vị trí đúng ở biên nhóm
                return float(boundaries[i])
            return float(boundaries[i] + (position - prev) / c * width)
    return float(boundaries[-1])


def summarize_grouped(values: list[float], num_groups: int) -> dict[str, object]:
    """Số đặc trưng ước lượng của mẫu ghép nhóm (Toán 11: trung tâm; Toán 12: phân tán).

    Trung bình và phương sai dùng giá trị đại diện (trung điểm nhóm); trung vị,
    tứ phân vị, mốt dùng công thức nội suy thường gặp trong SGK. Khoảng biến
    thiên xấp xỉ bằng hiệu biên lớn nhất trừ biên nhỏ nhất của các nhóm.
    """

    groups = group_series(values, num_groups)
    boundaries = groups["boundaries"]
    counts = groups["counts"]
    mids = groups["mids"]
    width = float(groups["width"])
    n_total = int(groups["n_total"])
    mean = sum(c * m for c, m in zip(counts, mids)) / n_total
    variance = sum(c * (m - mean) ** 2 for c, m in zip(counts, mids)) / n_total
    median = _grouped_percentile(boundaries, counts, width, n_total / 2.0)
    q1 = _grouped_percentile(boundaries, counts, width, n_total / 4.0)
    q3 = _grouped_percentile(boundaries, counts, width, 3.0 * n_total / 4.0)
    mode_count = max(counts)
    j = counts.index(mode_count)
    prev_n = counts[j - 1] if j > 0 else 0
    next_n = counts[j + 1] if j < len(counts) - 1 else 0
    denom = (mode_count - prev_n) + (mode_count - next_n)
    mode = (float(mids[j]) if denom == 0 else
            float(boundaries[j] + width * (mode_count - prev_n) / denom))
    return {**groups, "mean": mean, "median": median, "mode": mode,
            "q1": q1, "q3": q3, "iqr": q3 - q1,
            "range": float(boundaries[-1] - boundaries[0]),
            "variance": variance, "std": sqrt(variance)}


def compare_grouping(values: list[float], num_groups: int) -> tuple[dict, dict, pd.DataFrame]:
    """So sánh số đặc trưng ghép nhóm với không ghép nhóm (rel = sai số tương đối)."""

    base = summarize_ungrouped(values)
    grouped = summarize_grouped(values, num_groups)
    first_mode = base["modes"][0] if base["modes"] else float("nan")
    rows: list[dict[str, object]] = []
    for label, exact, approx in (
        ("Số trung bình", float(base["mean"]), float(grouped["mean"])),
        ("Trung vị", float(base["median"]), float(grouped["median"])),
        ("Mốt", first_mode, float(grouped["mode"])),
        ("Độ lệch chuẩn", float(base["std"]), float(grouped["std"])),
    ):
        rel = (abs(approx - exact) / abs(exact) * 100.0
               if exact and isfinite(exact) else float("nan"))
        rows.append({"Số đặc trưng": label, "Không ghép nhóm": exact,
                     "Ghép nhóm (ước lượng)": approx,
                     "Chênh lệch": approx - exact,
                     "Sai số tương đối (%)": rel})
    return base, grouped, pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Bài 4: bảng tần suất hai chiều và biểu đồ (tổ chức dữ liệu, lớp 10)
# ---------------------------------------------------------------------------

def updown_tally(prices: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Đếm phiên tăng/giảm/không đổi của từng mã → bảng tần suất hai chiều."""

    rows = []
    for symbol in symbols:
        series = pd.to_numeric(prices[symbol], errors="coerce").dropna()
        delta = series.diff().dropna()
        if delta.empty:
            continue
        rows.append({
            "Mã": symbol,
            "Tăng": int((delta > 0).sum()),
            "Giảm": int((delta < 0).sum()),
            "Không đổi": int((delta == 0).sum()),
            "Số phiên": int(len(delta)),
        })
    return pd.DataFrame(rows)


def pct_returns(prices: pd.DataFrame, symbol: str, last_n: int) -> pd.Series:
    """Lợi suất ngày (%) dạng phần trăm của một mã, lấy ``last_n`` phiên cuối."""

    series = pd.to_numeric(prices[symbol], errors="coerce").dropna()
    returns = series.pct_change(fill_method=None).dropna() * 100.0
    return returns.tail(int(last_n))


# ---------------------------------------------------------------------------
# Công thức để hiển thị (LaTeX)
# ---------------------------------------------------------------------------

FORMULA_APPROX = r"""
\Delta a = |a - \bar{a}| \quad \text{(sai số tuyệt đối)} \qquad
\delta = \frac{\Delta a}{|\bar{a}|} \cdot 100\% \quad \text{(sai số tương đối)}
"""

FORMULA_UNGROUPED = r"""
\bar{x} = \frac{x_1 + x_2 + \dots + x_n}{n} = \frac{1}{n}\sum_{i=1}^{n} x_i \\
s^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2 \qquad s = \sqrt{s^2} \\
R = x_{\max} - x_{\min} \qquad \Delta_Q = Q_3 - Q_1
"""

FORMULA_GROUPED = r"""
\bar{x}_g = \frac{n_1 c_1 + n_2 c_2 + \dots + n_k c_k}{N} \\
s^2_g = \frac{1}{N}\sum_{i=1}^{k} n_i\,(c_i - \bar{x}_g)^2 \qquad s_g = \sqrt{s^2_g} \\
M_e = u_{M_e} + \frac{\frac{N}{2} - cf}{n_{M_e}} \cdot w \\
R_g \approx u_{\max} - u_{\min} \qquad \Delta_{Q,g} = Q_{3,g} - Q_{1,g}
"""


# ---------------------------------------------------------------------------
# Phần hiển thị (Streamlit)
# ---------------------------------------------------------------------------

CHART_COLORS = ["#5EEAD4", "#93C5FD", "#FBBF24", "#FDA4AF", "#A5B4FC", "#86EFAC"]
DEFAULT_VALUES = "-2, 1, 0.5, 3, -1, 1, -0.5, 2"


# ---------------------------------------------------------------------------
# Ba khối sư phạm dùng chung cho mạch học 4 bước: dẫn dắt lý thuyết → tự tính
# trên giấy → nêu ý nghĩa → phản tư đào sâu. Mọi nơi dùng kiến thức thống kê
# đều chạy đủ mạch này để học sinh hiểu tự nhiên thay vì bấm máy tính qua loa.
# ---------------------------------------------------------------------------


def theory_lead(body: str) -> None:
    """Khối dẫn dắt lý thuyết đặt ngay dưới tiêu đề công cụ.

    Trả lời câu hỏi "cái này dùng để làm gì trong dự án" bằng ngôn ngữ SGK,
    đủ ngắn để đọc trong một phút trước khi bấm tính.
    """

    st.markdown(f"🧭 **Hiểu nhanh trước khi tính.** {body}")


def meaning_block(key: str, question: str, model_answer: str, *, hint: str = "") -> None:
    """Học sinh tự viết ý nghĩa trước, sau đó mới cho so đáp án mẫu.

    ``model_answer`` viết theo khung câu để học sinh bắt chước cách diễn đạt
    "con số kèm ý nghĩa", không phải chỉ chép kết quả. ``key`` chỉ dùng để đặt
    key widget, tránh trùng giữa các trang.
    """

    st.markdown(f"✍️ **Nêu ý nghĩa của em:** {question}")
    st.text_area(
        "Viết 2–3 câu bằng lời của em (không chấm điểm, viết xong mới so đáp án)",
        key=f"{key}_meaning",
        placeholder="Trả lời của em…",
    )
    if hint:
        st.caption(f"Gợi ý: {hint}")
    with st.expander("Đối chiếu đáp án mẫu"):
        st.markdown(model_answer)


def reflection_block(items: list[tuple[str, str]]) -> None:
    """Khối phản tư: mỗi câu hỏi đào sâu ẩn lời giải mẫu riêng để tự nghĩ trước.

    ``items`` là danh sách cặp (câu hỏi, lời giải mẫu).
    """

    st.markdown("🔁 **Phản tư — đào sâu thêm** (tự nghĩ trước rồi mới mở lời giải)")
    for index, (question, model) in enumerate(items, start=1):
        with st.expander(f"Câu {index}. {question}"):
            st.markdown(model)


def render_stats_calculator(prices: pd.DataFrame, market: str) -> None:
    """Máy tính số đặc trưng (không ghép nhóm) cho bài học lớp 10."""

    st.subheader("Máy tính số đặc trưng (mẫu không ghép nhóm)")
    theory_lead(
        "Trung bình x̄ trả lời “thường được bao nhiêu?”, độ lệch chuẩn s trả lời "
        "“đi lạc quanh mức đó cỡ bao nhiêu?” — cặp trung tâm–phân tán này là gốc của "
        "mọi ghi chú rủi ro ở tab Đầu tư. Riêng Q1, Q3 và khoảng tứ phân vị khoanh "
        "vùng “nửa số ở giữa”; giá trị nằm ngoài 1,5·IQR là phiên lạ, đáng dò tin "
        "trước khi tin vào bảng giá."
    )
    has_data = not prices.empty
    asset_names = [c for c in prices.columns if c != market] if has_data else []
    options = ("Nhập tay", "Lấy từ dữ liệu đã nạp") if has_data else ("Nhập tay",)
    source = st.radio("Nguồn dữ liệu", options, index=0, horizontal=True,
                      key="stats_calc_source")
    values: list[float] | None = None
    unit = "đơn vị dữ liệu"
    if source == "Lấy từ dữ liệu đã nạp" and has_data:
        left, right = st.columns(2)
        symbol = left.selectbox("Mã", asset_names, key="stats_calc_symbol")
        window = right.selectbox("Số phiên gần nhất", (10, 15, 20, 30, 40, 60, 90), index=2,
                                 key="stats_calc_window")
        series = pct_returns(prices, symbol, window)
        if len(series) >= 2:
            values = series.tolist()
            unit = "% lợi suất/ngày"
            last_day = pd.Timestamp(series.index.max()).strftime("%d/%m/%Y")
            st.caption(f"Lợi suất ngày của {symbol}, {len(series)} phiên gần nhất, "
                       f"in đến phiên {last_day}. Chuyển sang lợi suất (%) để các em "
                       "quản được thang số theo SGK.")
        else:
            st.info("Dữ liệu dự phòng không đủ hai phiên; nhập tay bên dưới.")
    if values is None:
        text = st.text_area(
            "Nhập các số, cách nhau bằng dấu phẩy hoặc xuống dòng",
            value="-2, 1, 0.5, 3, -1, 1, -0.5, 2",
            key="stats_calc_values",
            help="Dấu chấm là dấu thập phân. Ví dụ: -2, 1, 0.5, 3, -1",
        )
        try:
            values = parse_values(text)
            unit = "đơn vị nhập vào"
        except ValueError as exc:
            st.warning(str(exc))
            return

    try:
        summary = summarize_ungrouped(values)
    except ValueError as exc:
        st.warning(str(exc))
        return

    with st.expander("Công thức bám SGK Toán 10"):
        st.latex(FORMULA_UNGROUPED)
        st.caption("Tứ phân vị tính theo cách trung vị của nửa trái/phải; các bộ SGK "
                   "khác có thể nội suy hơi khác một chút nhưng ý nghĩa không đổi.")

    st.markdown("**Bước 1 — tự tính trên giấy trước khi đọc đáp số.** Dùng công thức "
                "phía trên, tính ra x̄ và s rồi nhập vào hai ô dưới; máy chỉ để đối chiếu.")
    pred_left, pred_right = st.columns(2)
    pred_mean = pred_left.number_input("Dự đoán x̄ của em", value=0.0,
                                       key="stats_calc_pred_mean",
                                       help="Nhập kết quả tự tính; để 0 nếu chưa tính.")
    pred_std = pred_right.number_input("Dự đoán s của em", value=0.0,
                                       key="stats_calc_pred_std",
                                       help="Nhập kết quả tự tính; để 0 nếu chưa tính.")
    if pred_mean != 0.0:
        gap = abs(pred_mean - summary["mean"])
        tol = max(0.05 * abs(summary["mean"]), 0.05)
        if gap <= tol:
            st.success(f"x̄ tự tính khớp máy (lệch {gap:,.4g}) — cách tính của em chuẩn.")
        else:
            st.info(f"x̄ tự tính lệch máy {gap:,.4g} (máy ra {summary['mean']:,.4g}). "
                    "Kiểm tra lại: cộng đủ n số chưa và có chia cho N chứ không phải N−1?")
    if pred_std != 0.0:
        gap = abs(pred_std - summary["std"])
        tol = max(0.1 * summary["std"], 0.05)
        if gap <= tol:
            st.success(f"s tự tính khớp máy (lệch {gap:,.4g}).")
        else:
            st.info(f"s tự tính lệch máy {gap:,.4g} (máy ra {summary['std']:,.4g}). "
                    "Nhắc lại: s là căn của phương sai và phương sai chia cho N "
                    "theo SGK Toán 10.")

    mode_text = ", ".join(f"{m:g}" for m in summary["modes"]) if summary["modes"] else "không có (không giá trị nào lặp lại)"
    grid = st.columns(4)
    grid[0].metric("Cỡ mẫu n", f"{summary['n']}")
    grid[1].metric("Số trung bình", f"{summary['mean']:,.4g}")
    grid[2].metric("Trung vị Me", f"{summary['median']:,.4g}")
    grid[3].metric("Mốt Mo", mode_text)
    grid2 = st.columns(4)
    grid2[0].metric(f"Khoảng biến thiên ({unit})", f"{summary['range']:,.4g}")
    grid2[1].metric("Tứ phân vị Q1", f"{summary['q1']:,.4g}")
    grid2[2].metric("Tứ phân vị Q3", f"{summary['q3']:,.4g}")
    grid2[3].metric("Khoảng tứ phân vị", f"{summary['iqr']:,.4g}")
    grid3 = st.columns(2)
    grid3[0].metric("Phương sai s²", f"{summary['variance']:,.4g}")
    grid3[1].metric("Độ lệch chuẩn s", f"{summary['std']:,.4g}")

    # Khoanh vùng giá trị bất thường theo quy tắc 1,5·IQR (SGK Toán 10);
    # với mẫu đồng nhất (IQR = 0) quy tắc không cho kết quả có nghĩa nên bỏ qua.
    if summary["outliers"]:
        low_fence, high_fence = summary["fences"]
        tags = ", ".join(f"{v:,.4g}" for v in summary["outliers"])
        st.info(f"Giá trị bất thường theo quy tắc 1,5·IQR (dưới {low_fence:,.4g} hoặc "
                f"trên {high_fence:,.4g}): **{tags}**. Đây là phiên biến động mạnh "
                "đáng dò tin tức, chưa chắc là dữ liệu lỗi.")

    st.caption("Độ lệch chuẩn s càng lớn, lợi suất càng dao động quanh mức trung bình "
               "— trong tab Đầu tư, đó chính là con số 'Biến động năm hóa'.")
    outlier_text = (
        ", ".join(f"{v:,.4g}" for v in summary["outliers"]) if summary["outliers"]
        else "không có"
    )
    meaning_block(
        "stats_calc",
        "Dùng các số vừa tính, viết 2–3 câu mô tả mẫu lợi suất như một nhận định "
        "trong báo cáo dự án.",
        f"Khung tham khảo: “Với n = {summary['n']} số, lợi suất trung bình khoảng "
        f"{summary['mean']:,.4g} ({unit}); phân tán s = {summary['std']:,.4g} — mỗi số "
        f"thường lệch khỏi trung bình cỡ {summary['std']:,.4g}. Nửa số liệu nằm trong "
        f"khoảng [{summary['q1']:,.4g}; {summary['q3']:,.4g}]; giá trị bất thường: "
        f"{outlier_text}.”",
        hint="Trình tự nên kể: trung tâm → phân tán → giá trị lạ; kèm ý nghĩa rủi ro cao hay thấp.",
    )
    reflection_block([
        ("Thêm một ngày bật lên +20% vào mẫu thì trung bình hay trung vị đổi mạnh hơn? Vì sao?",
         "Trung bình bị kéo theo số cực đại nên đổi rõ; trung vị dựa vào vị trí giữa nên "
         "gần như đứng yên. Mẫu có giá trị bất thường thì phải đọc kèm trung vị mới phản "
         "ánh trung tâm thật."),
        ("Hai mã có s ngày là 1,2% và 0,4% — lớp muốn “ngủ ngon” chọn mã nào, muốn cơ hội "
         "lãi lớn thì sao?",
         "s nhỏ thì ngày nào cũng gần trung bình nên đi êm (mã 0,4%); s lớn thì dao động "
         "mạnh, cơ hội lãi lẫn lỗ đều lớn hơn (mã 1,2%). Đây chính là bài toán rủi ro – "
         "lợi suất sẽ học kỹ ở bài Rủi ro và đa dạng hóa."),
    ])
    return None


def render_grouping_lab(prices: pd.DataFrame, market: str) -> None:
    """Phòng thí nghiệm ghép nhóm: tần số, giá trị đại diện, so sánh ghép/không ghép."""

    st.subheader("Phòng thí nghiệm ghép nhóm")
    theory_lead(
        "Mẫu càng lớn (60, 90 phiên) càng không đọc nổi từng số. Ghép nhóm chia mẫu "
        "thành các khoảng đều, đếm tần số từng khoảng rồi gán cho khoảng một giá trị "
        "đại diện — trung điểm. Cái được là gọn và dễ báo cáo; cái mất là chi tiết "
        "trong từng khoảng bị bỏ đi, nên mọi số ghép nhóm chỉ là ước lượng (nối thẳng "
        "bài Số gần đúng và sai số, Toán 10)."
    )
    has_data = not prices.empty
    asset_names = [c for c in prices.columns if c != market] if has_data else []
    options = ("Nhập tay", "Lấy từ dữ liệu đã nạp") if has_data else ("Nhập tay",)
    source = st.radio("Nguồn dữ liệu", options, index=0, horizontal=True,
                      key="grouping_lab_source")
    values: list[float] | None = None
    if source == "Lấy từ dữ liệu đã nạp" and has_data:
        left, right = st.columns(2)
        symbol = left.selectbox("Mã", asset_names, key="grouping_lab_symbol")
        window = right.selectbox("Số phiên gần nhất", (30, 40, 60, 90, 120), index=2,
                                 key="grouping_lab_window")
        series = pct_returns(prices, symbol, window)
        if len(series) >= 8:
            values = series.tolist()
            last_day = pd.Timestamp(series.index.max()).strftime("%d/%m/%Y")
            st.caption(f"Lợi suất ngày (%) của {symbol}, {len(series)} phiên gần nhất, "
                       f"in đến phiên {last_day}.")
        else:
            st.info("Dữ liệu đã nạp không đủ phiên; chuyển sang nhập tay bên dưới.")
    if values is None:
        text = st.text_area(
            "Nhập các số, cách nhau bằng dấu phẩy hoặc xuống dòng",
            value=DEFAULT_VALUES, key="grouping_lab_values",
            help="Dấu chấm là dấu thập phân. Ví dụ: -2, 1, 0.5, 3, -1",
        )
        try:
            values = parse_values(text)
        except ValueError as exc:
            st.warning(str(exc))
            return
    if len(values) < 4:
        st.warning("Cần ít nhất 4 số để ghép nhóm có ý nghĩa.")
        return

    num_groups = st.slider("Số nhóm k", 2, 10, 4, key="grouping_lab_k")
    _, grouped, table = compare_grouping(values, num_groups)

    st.markdown("**Bước 1 — tự tính trên giấy.** Hình dung từ bảng tần số phía dưới: "
                "x̄g = (n₁·c₁ + … + nₖ·cₖ)/N. Tính ra rồi nhập để đối chiếu.")
    pred_grouped = st.number_input("Dự đoán x̄g của em", value=0.0,
                                   key="grouping_lab_pred_mean",
                                   help="Gợi ý: nhân tần số với giá trị đại diện của từng "
                                        "nhóm, cộng lại rồi chia cho N.")
    if pred_grouped != 0.0:
        grouped_mean = float(grouped["mean"])
        gap = abs(pred_grouped - grouped_mean)
        tol = max(0.05 * abs(grouped_mean), 0.05)
        if gap <= tol:
            st.success(f"x̄g tự tính khớp ước lượng của máy (lệch {gap:,.4g}).")
        else:
            st.info(f"x̄g tự tính lệch {gap:,.4g} (máy ước lượng {grouped_mean:,.4g}). "
                    "Kiểm tra lại: mỗi nhóm nhân đúng giá trị đại diện chưa, có chia "
                    "cho tổng tần số N chưa?")

    left, right = st.columns(2)
    with left:
        st.markdown("**Bảng tần số sau khi ghép nhóm**")
        freq = pd.DataFrame({
            "Nhóm": grouped["labels"],
            "Giá trị đại diện c": grouped["mids"],
            "Tần số n": grouped["counts"],
        })
        st.dataframe(freq, hide_index=True, use_container_width=True)
        st.caption(f"Kích thước nhóm w = {float(grouped['width']):,.4g}; "
                   f"tổng tần số N = {int(grouped['n_total'])}.")
    with right:
        st.markdown("**Số đặc trưng ước lượng của mẫu ghép nhóm**")
        grid = st.columns(2)
        grid[0].metric("Số trung bình x̄g", f"{float(grouped['mean']):,.4g}")
        grid[1].metric("Trung vị Meg (nội suy)", f"{float(grouped['median']):,.4g}")
        grid[0].metric("Mốt Mog", f"{float(grouped['mode']):,.4g}")
        grid[1].metric("Độ lệch chuẩn sg", f"{float(grouped['std']):,.4g}")
        grid2 = st.columns(2)
        grid2[0].metric("Khoảng biến thiên g", f"{float(grouped['range']):,.4g}")
        grid2[1].metric("Khoảng tứ phân vị g", f"{float(grouped['iqr']):,.4g}")
    with st.expander("Công thức ghép nhóm (SGK Toán 11 và 12)"):
        st.latex(FORMULA_GROUPED)
        st.caption("Một số bộ SGK gọi giá trị đại diện của nhóm là 'tổ trọng tâm' — ý nghĩa giống nhau.")

    st.markdown("**So sánh ghép nhóm với không ghép nhóm**")
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption("Cột cuối là sai số tương đối do ghép nhóm: mất chi tiết nên ước lượng "
               "lệch đi một chút — đúng tinh thần bài Số gần đúng và sai số (lớp 10).")
    fig = px.bar(freq, x="Nhóm", y="Tần số n", color_discrete_sequence=CHART_COLORS[:1])
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title="Tần số theo nhóm")
    st.plotly_chart(fig, use_container_width=True, key="grouping_lab_bar")

    direct_mean = float(table.iloc[0]["Không ghép nhóm"])
    rel_error = float(table.iloc[0]["Sai số tương đối (%)"])
    meaning_block(
        "grouping_lab",
        "So x̄g với x̄ tính trực tiếp: sai số tương đối (%) cho biết mẫu ghép nhóm "
        "còn đáng tin không?",
        f"Khung tham khảo: “Ghép {num_groups} nhóm, x̄g = {float(grouped['mean']):,.4g} "
        f"trong khi tính trực tiếp x̄ = {direct_mean:,.4g}, lệch khoảng {rel_error:,.2f}%. "
        "Sai số nhỏ nên vẫn dùng số ghép nhóm để nói xu thế; cần chính xác từng ngày thì "
        "phải quay về mẫu chưa ghép.”",
        hint="Đọc cột 'Sai số tương đối (%)' ở bảng so sánh; lệch dưới khoảng 5% thường "
             "được coi là chấp nhận được.",
    )
    reflection_block([
        ("Kéo k từ 2 lên 8 rồi về 2 — bảng tần số và các số đặc trưng đổi thế nào?",
         "k = 2: mất hầu hết chi tiết, tần số dồn về ít nhóm, các số đặc trưng xấp xỉ "
         "trung điểm hai nửa; k quá lớn thì mỗi nhóm có ít số, ước lượng nhiễu. Kinh "
         "nghiệm: mỗi nhóm nên có khoảng 4–6 số."),
        ("Vì sao lấy trung điểm làm giá trị đại diện cho cả khoảng?",
         "Giả định các số rải đều trong khoảng nên trung bình của khoảng trùng trung "
         "điểm; dữ liệu dồn về một đầu thì trung điểm lệch đi — đó cũng chính là nguồn "
         "gây sai số đã thấy ở bảng so sánh."),
    ])


def render_frequency_table(prices: pd.DataFrame, market: str) -> None:
    """Bảng tần suất hai chiều (mã × trạng thái phiên) và biểu đồ trực quan."""

    st.subheader("Bảng tần suất hai chiều và biểu đồ")
    theory_lead(
        "Giá là số đo lường, còn “phiên tăng hay giảm” là dữ liệu phân loại: gom thành "
        "bảng tần suất hai chiều (hàng: mã, cột: Tăng/Giảm/Không đổi) rồi vẽ biểu đồ — "
        "đúng kỹ năng tổ chức dữ liệu của SGK Toán 10. Bảng trả lời nhanh câu hỏi kiểu "
        "“giai đoạn này mã nào lên xu thế?” mà không cần đọc từng phiên một."
    )
    prices_local = prices
    demo = False
    if prices_local is None or prices_local.empty:
        from sample_data import make_sample_prices
        prices_local = make_sample_prices()
        demo = True
        st.info("Chưa nạp dữ liệu thật — đang dùng bộ dữ liệu mô phỏng (CTG, HPG, FPT, "
                "VN-Index, 260 phiên) để các em vẫn làm được bài.")
    asset_names = [c for c in prices_local.columns if c != market]
    symbols = st.multiselect("Chọn mã", asset_names, default=asset_names[:4],
                             key="freq_symbols")
    if not symbols:
        st.warning("Hãy chọn ít nhất một mã.")
        return
    guess = st.selectbox(
        "Đoán trước khi vẽ: giai đoạn này mã nào có nhiều phiên tăng nhất?",
        ("Chưa đoán — muốn tự nghĩ đã",) + tuple(symbols),
        key="freq_guess_top",
        help="Ghi dự đoán của em ra vở, rồi đối chiếu với bảng bên dưới.",
    )
    tally = updown_tally(prices_local, symbols)
    if tally.empty or tally["Số phiên"].max() < 1:
        st.warning("Mã đã chọn không có đủ số liệu để đếm phiên.")
        return

    leader = str(tally.loc[tally["Tăng"].idxmax(), "Mã"])
    if guess != "Chưa đoán — muốn tự nghĩ đã":
        if guess == leader:
            st.success(f"Đoán trúng: {leader} dẫn đầu số phiên tăng trong giai đoạn này.")
        else:
            st.info(f"Thực ra là {leader}. So lại cột Tăng: {guess} thua mấy phiên? "
                    "Kết luận về xu thế phải dựa vào tần số, không dựa vào cảm giác.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Bảng tần suất hai chiều**")
        st.dataframe(tally, hide_index=True, use_container_width=True)
    with right:
        long = tally.melt(id_vars="Mã", value_vars=("Tăng", "Giảm", "Không đổi"),
                          var_name="Phiên", value_name="Tần số")
        fig = px.bar(long, x="Mã", y="Tần số", color="Phiên", barmode="stack",
                     color_discrete_sequence=CHART_COLORS[:3])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10),
                          legend_title_text="", title="Tần số tăng/giảm theo mã")
        st.plotly_chart(fig, use_container_width=True, key="freq_bar")
        totals = tally.drop(columns="Mã")[["Tăng", "Giảm", "Không đổi"]].sum()
        fig_pie = px.pie(names=totals.index, values=totals.values, hole=0.45,
                         color_discrete_sequence=CHART_COLORS[:3])
        fig_pie.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10),
                              title="Tỉ trọng trạng thái phiên")
        st.plotly_chart(fig_pie, use_container_width=True, key="freq_pie")

    last_day = pd.Timestamp(prices_local.index.max()).strftime("%d/%m/%Y")
    label = "(dữ liệu mô phỏng)" if demo else "(nguồn: giá đã nạp trong phiên làm việc)"
    st.caption(f"Đếm phiên liền sau phiên trước, in đến ngày phiên {last_day} {label}. "
               "Đọc bảng: hàng nào 'Tăng' áp đảo thì mã đó lên xu thế trong giai đoạn này.")

    leader_row = tally.loc[tally["Mã"] == leader]
    leader_total = float(leader_row[["Tăng", "Giảm", "Không đổi"]].sum(axis=1).iloc[0])
    leader_up = int(leader_row["Tăng"].iloc[0])
    rise_pct = leader_up / leader_total * 100 if leader_total else 0.0
    meaning_block(
        "freq_table",
        "Viết 2 câu nhận xét từ bảng này để đưa vào phần chọn mã của báo cáo dự án.",
        f"Khung tham khảo: “Trong giai đoạn vừa đếm, {leader} có số phiên tăng cao nhất "
        f"({leader_up} phiên, chiếm {rise_pct:.0f}% các phiên đã đếm) — dấu hiệu lên xu "
        "thế. Tuy nhiên bảng chỉ đếm trạng thái, chưa nói mỗi phiên tăng mạnh hay nhẹ, "
        "nên kết luận cuối cần đối chiếu thêm số đặc trưng lợi suất.”",
        hint="Đọc cả hàng (Tăng + Giảm + Không đổi) chứ đừng chỉ nhìn cột Tăng; "
             "tỉ lệ phần trăm thuyết phục hơn số thô.",
    )
    reflection_block([
        ("Bảng gom mọi phiên thành ba trạng thái — những thông tin nào bị bỏ phí?",
         "Độ lớn biến động bị bỏ: hai mã cùng tăng 5 phiên nhưng “tăng nhẹ” và “tăng "
         "vọt” khác nhau rõ. Muốn thấy điều đó phải quay lại tính s ở máy tính số đặc "
         "trưng (Toán 10) hoặc s_g ghép nhóm (Toán 12)."),
        ("Nếu đổi cách phân cột thành “tăng trên 2% / giảm dưới −2% / khác”, kết luận "
         "về mã dẫn đầu có đổi không?",
         "Có thể đổi: mỗi phiên chỉ thuộc một ô nên bảng vẫn là tần suất hai chiều đúng "
         "nghĩa, nhưng tiêu chí phân loại quyết định câu trả lời rút ra. Trình bày báo "
         "cáo phải ghi rõ tiêu chí đã dùng."),
    ])
