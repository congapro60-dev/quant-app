"""Nội dung giới thiệu Chứng khoán trên MoMo — tra cứu, không mời gọi.

Nguyên tắc (khớp với provider_directory.py):
- **Chỉ ghi điều có nguồn chính chủ.** Số liệu phí, sàn, khung giờ lấy nguyên
  từ https://www.momo.vn/chung-khoan (đọc ngày 24/10/2026). Đổi chính sách là
  số trong tệp này sai theo, nên mỗi mục đều kèm ngày đọc và URL.
- **Không suy diễn chính sách tuổi.** Điều kiện tuổi của CVS do CVS quy định;
  những gì luật cho phép khác với những gì một công ty chứng khoán nhận. Tách
  rõ hai thứ đó thay vì gộp thành một câu chắc nịch.
- **Cảnh báo đặt ngang, không giấu cuối trang.** Rủi ro mất vốn và các hành vi
  bị pháp luật cấm nằm cùng một khối nhìn thấy được, không phải chú thích mờ.

Tệp này không phải ý kiến pháp lý. Trước khi nộp tiền thật, người học và phụ
huynh phải đọc văn bản hiện hành và hỏi trực tiếp CVS.
"""

from __future__ import annotations

import streamlit as st

MOMO_URL = "https://www.momo.vn/chung-khoan"
MOMO_FEE_URL = "https://www.momo.vn/hoi-dap/bieu-phi-giao-dich-chung-khoan"
SOURCE_DATE = "24/10/2026"

# Nguồn pháp lý: Thông tư 120/2020/TT-BTC (sửa đổi bởi Thông tư 68/2024/TT-BTC)
# hướng dẫn giao dịch chứng khoán trên hệ thống giao dịch. Không dẫn số điều cụ
# thể vì có thể bị sửa tiếp; chỉ nêu tên văn bản để người đọc tự tra bản mới nhất.
LEGAL_DOCS = (
    "Luật Chứng khoán 2019 (số 54/2019/QH14), sửa đổi bởi Luật số 56/2024/QH15",
    "Thông tư 120/2020/TT-BTC và các thông tư sửa đổi của Bộ Tài chính về giao dịch chứng khoán",
    "Bộ luật Dân sự 2015 về năng lực hành vi dân sự và người đại diện theo pháp luật",
)

# ---------------------------------------------------------------------------
# Điều kiện tuổi — hai nhánh tách hẳn, không gộp
# ---------------------------------------------------------------------------

AGE_TRACKS = (
    {
        "who": "Từ đủ 18 tuổi trở lên",
        "can": "Tự mở tài khoản giao dịch bằng chính danh của mình.",
        "requires": (
            "Có năng lực hành vi dân sự đầy đủ.",
            "Không thuộc trường hợp mất hoặc bị hạn chế năng lực hành vi dân sự.",
            "Có căn cước công dân để định danh điện tử (eKYC) trên ứng dụng.",
        ),
        "tone": "ok",
    },
    {
        "who": "Từ đủ 15 tuổi đến chưa đủ 18 tuổi",
        "can": (
            "Được mở tài khoản giao dịch nếu không bị mất hoặc hạn chế năng lực "
            "hành vi dân sự — nhưng **phải được người đại diện theo pháp luật "
            "đồng ý** (cha, mẹ hoặc người giám hộ hợp pháp)."
        ),
        "requires": (
            "Ý kiến đồng ý của người đại diện theo pháp luật — thường bằng giấy "
            "đồng ý có xác nhận, không chỉ lời nói.",
            "Tài khoản và tiền trong tài khoản vẫn thuộc về em; nghĩa vụ pháp lý "
            "gắn với em và người đại diện cùng lúc.",
            "Tiền dùng để đầu tư phải là tiền của gia đình cho phép, không phải "
            "tiền vay hoặc tiền đi vay bạn bè.",
        ),
        "tone": "warn",
    },
)

AGE_CAVEAT = (
    "Phần trên là những gì **pháp luật cho phép**. Điều kiện thực tế để mở được "
    "tài khoản còn tuỳ chính sách của CVS (ví dụ quy trình eKYC có nhận người "
    "chưa đủ 18 tuổi hay không). Trang chính chủ của MoMo **không nêu điều kiện "
    "tuổi**, nên đừng coi phần này là cam kết của CVS. Muốn chắc: gọi tổng đài "
    "MoMo 1900 5454 41 hoặc hỏi trực tiếp CVS trước khi nộp bất kỳ khoản tiền nào."
)

# ---------------------------------------------------------------------------
# Sản phẩm và phí — chép nguyên từ trang chính chủ
# ---------------------------------------------------------------------------

PRODUCTS = (
    ("Cổ phiếu niêm yết", "HOSE, HNX, UPCOM", "Phổ biến nhất; cổ đông nhỏ lẻ."),
    ("Chứng quyền có bảo đảm", "HOSE", "⚠️ Có đòn bẩy, biến động rất mạnh, có thể mất toàn bộ vốn."),
    ("Chứng chỉ quỹ", "HOSE, HNX, UPCOM", "Rổ nhiều mã; biến động êm hơn cổ phiếu lẻ."),
    ("Trái phiếu niêm yết", "HOSE, HNX", "Thu nhập cố định; rủi ro tổ chức phát hành."),
)

FEES = (
    ("Mở tài khoản giao dịch", "Miễn phí", "Mở online 100% trên MoMo."),
    ("Nạp/rút qua Túi Thần Tài hoặc MoMo", "Miễn phí", "Nạp từ ngân hàng có thể bị phí của ngân hàng."),
    ("Phí giao dịch cổ phiếu, chứng quyền, chứng chỉ quỹ", "0,1% giá trị khớp lệnh",
     "Đã bao gồm 0,027% phí sở giao dịch thu."),
    ("Phí lưu ký", "0,27 đồng/chứng khoán/tháng", "Tính hằng tháng trên số chứng khoán đang giữ."),
    ("Thuế thu nhập cá nhân khi bán", "0,1% giá trị khớp lệnh", "Nhà nước thu — áp dụng cho **mỗi lần bán**, kể cả bán lỗ."),
    ("Thuế cổ tức bằng cổ phiếu, cổ phiếu thưởng", "5% mệnh giá", "Nhà nước thu."),
)

FEE_WARNING = (
    "Con số dễ bị bỏ qua nhất là **thuế 0,1% mỗi lần bán, kể cả khi bán lỗ**. "
    "Mua bán 10 lần một tháng với danh mục 10 triệu đồng: riêng thuế và phí "
    "giao dịch đã ~20.000 đồng, chưa tính lưu ký. Lướt sóng nhỏ liên tục thì "
    "phí ăn hết phần lãi mỏng — đây là lý do ứng dụng dặn ghi lý do trước khi "
    "đặt lệnh, chứ không phải để thử cảm giác."
)

TRADING_HOURS = (
    ("HOSE", "09:00–11:30 và 13:00–14:45"),
    ("HNX", "09:00–11:30 và 13:00–15:00"),
    ("UPCOM", "09:00–11:30 và 13:00–15:00"),
)

HOURS_NOTE = (
    "Thứ Hai đến thứ Sáu, trừ ngày lễ Tết. Lệnh đặt trong giờ nghỉ trưa được "
    "gửi lên sàn lúc 13:00; lệnh đặt sau 18:00 được gửi lúc 09:00 ngày giao "
    "dịch kế tiếp."
)

# ---------------------------------------------------------------------------
# Cảnh báo pháp lý — bắt buộc, không rút gọn
# ---------------------------------------------------------------------------

LEGAL_WARNINGS = (
    {
        "title": "Những việc bị pháp luật nghiêm cấm",
        "body": (
            "Luật Chứng khoán 2019 quy định các hành vi bị cấm, trong đó có: "
            "**thao túng thị trường**, **giao dịch nội gián** (dùng thông tin "
            "chưa công bố để mua bán), **tạo dựng hoặc loan truyền thông tin sai "
            "sự thật** gây ảnh hưởng giá, và **lôi kéo người khác mua bán** bằng "
            "thông tin sai lệch. Các hành vi này có thể bị xử phạt hành chính "
            "hoặc truy cứu trách nhiệm hình sự tuỳ mức độ."
        ),
    },
    {
        "title": "Tài khoản đứng tên em — trách nhiệm cũng của em",
        "body": (
            "Mở tài khoản bằng căn cước của mình nghĩa là mọi lệnh trên tài khoản "
            "đó đều gắn với tên em. **Cho người khác mượn tài khoản** (nhờ người "
            "lớn đặt lệnh hộ, hoặc cho bạn dùng chung tài khoản) là vi phạm quy "
            "định của công ty chứng khoán và có thể bị khoá tài khoản; nặng hơn, "
            "em phải chịu trách nhiệm cho những lệnh mình không hề đặt."
        ),
    },
    {
        "title": "Không có ai bảo đảm lãi",
        "body": (
            "Mọi lời hứa **'lãi cố định 2%/tháng', 'bao lỗ', 'chắc thắng'** đều "
            "là dấu hiệu lừa đảo hoặc đa cấp trái phép. Công ty chứng khoán hợp "
            "pháp không bao giờ hứa lợi nhuận và không nhận tiền chuyển vào tài "
            "khoản cá nhân của nhân viên. Chỉ nộp tiền vào tài khoản mang tên "
            "chính em mở tại CVS, không chuyển cho một cá nhân."
        ),
    },
    {
        "title": "Quảng cáo trên mạng xã hội không phải lời khuyên đầu tư",
        "body": (
            "Nhiều nhóm, kênh TikTok/YouTube hướng dẫn mua bán cổ phiếu có nhận "
            "hoa hồng hoặc đang cầm hàng chờ bán. Họ không chịu trách nhiệm nếu "
            "em lỗ. Trước khi nghe ai, yêu cầu họ nêu số giấy phép hành nghề môi "
            "giới chứng khoán — luật yêu cầu người hành nghề phải có chứng chỉ."
        ),
    },
    {
        "title": "Thứ tự đúng: học — mô phỏng — rồi mới tiền thật",
        "body": (
            "Trong ứng dụng này, hãy **hoàn thành bài học, luyện bằng danh mục mô "
            "phỏng, rồi mới nghĩ đến tiền thật**. Nếu em chưa làm được điều đó "
            "với tiền ảo 500 triệu đồng trong vài tháng, thì với 2 triệu đồng thật "
            "em cũng sẽ mắc đúng lỗi đó — chỉ khác là mất tiền thật."
        ),
    },
)

RISK_STATEMENT = (
    "**Cảnh báo rủi ro:** đầu tư chứng khoán có thể mất một phần hoặc toàn bộ "
    "vốn. Kết quả quá khứ không bảo đảm tương lai. Ứng dụng này chỉ để học, không "
    "phải lời khuyên đầu tư, không phải lời mời mua bán chứng khoán."
)

# Ghi chú riêng của ứng dụng — phần duy nhất không lấy từ nguồn ngoài.
APP_STANCE = (
    "Ứng dụng **không** hưởng hoa hồng, không có mã giới thiệu, không xếp hạng nhà "
    "cung cấp. Mục này tồn tại vì nhiều em hỏi 'học xong thì làm thật ở đâu' — "
    "câu trả lời ngắn nhất là mở tài khoản ngay trên một ứng dụng em đã có. Nhưng "
    "mở được không có nghĩa là nên mở ngay."
)


def age_checklist(track_index: int) -> tuple[str, ...]:
    """Trả về các bước chuẩn bị cho đúng nhóm tuổi đang chọn."""

    common_tail = (
        "Đọc bảng phí bên trên và tính thử phí cho đúng số lệnh em định đặt.",
        "Chuẩn bị sẵn câu trả lời cho câu hỏi: nếu khoản này mất 30%, em làm gì?",
    )
    if track_index == 0:
        return (
            "Căn cước công dân còn hiệu lực để eKYC.",
            "Số điện thoại đã đăng ký chính chủ trùng tên trên căn cước.",
            "Đọc mục cảnh báo pháp lý trong tab này trước khi bấm 'Mở tài khoản ngay'.",
        ) + common_tail
    return (
        "Trao đổi với cha/mẹ hoặc người giám hộ, và có văn bản đồng ý rõ ràng.",
        "Người đại diện cùng đọc mục cảnh báo pháp lý trong tab này.",
        "Xác nhận với CVS (qua MoMo hoặc hotline) rằng hồ sơ của người chưa đủ 18 "
        "tuổi được chấp nhận, trước khi nộp tiền.",
        "Căn cước công dân còn hiệu lực để eKYC.",
    ) + common_tail


# ---------------------------------------------------------------------------
# Hiển thị
# ---------------------------------------------------------------------------

def render_momo_guide() -> None:
    """Tab giới thiệu Chứng khoán trên MoMo: tra cứu trước, cảnh báo ngang tầm."""

    st.subheader("Chứng khoán trên MoMo — tra cứu trước khi làm thật")
    st.caption(
        f"Sản phẩm **Chứng Khoán** trên MoMo do **Công ty Cổ phần Chứng khoán CV "
        f"(CVS)** cung cấp, MoMo là nền tảng công nghệ. Số liệu dưới đây chép từ "
        f"trang chính chủ ngày {SOURCE_DATE}."
    )
    st.warning(RISK_STATEMENT, icon="⚠️")

    st.markdown(f"**Vì sao có mục này trong ứng dụng học?** {APP_STANCE}")

    st.markdown("---")

    # 1. Tuổi -------------------------------------------------------------
    st.markdown("### 1. Bao nhiêu tuổi thì được mở tài khoản?")
    st.caption(
        "Luật chia thành hai nhánh khác nhau hẳn. Chọn đúng nhánh của em — "
        "nhiều trang trên mạng nói sai chỗ này."
    )
    labels = [f"{t['who']}" for t in AGE_TRACKS]
    chosen = st.radio(
        "Nhóm tuổi của em:", range(len(AGE_TRACKS)), index=None,
        format_func=lambda i: labels[i], key="momo_age_track",
    )
    if chosen is None:
        st.info("Chọn nhóm tuổi để xem điều kiện áp dụng cho em.")
    else:
        track = AGE_TRACKS[chosen]
        show = st.success if track["tone"] == "ok" else st.warning
        show(f"**{track['who']}** — {track['can']}",
             icon="✅" if track["tone"] == "ok" else "👨‍👩‍👧")
        st.markdown("**Chuẩn bị trước khi mở:**")
        for line in age_checklist(chosen):
            st.markdown(f"- {line}")

    st.caption(AGE_CAVEAT)

    st.markdown("---")

    # 2. Sản phẩm ---------------------------------------------------------
    st.markdown("### 2. Mua được gì trên đó?")
    st.dataframe(
        [{"Sản phẩm": p, "Sàn": s, "Ghi chú": n} for p, s, n in PRODUCTS],
        hide_index=True, width="stretch",
    )
    st.caption(
        "Ứng dụng này khoá chứng quyền và phái sinh với người chưa đủ 18 tuổi: "
        "đòn bẩy làm mất vốn nhanh hơn nhiều so với cổ phiếu thường."
    )

    # 3. Phí --------------------------------------------------------------
    st.markdown("### 3. Phí và thuế thật")
    st.dataframe(
        [{"Khoản": k, "Mức": v, "Ghi chú": n} for k, v, n in FEES],
        hide_index=True, width="stretch",
    )
    st.info(FEE_WARNING, icon="🧾")
    st.caption(
        f"Biểu phí áp dụng theo từng thời kỳ công bố — đối chiếu lại tại "
        f"[trang phí chính chủ]({MOMO_FEE_URL}) trước khi giao dịch."
    )

    # 4. Giờ giao dịch ----------------------------------------------------
    st.markdown("### 4. Giờ đặt lệnh")
    st.dataframe(
        [{"Sàn": s, "Giờ trong phiên": h} for s, h in TRADING_HOURS],
        hide_index=True, width="stretch",
    )
    st.caption(HOURS_NOTE)

    st.markdown("---")

    # 5. Cảnh báo pháp lý -------------------------------------------------
    st.markdown("### 5. Quy định pháp luật và cảnh báo — đọc hết trước khi nộp tiền")
    for item in LEGAL_WARNINGS:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.markdown(item["body"])

    st.markdown("**Văn bản gốc nên đọc cùng người lớn:**")
    for doc in LEGAL_DOCS:
        st.markdown(f"- {doc}")

    st.warning(
        "Ứng dụng không phải công ty chứng khoán, không nhận tiền, không đặt lệnh "
        "hộ em và không chịu trách nhiệm cho quyết định đầu tư của em.",
        icon="🚫",
    )
    st.caption(
        f"[Trang chính thức Chứng khoán trên MoMo]({MOMO_URL}) · Hotline MoMo "
        "1900 5454 41. Toàn bộ số liệu trong tab này lấy từ đó, không có nguồn thứ ba."
    )
