"""Bản đọc trước thân thiện học sinh phổ thông cho sáu bài đại học.

Yêu cầu của sản phẩm: học sinh cấp ba muốn đọc trước kiến thức đại học thì
được mở, nhưng nội dung phải trình bày đủ bốn phần — giải thích dễ hiểu,
ví dụ minh họa tính tay được, ứng dụng gần gũi và câu phản tư hợp lý.

Nội dung tách khỏi :mod:`curriculum_university` để lộ trình đại học giữ
nguyên văn phong giáo trình. Module này chỉ là lớp "dịch" cho học sinh:
không đụng schema ``Lesson``, không chấm điểm, không trỏ tới công cụ nâng
cao một cách làm lệch cổng mở (nơi nhắc công cụ nâng cao đều ghi rõ là
phải đạt cổng tiến độ).
"""

from __future__ import annotations

# Thứ tự và nhãn của bốn phần khi hiển thị.
TEEN_HEADINGS: tuple[tuple[str, str], ...] = (
    ("easy", "Nói dễ hiểu"),
    ("example", "Ví dụ minh họa"),
    ("application", "Ứng dụng vào tình huống của em"),
    ("reflection", "Phản tư"),
)

_TEEN_PARTS: dict[str, dict[str, str]] = {
    "dh1_loi_suat": {
        "easy": (
            "Lợi suất trả lời một câu hỏi: bỏ ra 100 nghìn, nhận lại thêm "
            "bao nhiêu phần trăm? Công thức chỉ là (giá mới − giá cũ) chia "
            "giá cũ. Khi thay đổi rất nhỏ — mỗi phiên, mỗi ngày — người ta "
            "thường ghi lợi suất theo logarit vì có một tiện lợi: cộng dồn "
            "nhiều kỳ chỉ thành một phép cộng, như cộng điểm từng bài để ra "
            "điểm tổng."
        ),
        "example": (
            "Cổ phiếu tăng từ 20 lên 21 nghìn đồng: lợi suất = (21 − 20)/20 "
            "= 5%. Tính theo logarit: ln(21/20) ≈ 4,88% — hơi lệch vì mức "
            "tăng nhỏ. Sang danh mục: chia 1 triệu thành 300 nghìn cho A "
            "(kỳ vọng 1%), 200 nghìn cho B (2%) và 500 nghìn cho C (3%), "
            "lợi suất kỳ vọng = 0,3×1% + 0,2×2% + 0,5×3% = 2,2% — đúng kiểu "
            "tính điểm trung bình môn có hệ số, và ba tỷ trọng cộng lại "
            "phải đúng 100%."
        ),
        "application": (
            "So sánh hai lựa chọn — gửi tiết kiệm 5% mỗi năm với cổ phiếu "
            "tăng 1% mỗi tuần — việc đầu tiên là quy về cùng chu kỳ thời "
            "gian; quy tắc \"cùng chu kỳ\" của bài dùng được ngay khi đọc "
            "bất kỳ lời khuyên đầu tư nào. Tỷ trọng w cũng là chiếc kính "
            "nhìn danh mục của chính em: tiền đang nằm ở đâu, mỗi phần chiếm "
            "vài phần trăm."
        ),
        "reflection": (
            "Cổ phiếu A tăng 50% trong một năm, B tăng 9% mỗi quý trong sáu "
            "quý: lựa chọn nào có lợi hơn, và cần thêm dữ kiện gì để chắc "
            "chắn? Nếu một ngày em thấy quảng cáo \"lợi suất 30%, đã gồm cả "
            "cổ tức\", em sẽ hỏi lại điều gì trước khi tin?"
        ),
    },
    "dh2_do_dao_dong": {
        "easy": (
            "Độ dao động σ đo một thứ: giá trị tài khoản nhảy lên nhảy xuống "
            "mạnh đến đâu. Hiệp phương sai đo thêm một thứ: tài sản này lên "
            "thì tài sản kia có chạy theo không. Công thức ma trận trông "
            "phức tạp nhưng tinh thần đơn giản — ghép những tài sản không "
            "đồng hành với nhau thì biến động của từng cái triệt tiêu nhau "
            "một phần, như hai con sóng lệch pha gặp nhau làm mặt nước "
            "phẳng hơn."
        ),
        "example": (
            "Hai tài sản, mỗi cái biến động 20% một năm, chia tiền đều "
            "50–50. Nếu hai cái luôn đồng hành (tương quan 1): danh mục vẫn "
            "biến động đúng 20% — chia cỡ nào cũng không đỡ rủi ro. Nếu hai "
            "cái chẳng liên quan (tương quan 0): biến động còn "
            "√(0,25×20%² + 0,25×20%²) ≈ 14,1%. Cùng số tiền, chỉ khác việc "
            "chọn tài sản không đồng hành, rủi ro đã giảm gần một phần ba — "
            "tính tay được trên giấy nháp."
        ),
        "application": (
            "Đây là bài toán thật khi giữ tiền: nắm 10 mã nhưng cả 10 đều "
            "cùng một ngành thì gần như vẫn là \"một giỏ trứng\". Mở Danh "
            "mục mô phỏng trong app, nhìn vào các vị trí em đang giữ và tự "
            "hỏi: nếu ngành này xấu đi cùng lúc, bao nhiêu vị trí rơi cùng "
            "nhau? Thêm tài sản lệch nhịp mới gọi là đa dạng thật."
        ),
        "reflection": (
            "Vì sao nắm 20 mã cùng ngành không phải là đa dạng hóa thật "
            "sự? Nếu hai tài sản tương quan âm hoàn hảo — một lên đúng "
            "khi kia xuống — em có còn rủi ro gì không, và kiểu tương tác "
            "đó có tồn tại bền vững ngoài đời thật không?"
        ),
    },
    "dh3_sim_gia_thiet": {
        "easy": (
            "Hình dung cả thị trường như thủy triều: nước dâng thì mọi con "
            "thuyền dâng theo. Mô hình chỉ số đơn chỉ làm hai việc — đo "
            "thủy triều (lợi suất chỉ số) và đo mỗi con thuyền nổi theo "
            "triều nhạy cỡ nào qua chỉ số β. Phần còn lại của chuyển động, "
            "sóng riêng của từng con thuyền, gọi là nhiễu ε. β trên 1 là "
            "thuyền năng động, nhạy hơn triều; β dưới 1 là thuyền thụ "
            "động, lười theo triều."
        ),
        "example": (
            "Hồi quy một cổ phiếu ngân hàng cho ra r_i = 0,0005 + 1,07·r_I. "
            "Đọc thế này: phiên bình thường cổ phiếu có phần riêng rất nhỏ "
            "(γ = 0,0005), và khi chỉ số tăng 1% thì cổ phiếu tăng trung "
            "bình khoảng 1,07% — nhạy hơn thị trường một chút. Ngược lại, "
            "cổ phiếu có β = 0,6: thị trường tăng 1% thì nó tăng khoảng "
            "0,6%, trầm hơn thị trường."
        ),
        "application": (
            "β giúp em chọn \"độ đậm đặc rủi ro\": muốn đi cùng thị trường "
            "mạnh thì chọn β cao, muốn bình tĩnh hơn thì β thấp. Nhưng đừng "
            "đọc thành \"β cao tốt hơn\" — khi thị trường đỏ, β cao đỏ theo "
            "còn sâu. Trong app, công cụ SIM nằm ở nhóm nâng cao: mở được "
            "khi em đạt cổng bốn bài 70/100, lúc đó đọc β từng mã để xếp "
            "chúng thành nhóm năng động hay thụ động."
        ),
        "reflection": (
            "Một công ty gặp bê bối riêng, giá lao dốc trong khi thị trường "
            "đứng yên: phần biến động đó thuộc \"triều\" hay \"sóng riêng\"? "
            "Vì sao hai cổ phiếu cùng ngành thường làm giả thiết \"sóng "
            "riêng của các mã không liên quan nhau\" trở nên sai?"
        ),
    },
    "dh4_phan_ra_rui_ro": {
        "easy": (
            "Tổng rủi ro của một cổ phiếu gồm hai lớp: lớp thị trường — cả "
            "sàn chuyển động cùng nhau — và lớp riêng của doanh nghiệp. "
            "Công thức β²·σ_I² + η² là cách ghi lại phép chia hai lớp đó. "
            "Chỉ số R² của mô hình cho biết thị trường chiếm bao nhiêu phần "
            "trăm câu chuyện của mã này: R² = 0,43 nghĩa là khoảng 43% biến "
            "động đến từ thủy triều chung, phần còn lại là chuyện riêng."
        ),
        "example": (
            "Hồi quy một cổ phiếu cho tổng biến động σ² ≈ 0,000344 và phần "
            "nhiễu riêng η² ≈ 0,000198. Rủi ro hệ thống = 0,000344 − "
            "0,000198 ≈ 0,000146, tức khoảng 42% tổng rủi ro — khớp với R² "
            "của mô hình. Toàn bài toán chỉ là một phép trừ."
        ),
        "application": (
            "Khủng hoảng là minh họa sống: công ty vẫn kinh doanh tốt nhưng "
            "giá vẫn rơi theo cả sàn — đó là rủi ro hệ thống, thêm bao "
            "nhiêu mã cũng không xóa được. Đa dạng hóa chỉ triệt phần riêng "
            "(η). Hiểu điều này, em sẽ không nói \"mua đủ 30 mã là an toàn "
            "tuyệt đối\" nữa."
        ),
        "reflection": (
            "Em nắm 30 mã, một buổi cả sàn đỏ và tài khoản lỗ nặng: phần "
            "rủi ro nào chưa được triệt tiêu, vì sao? R² cao hay thấp mới "
            "đáng mong muốn — câu trả lời có \"đúng\" không, hay tùy người "
            "nắm giữ muốn gì?"
        ),
    },
    "dh5_quy_trinh_uoc_luong": {
        "easy": (
            "Trước khi tìm quy luật trong dữ liệu thời gian, phải kiểm tra "
            "dữ liệu có \"đứng yên quanh một mức\" không — gọi là tính "
            "dừng. Cân chưa chuẩn thì cân bao nhiêu cũng sai; hồi quy trên "
            "chuỗi chưa dừng cho ra mô hình trông rất thuyết phục nhưng "
            "thực chất là quy luật giả mạo. Giáo trình bắt buộc ba bước đi "
            "đúng thứ tự: kiểm dừng bằng Dickey–Fuller mở rộng, rồi hồi "
            "quy, rồi kiểm dạng hàm bằng Ramsey — không được đảo."
        ),
        "example": (
            "Kiểm định cho một chuỗi lợi suất cho τ = −9,90 trong khi ngưỡng "
            "tới hạn 1% là −3,45. Vì |−9,90| vượt xa |−3,45|, bác bỏ giả "
            "thiết \"không dừng\": chuỗi ổn định, đủ điều kiện hồi quy. "
            "Câu chuyện ngược lại: τ = −2,10 với ngưỡng −2,87 thì chưa đủ "
            "cơ sở — phải dừng tay, không hồi quy vội."
        ),
        "application": (
            "Thói quen này dùng được cho mọi con số được truyền miệng: trước "
            "khi tin \"chỉ số này dự báo được giá\", hãy hỏi dữ liệu gốc có "
            "ổn định không, mô hình đã kiểm khuyết tật chưa. Công cụ EViews "
            "tiếng Việt và các kiểm định nằm ở nhóm nâng cao, mở sau cổng "
            "bốn bài; khi tới đó, chạy ADF rồi LS đúng thứ tự sẽ thành phản "
            "xạ."
        ),
        "reflection": (
            "Vì sao một mô hình cho hệ số đẹp và thống kê t khổng lồ vẫn có "
            "thể hoàn toàn vô nghĩa? Bạn bè em khoe mô hình dự đoán giá chỉ "
            "từ chuỗi giá thô: câu hỏi đầu tiên em dùng để soi là gì?"
        ),
    },
    "dh6_markowitz": {
        "easy": (
            "Câu hỏi của Markowitz rất đời thường: muốn mức lợi kỳ vọng là "
            "X, chọn tỷ trọng nào để biến động nhỏ nhất? Tập hợp các đáp án "
            "tốt nhất cho từng mức X gọi là biên duyên; lấy nửa trên — cùng "
            "mức rủi ro nhưng lợi hơn — được biên hiệu quả, với hình quả "
            "chuông quen thuộc trong mọi sách tài chính. Bốn đại lượng A, "
            "B, C, D chỉ là máy rút gọn: tính một lần là suy ra toàn bộ "
            "danh mục biên duyên, không phải lặp lại thủ tục cho từng mức."
        ),
        "example": (
            "Thử với hai tài sản: tỷ trọng 100%–0%, rồi 50%–50%, rồi "
            "0%–100%. Tính lợi suất kỳ vọng và biến động của từng trường "
            "hợp bằng công thức hai tài sản ở bài trước, rồi vẽ ba điểm lên "
            "trục (biến động, lợi suất) và nối lại — điểm đẹp nhất nằm ở "
            "giữa, chính là mầm mống của đường biên. Với nhiều tài sản, "
            "công thức A, B, C, D làm việc đó một cách hệ thống."
        ),
        "application": (
            "Ý tưởng này chạy bên dưới những sản phẩm em sẽ gặp sau này: "
            "quỹ đa tài sản, ứng dụng tư vấn phân bổ vốn. Nhưng nhớ cái bẫy "
            "của bài gốc: nghiệm tối ưu cực nhạy với con số lợi kỳ vọng ta "
            "đặt vào — ước lượng lệch một chút, \"tối ưu\" hóa ra chỉ là "
            "ảo. Cách phòng là thử nhiều kịch bản thay vì tin một điểm duy "
            "nhất; trong app, công cụ Danh mục Markowitz mở sau cổng bốn "
            "bài để em trải nghiệm chính điều đó."
        ),
        "reflection": (
            "Hai người ước lượng lợi kỳ vọng chỉ khác nhau một chút: danh "
            "mục \"tối ưu\" của họ lệch nhau cỡ nào? Vì sao tin tuyệt đối "
            "vào một tỷ trọng tối ưu nguy hiểm hơn cả việc chọn sai tỷ "
            "trọng?"
        ),
    },
}


def teen_parts(lesson_id: str) -> dict[str, str] | None:
    """Bốn phần thân thiện học sinh cho một bài đại học, hoặc ``None``.

    Trả về ``None`` cho bài chưa được dịch để tầng hiển thị bỏ qua thay vì
    hiện khối thiếu nội dung.
    """

    return _TEEN_PARTS.get(str(lesson_id or "").strip())


def covered_lesson_ids() -> tuple[str, ...]:
    """Danh sách bài đại học đã có bản đọc trước, theo thứ tự khai báo."""

    return tuple(_TEEN_PARTS.keys())
