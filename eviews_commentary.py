"""Nhận xét kết quả bảng EViews trên web, viết cho cả người mới lẫn người đã quen.

Thứ tự đọc: dữ liệu có dùng được không, mô hình có đáng tin không, mô hình giải
thích được bao nhiêu, hệ số nói gì, rồi kết luận nên làm gì. Mỗi bước nói bằng
ngôn ngữ thường trước, rồi mới đến con số. Đây là quy tắc cố định, không gọi mô
hình ngôn ngữ, nên kiểm thử được và không cần khóa API. Các ngưỡng là quy tắc
ngón tay cái và được ghi rõ trong nhận xét.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_white, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.tsa.stattools import adfuller

from eviews_emulator import mackinnon_critical_values

ALPHA = 0.05
ADF_LAGS = 4
MIN_OBS = 30
TRADING_DAYS = 252
CONST_NAMES = ("const", "c")


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _is_const(name):
    return str(name).lower() in CONST_NAMES


def _is_return_name(name):
    return str(name).upper().startswith("R_")


def _p_text(p):
    p = float(p)
    return "p < 0.0001" if p < 0.0001 else f"p = {p:.4f}"


def _sig_text(p):
    return "có ý nghĩa thống kê" if float(p) < ALPHA else "chưa có ý nghĩa thống kê"


def _adf_on(series):
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < MIN_OBS:
        return None
    stat, pval, used, nobs, _ = adfuller(x, maxlag=ADF_LAGS, autolag=None, regression="c")
    return {"stat": float(stat), "pvalue": float(pval), "lags": int(used),
            "nobs": int(nobs), "crit": mackinnon_critical_values(nobs)}


def _stationary_level(stat, crit):
    for label in ("1%", "5%", "10%"):
        if stat < crit[label]:
            return label
    return None


def _beta_class_key(lo, hi):
    if lo > 1.0:
        return "dong"
    if lo > 0.0 and hi < 1.0:
        return "thu"
    if lo <= 0.0 <= hi:
        return "none"
    if hi < 0.0:
        return "neg"
    return "unsure"


def _beta_decision(key, dep):
    texts = {
        "dong": f"Có cơ sở xếp {dep} vào nhóm nhạy hơn thị trường: rủi ro và lợi nhuận có xu hướng lớn hơn thị trường.",
        "thu": f"Có cơ sở xếp {dep} vào nhóm ít nhạy hơn thị trường: rủi ro và lợi nhuận có xu hướng nhỏ hơn thị trường.",
        "none": f"Trong mẫu này không có quan hệ tuyến tính đáng kể, nên không dùng β để đo độ nhạy của {dep}.",
        "neg": f"Hai biến đi ngược chiều trong mẫu này. Cần xem lại dữ liệu và bối cảnh trước khi dùng.",
        "unsure": f"Chưa đủ bằng chứng để xếp {dep} vào nhóm nhạy hơn hay ít nhạy hơn thị trường. Cần kéo dài mẫu để thu hẹp khoảng tin cậy.",
    }
    return texts[key]


def _beta_class_text(key):
    texts = {
        "dong": "nhạy hơn thị trường (khoảng tin cậy nằm hoàn toàn trên 1)",
        "thu": "ít nhạy hơn thị trường (khoảng tin cậy nằm hoàn toàn trong khoảng từ 0 đến 1)",
        "none": "không có ý nghĩa thống kê, nên không kết luận gì về độ nhạy",
        "neg": "ngược chiều với thị trường",
        "unsure": "chưa đủ bằng chứng để nói nhạy hơn hay ít nhạy hơn (khoảng tin cậy chứa 1)",
    }
    return texts[key]


def adf_commentary(adf):
    var = str(adf["var"])
    stat = float(adf["stat"])
    crit = adf["crit"]
    c1, c5, c10 = crit["1%"], crit["5%"], crit["10%"]
    lags, nobs = adf["lags"], adf["nobs"]
    level = _stationary_level(stat, crit)
    out = [f"### 🧠 Kiểm định nghiệm đơn vị (ADF) của {var}", ""]
    out.append("**Nghĩa là gì?** Kiểm định này xem chuỗi có dừng không. Chuỗi dừng dao động quanh một mức ổn định; "
               "chuỗi không dừng (như giá cổ phiếu) trôi theo thời gian. Giả thuyết H0 là chuỗi không dừng. "
               "Nếu bác bỏ được H0 thì chuỗi dừng.")
    out.append(f"**Con số.** τ = {stat:.4f} (τ càng âm càng có bằng chứng chuỗi dừng). "
               f"Ngưỡng 1% = {c1:.4f}, 5% = {c5:.4f}, 10% = {c10:.4f}. Kiểm định dùng {lags} trễ và {nobs} quan sát.")
    if level:
        out.append(f"**Kết luận.** Bác bỏ H0 ở mức {level}: {var} là chuỗi dừng.")
        out.append("**Dùng để làm gì?** Chỉ khi chuỗi dừng, hồi quy trên nó mới cho quan hệ ổn định theo thời gian. "
                   "Với lợi suất, đây là điều kiện để β và R² có ý nghĩa.")
        out.append("**Quyết định.** Có thể đưa chuỗi này vào hồi quy và phân tích rủi ro. "
                   "Nếu chuỗi là giá mức, nên dùng lợi suất (sai phân lôgarit) để so sánh các chuỗi có cùng quy mô.")
    else:
        out.append(f"**Kết luận.** Chưa bác bỏ H0 ngay cả ở mức 10%: {var} có thể không dừng.")
        out.append("**Dùng để làm gì?** Cảnh báo: với chuỗi không dừng, R² và β có thể cao một cách giả tạo "
                   "(hồi quy giả mạo), vì hai chuỗi cùng trôi theo thời gian chứ không thật sự gắn bó.")
        out.append("**Quyết định.** Không dùng β, R² của chuỗi này để ra quyết định. "
                   "Lấy sai phân lôgarit (lợi suất), kiểm lại ADF, rồi mới hồi quy.")
    out.append("> Lưu ý: kết quả ADF nhạy với số trễ và với các giai đoạn gãy cấu trúc; nên đối chiếu với đồ thị chuỗi.")
    return "\n".join(out)


def ls_commentary(res):
    m = res.get("results")
    if m is None:
        return None
    dep = str(res.get("dep_var", "Y"))
    names = [str(nm) for nm in m.model.exog_names]
    params = np.asarray(m.params, dtype=float)
    bse_ols = np.asarray(m.bse, dtype=float)
    n = int(m.nobs)
    dfres = float(m.df_resid)
    tcrit = float(stats.t.ppf(0.975, dfres))
    resid = np.asarray(m.resid, dtype=float)
    exog = np.asarray(m.model.exog, dtype=float)
    endog = np.asarray(m.model.endog, dtype=float)
    reg_idx = [i for i, nm in enumerate(names) if not _is_const(nm)]
    const_idx = [i for i, nm in enumerate(names) if _is_const(nm)]
    x_label = ", ".join(names[i] for i in reg_idx) if reg_idx else "X"
    ret_ctx = _is_return_name(dep) and all(_is_return_name(names[i]) for i in reg_idx)

    def amt(v):
        return f"{v * 100:.2f}%" if ret_ctx else f"{v:.6f}"

    white = _safe(het_white, resid, exog)
    bg = _safe(acorr_breusch_godfrey, m, nlags=1)
    reset = _safe(linear_reset, m, power=2, use_f=True)
    jb = _safe(jarque_bera, resid)
    robust = _safe(m.get_robustcov_results, cov_type="HC1", use_t=True)
    white_bad = bool(white is not None and float(white[1]) < ALPHA)
    user_robust = "coef_results" in res
    use_robust = bool(robust is not None and (white_bad or user_robust))
    bse = np.asarray(robust.bse, dtype=float) if use_robust else bse_ols
    if use_robust and user_robust:
        se_reason = "bạn đã chọn LS(H)"
    elif use_robust:
        se_reason = "kiểm định White có ý nghĩa"
    else:
        se_reason = ""
    se_label = "SE White (HC1)" if use_robust else "SE thường (OLS)"

    r2 = float(m.rsquared)
    r2a = float(m.rsquared_adj)
    fval = float(m.fvalue)
    fp = float(m.f_pvalue)
    s_reg = float(np.sqrt(m.ssr / dfres)) if dfres > 0 else float("nan")
    sd_y = float(np.std(endog, ddof=1))
    dw = float(durbin_watson(resid))
    aic = float(m.aic) / n
    bic = float(m.bic) / n
    sys_sd = float(np.sqrt(max(r2, 0.0)) * sd_y)
    idio_sd = float(np.sqrt(max(1.0 - r2, 0.0)) * sd_y)

    adf_rows = []
    nonstationary = []
    for label, series in [(dep, endog)] + [(names[j], exog[:, j]) for j in reg_idx]:
        a = _safe(_adf_on, series)
        if a is None:
            adf_rows.append((label, None, None, None))
            continue
        stat_v = float(a["stat"])
        c5 = float(a["crit"]["5%"])
        ok = stat_v < c5
        if not ok:
            nonstationary.append(label)
        adf_rows.append((label, stat_v, c5, ok))

    r2_gt_dw = r2 > dw
    spurious = bool(nonstationary) or r2_gt_dw
    reset_bad = reset is not None and float(reset.pvalue) < ALPHA
    bg_bad = bg is not None and float(bg[1]) < ALPHA
    jb_bad = jb is not None and float(jb[1]) < ALPHA

    betas = []
    for j in reg_idx:
        b = float(params[j])
        se = float(bse[j])
        t = b / se
        p = 2.0 * float(stats.t.sf(abs(t), dfres))
        lo, hi = b - tcrit * se, b + tcrit * se
        t1 = (b - 1.0) / se
        p1 = 2.0 * float(stats.t.sf(abs(t1), dfres))
        betas.append({"name": names[j], "b": b, "se": se, "se_ols": float(bse_ols[j]),
                      "t": t, "p": p, "lo": lo, "hi": hi, "t1": t1, "p1": p1,
                      "key": _beta_class_key(lo, hi)})

    c = pc = None
    if const_idx:
        i = const_idx[0]
        c = float(params[i])
        pc = 2.0 * float(stats.t.sf(abs(c / float(bse[i])), dfres))

    vifs = []
    if len(reg_idx) >= 2:
        for j in reg_idx:
            v = _safe(variance_inflation_factor, exog, j)
            if v is not None:
                vifs.append((names[j], float(v)))
    names_nonstat = ", ".join(nonstationary)
    out = [f"### 🧠 Nhận xét: {dep} theo {x_label} ({n} quan sát)", ""]
    out.append(f"Đây là **hồi quy tuyến tính**: đo xem khi {x_label} thay đổi thì {dep} thay đổi bao nhiêu, "
               "và con số đó đáng tin đến đâu.")
    if ret_ctx:
        out.append("Biến có tiền tố **R_** là **lợi suất theo ngày**: phần trăm thay đổi của giá so với hôm trước, "
                   "viết dạng thập phân (0.01 nghĩa là 1%).")
    if n < MIN_OBS:
        out.append(f"> Mẫu nhỏ ({n} quan sát): các kiểm định chỉ mang tính tham khảo.")
    out.append("")

    out.append("**Đọc nhanh**")
    if spurious:
        out.append("- **Dữ liệu:** không đáng tin, vì có dấu hiệu hồi quy giả mạo (xem Bước 1).")
        out.append(f"- **Độ giải thích:** R² = {r2:.4f} trông cao nhưng không đáng tin, nên không dùng để kết luận.")
    else:
        out.append("- **Dữ liệu:** dùng được, vì các chuỗi đều dừng.")
        out.append(f"- **Độ giải thích:** {x_label} giải thích khoảng {r2 * 100:.1f}% biến động của {dep}.")
    if betas:
        fb = betas[0]["b"]
        fn = betas[0]["name"]
        if spurious:
            out.append(f"- **Hệ số chính:** β = {fb:.4f} chưa dùng được để kết luận.")
        elif ret_ctx:
            out.append(f"- **Hệ số chính:** β = {fb:.4f}: khi {fn} tăng 1% thì {dep} thay đổi trung bình {fb:.2f}%.")
        else:
            out.append(f"- **Hệ số chính:** β = {fb:.4f}: khi {fn} tăng 1 đơn vị thì {dep} thay đổi trung bình {fb:.4f} đơn vị.")
    if spurious:
        out.append("- **Kết luận:** không ra quyết định từ mô hình này; làm lại bằng lợi suất rồi kiểm tra lại.")
    else:
        out.append("- **Kết luận:** dùng được để đo độ nhạy và phân tách rủi ro; không dùng để dự báo giá chắc chắn.")
    out.append("")

    out.append("**Bước 1. Dữ liệu có dùng được không? (kiểm tra tính dừng)**")
    out.append("Chuỗi dừng dao động quanh một mức ổn định. Chuỗi không dừng (như giá cổ phiếu) trôi theo thời gian. "
               "Nếu hai chuỗi không dừng cùng trôi, hồi quy có thể cho R² cao dù không có quan hệ thật "
               "(gọi là hồi quy giả mạo). Kiểm định ADF với 4 trễ trên từng biến; τ càng âm càng có bằng chứng "
               "chuỗi dừng:")
    for label, stat_v, c5, ok in adf_rows:
        if stat_v is None:
            out.append(f"- {label}: không tính được (mẫu quá nhỏ).")
        else:
            verdict = "dừng." if ok else "không dừng."
            out.append(f"- {label}: τ = {stat_v:.4f}, ngưỡng 5% = {c5:.4f} → {verdict}")
    if nonstationary:
        out.append(f"**Kết luận:** có chuỗi không dừng ({names_nonstat}). Hồi quy có nguy cơ giả mạo.")
    else:
        out.append("**Kết luận:** mọi chuỗi đều dừng, nên hồi quy có cơ sở.")
    out.append("")
    out.append("**Bước 2. Mô hình có đáng tin không? (kiểm định chẩn đoán)**")
    if white is None:
        out.append("- **Phương sai thay đổi (White):** không tính được.")
    else:
        wp = float(white[1])
        if white_bad:
            out.append(f"- **Phương sai thay đổi (White):** {_p_text(wp)}. Nghĩa là mức dao động của sai số không đều "
                       "(lúc dao động mạnh, lúc yếu). Hệ quả: sai số chuẩn thường bị sai, nên t và p có thể sai. "
                       "**Đã làm:** dùng sai số chuẩn White, nên mọi kết luận về β bên dưới dựa trên sai số đã hiệu chỉnh.")
        else:
            out.append(f"- **Phương sai thay đổi (White):** {_p_text(wp)}. Nghĩa là không thấy mức dao động của sai số "
                       "thay đổi; sai số chuẩn thường dùng được.")
    if bg is None:
        out.append("- **Tự tương quan (Breusch–Godfrey):** không tính được.")
    else:
        bgp = float(bg[1])
        if bg_bad:
            out.append(f"- **Tự tương quan (Breusch–Godfrey):** {_p_text(bgp)}. Nghĩa là sai số hôm nay còn liên quan "
                       "đến hôm qua, tức mô hình bỏ sót động học theo thời gian. Hệ quả: sai số chuẩn có thể bị đánh giá thấp. "
                       "Nên thử thêm biến trễ hoặc sai số HAC (Newey–West).")
        else:
            out.append(f"- **Tự tương quan (Breusch–Godfrey):** {_p_text(bgp)}. Nghĩa là sai số hôm nay không liên quan "
                       "đáng kể đến hôm qua. Không có vấn đề ở bậc này.")
    if reset is None:
        out.append("- **Dạng hàm (RESET):** không tính được.")
    else:
        rp = float(reset.pvalue)
        if reset_bad:
            out.append(f"- **Dạng hàm (RESET):** {_p_text(rp)}. Nghĩa là đường thẳng có thể không phải dạng đúng; "
                       "quan hệ có thể cong hoặc thiếu biến quan trọng. Nên thử biến đổi (bình phương, lôgarit) "
                       "hoặc thêm biến rồi kiểm lại.")
        else:
            out.append(f"- **Dạng hàm (RESET):** {_p_text(rp)}. Nghĩa là đường thẳng là dạng phù hợp với dữ liệu.")
    if jb is None:
        out.append("- **Phân phối sai số (Jarque–Bera):** không tính được.")
    else:
        jbp, skew, kurt = float(jb[1]), float(jb[2]), float(jb[3])
        if jb_bad:
            out.append(f"- **Phân phối sai số (Jarque–Bera):** {_p_text(jbp)}; độ lệch = {skew:.3f}, độ nhọn = {kurt:.3f} "
                       "(chuẩn là 3). Nghĩa là sai số lệch hoặc có đuôi dày. Hệ quả: kiểm định t kém tin cậy trong mẫu nhỏ, "
                       "và VaR giả định chuẩn có thể đánh giá thấp tổn thất cực đoan.")
        else:
            out.append(f"- **Phân phối sai số (Jarque–Bera):** {_p_text(jbp)}; độ lệch = {skew:.3f}, độ nhọn = {kurt:.3f} "
                       "(chuẩn là 3). Nghĩa là sai số gần đối xứng, đuôi gần bình thường; kiểm định t và F đáng tin ở mức mẫu này.")
    if vifs:
        vif_text = ", ".join(f"{nm} = {v:.2f}" for nm, v in vifs)
        out.append(f"- **Đa cộng tuyến (VIF):** {vif_text}. Nghĩa là các biến giải thích có trùng nhau không. "
                   "VIF trên 10 là nặng, từ 5 đến 10 là vừa; khi nặng thì từng β không tin được riêng.")
    out.append("")
    out.append("**Bước 3. Mô hình giải thích được bao nhiêu?**")
    out.append(f"- **R² = {r2:.4f} ({r2 * 100:.1f}%)**: tỷ lệ biến động của {dep} được {x_label} giải thích. "
               f"Phần còn lại ({(1 - r2) * 100:.1f}%) là yếu tố riêng của {dep}, như tin tức, kết quả kinh doanh, "
               f"cung cầu riêng của cổ phiếu. R² hiệu chỉnh = {r2a:.4f} (phạt thêm khi có nhiều biến; dùng khi so sánh mô hình).")
    if spurious:
        out.append("- **Phân rã rủi ro:** không dùng, vì hồi quy có dấu hiệu giả mạo.")
    else:
        out.append(f"- **Phân rã rủi ro (theo độ lệch chuẩn hằng ngày):** {dep} dao động điển hình {amt(sd_y)}, trong đó "
                   f"phần do {x_label} ≈ {amt(sys_sd)}, phần riêng ≈ {amt(idio_sd)}. Đa dạng hóa giảm được phần riêng, "
                   "không giảm được phần do thị trường.")
        out.append("- Ngưỡng tham khảo: R² dưới 0.3 thì rủi ro chủ yếu là riêng; trên 0.7 thì chủ yếu theo thị trường; "
                   "ở giữa thì trộn cả hai.")
    if spurious:
        fit_text = ("F có ý nghĩa thống kê nhưng không đáng tin, vì hồi quy có dấu hiệu giả mạo "
                    "(hai chuỗi cùng trôi có thể làm F lớn).")
    elif fp < ALPHA:
        fit_text = "Quan hệ này khó là ngẫu nhiên, nên mô hình hợp lệ để đọc hệ số."
    else:
        fit_text = "Chưa đủ bằng chứng về quan hệ thật, không nên đọc hệ số."
    out.append(f"- **F = {fval:.2f}, {_p_text(fp)}**: kiểm định cả mô hình xem {x_label} có thật sự liên quan "
               f"đến {dep} không. {fit_text}")
    sd_note = ""
    if not spurious:
        sd_note = f" Con số này bằng {s_reg / sd_y * 100:.0f}% độ dao động ban đầu của {dep}."
    unit_note = "" if ret_ctx else f" (cùng đơn vị với {dep})"
    out.append(f"- **Sai số hồi quy (S.E.) = {amt(s_reg)}**: khi dùng {x_label} để ước lượng {dep}, sai lệch điển hình "
               f"khoảng {amt(s_reg)}{unit_note}.{sd_note}")
    if dw < 1.5:
        dw_text = "dưới 1.5, cho thấy sai số có liên quan theo thời gian (xem Bước 2)"
    elif dw > 2.5:
        dw_text = "trên 2.5, cho thấy sai số đảo chiều theo thời gian"
    else:
        dw_text = "gần 2 là tốt: sai số không kéo dài từ ngày này sang ngày khác"
    out.append(f"- **Durbin–Watson = {dw:.4f}**: {dw_text}.")
    out.append(f"- **AIC = {aic:.6f}, SC = {bic:.6f}** (chia theo số quan sát, như EViews): chỉ có nghĩa khi so với mô hình "
               "khác trên cùng dữ liệu; đứng một mình không kết luận gì.")
    out.append("")
    out.append("**Bước 4. Hệ số nói gì? (β và C)**")
    for bb in betas:
        b, se, lo, hi, p, name = bb["b"], bb["se"], bb["lo"], bb["hi"], bb["p"], bb["name"]
        out.append(f"- **β = {b:.6f}**: độ nhạy của {dep} với {name}.")
        if ret_ctx:
            out.append(f"  - Ý nghĩa: khi {name} tăng 1% thì {dep} thay đổi trung bình {b:.2f}%; các yếu tố khác giữ nguyên.")
        else:
            out.append(f"  - Ý nghĩa: khi {name} tăng 1 đơn vị thì {dep} thay đổi trung bình {b:.4f} đơn vị; các yếu tố khác giữ nguyên.")
        se_extra = ""
        if use_robust:
            se_extra = f" (SE thường = {bb['se_ols']:.6f}; {se_reason})"
        out.append(f"  - Độ chắc chắn: {se_label} = {se:.6f}{se_extra}. Khoảng tin cậy 95%: [{lo:.4f}; {hi:.4f}], "
                   "nghĩa là giá trị thật có khả năng 95% nằm trong khoảng này.")
        out.append(f"  - Kiểm định β khác 0: {_p_text(p)}, {_sig_text(p)}.")
        if spurious:
            out.append("  - Không phân loại và không ra quyết định từ β, vì hồi quy có dấu hiệu giả mạo.")
            continue
        if ret_ctx:
            t1, p1, key = bb["t1"], bb["p1"], bb["key"]
            test_text = "khác 1 có ý nghĩa thống kê." if p1 < ALPHA else "không đủ bằng chứng để nói khác 1."
            out.append(f"  - Kiểm định β = 1 (xem {dep} có đi đúng nhịp {name} không): t = {t1:.4f}, {_p_text(p1)}: {test_text}")
            out.append(f"  - Phân loại: {_beta_class_text(key)}.")
            out.append(f"  - Dùng để: làm kịch bản. Nếu {name} tăng 5%, {dep} trung bình thay đổi khoảng {b * 5:+.1f}%, "
                       f"và với khoảng tin cậy có thể thay đổi từ {lo * 5:+.1f}% đến {hi * 5:+.1f}%. "
                       "Đây là ước lượng trung bình trong mẫu, không phải dự báo.")
            out.append(f"  - Quyết định gợi ý: {_beta_decision(key, dep)}")
        else:
            out.append("  - Phân loại năng động hay phòng thủ chỉ áp dụng khi cả hai biến là lợi suất.")
            out.append(f"  - Dùng để: làm kịch bản. Nếu {name} tăng 1 đơn vị, {dep} trung bình thay đổi khoảng {b:.4f} đơn vị.")
    if c is not None:
        c_title = " (hằng số, còn gọi là alpha)" if ret_ctx else " (hằng số)"
        out.append(f"- **C = {c:.6f}**{c_title}.")
        if spurious:
            out.append(f"  - Kiểm định: {_p_text(pc)}, {_sig_text(pc)}. Không dùng để kết luận về lợi suất vượt trội, "
                       "vì hồi quy có dấu hiệu giả mạo.")
        elif ret_ctx:
            out.append(f"  - Ý nghĩa: phần lợi suất của {dep} không do thị trường giải thích, trung bình mỗi ngày ≈ "
                       f"{c * 100:.4f}% (quy ra ≈ {c * TRADING_DAYS * 100:.2f}% mỗi năm nếu là lợi suất ngày).")
            out.append(f"  - Kiểm định: {_p_text(pc)}, {_sig_text(pc)}.")
            if pc >= ALPHA:
                out.append("  - Quyết định gợi ý: không có bằng chứng về lợi suất vượt trội trong mẫu; "
                           "không nên coi mức này là lý do để trả phí.")
            else:
                out.append("  - Quyết định gợi ý: có lợi suất vượt trội trong mẫu; cần kiểm chứng trên dữ liệu ngoài mẫu "
                           "và sau phí trước khi tin.")
        else:
            out.append(f"  - Ý nghĩa: giá trị của {dep} khi các biến giải thích bằng 0. Vì không phải lợi suất, "
                       "C không phải alpha và không dùng để đánh giá vượt trội.")
            out.append(f"  - Kiểm định: {_p_text(pc)}, {_sig_text(pc)}.")
    out.append("")

    out.append("**Bước 5. Kết luận và việc nên làm**")
    if spurious:
        out.append("- Không ra quyết định từ β, C hay R² của mô hình này.")
        out.append("- Việc nên làm: lấy lợi suất (sai phân lôgarit của giá), kiểm tra tính dừng, rồi hồi quy lại.")
    else:
        out.append("- **Dùng được để:** đo độ nhạy β với biến giải thích; phân tách rủi ro bằng R²; "
                   "kiểm tra có lợi suất vượt trội không (C).")
        out.append(f"- **Chưa nên dùng để:** dự báo giá chắc chắn, khẳng định nguyên nhân, hay chọn cổ phiếu chỉ dựa trên "
                   f"{n} quan sát.")
        if reset_bad:
            out.append("- Dạng hàm chưa phù hợp: đừng đọc β như hệ số cố định trước khi sửa mô hình.")
        if use_robust:
            out.append("- Các kết luận về β đã dùng sai số chuẩn White.")
        if bg_bad:
            out.append("- Có tự tương quan: sai số chuẩn có thể bị đánh giá thấp; cân nhắc thêm biến trễ.")
        if jb_bad:
            out.append("- Đuôi phân phối dày: đừng ước lượng tổn thất cực đoan bằng VaR giả định chuẩn.")
    out.append("")
    out.append("> Đây là nhận xét học thuật trên dữ liệu quá khứ, không phải khuyến nghị mua hay bán.")
    return "\n".join(out)


GLOSSARY = [
    ("Lợi suất theo ngày (R_)", "phần trăm thay đổi của giá so với hôm trước, viết dạng thập phân: 0.01 là 1%."),
    ("Hồi quy tuyến tính", "đường thẳng tốt nhất mô tả Y thay đổi theo X như thế nào."),
    ("β (độ nhạy)", "khi X tăng 1 đơn vị, Y thay đổi trung bình β đơn vị, các yếu tố khác giữ nguyên. Với lợi suất, β là độ nhạy với thị trường."),
    ("C (hằng số, alpha)", "giá trị của Y khi X bằng 0. Với lợi suất, là phần lợi suất không do thị trường giải thích."),
    ("R²", "tỷ lệ biến động của Y được X giải thích, từ 0 đến 1 (nhân 100 để ra phần trăm)."),
    ("Sai số chuẩn (SE)", "độ bất định của một hệ số; SE càng nhỏ thì ước lượng càng chắc."),
    ("Khoảng tin cậy 95%", "khoảng chứa giá trị thật với xác suất 95% nếu lặp lại việc lấy mẫu nhiều lần."),
    ("p-value", "nếu thực tế không có quan hệ, xác suất thấy kết quả như vậy hoặc cực đoan hơn. p dưới 0.05 là ngưỡng thường dùng để nói có ý nghĩa thống kê."),
    ("Chuỗi dừng và nghiệm đơn vị", "chuỗi dừng dao động quanh một mức ổn định; chuỗi có nghiệm đơn vị là chuỗi không dừng, trôi theo thời gian."),
    ("Hồi quy giả mạo", "hai chuỗi không dừng cùng trôi nên R² cao dù không có quan hệ thật."),
    ("Phương sai thay đổi", "mức dao động của sai số không đều theo thời gian hoặc theo X. Xử lý bằng sai số chuẩn White."),
    ("Tự tương quan", "sai số hôm nay liên quan đến hôm qua. Durbin–Watson gần 2 là không có tự tương quan bậc 1."),
    ("Đa cộng tuyến (VIF)", "các biến giải thích trùng nhau. VIF trên 10 là nặng."),
    ("Dạng hàm (RESET)", "kiểm tra quan hệ có đúng là đường thẳng không."),
    ("Jarque–Bera", "kiểm tra sai số có gần phân phối chuẩn không. Độ nhọn chuẩn là 3."),
    ("AIC và SC", "thước đo chất lượng mô hình; nhỏ hơn là tốt, chỉ so sánh giữa các mô hình trên cùng dữ liệu."),
    ("VaR", "mức tổn thất có thể xảy ra với một xác suất cho trước trong một khoảng thời gian; dựa trên giả định về phân phối."),
]


def glossary_markdown():
    lines = ["**Từ khóa cho người mới**"]
    for term, meaning in GLOSSARY:
        lines.append(f"- **{term}**: {meaning}")
    return "\n".join(lines)


def commentary_for(res):
    if not isinstance(res, dict) or res.get("error"):
        return None
    if "results" in res:
        return ls_commentary(res)
    if "adf" in res:
        return adf_commentary(res["adf"])
    return None
