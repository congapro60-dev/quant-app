"""Mười bài học nền tảng cho học sinh trung học phổ thông.

Sáu bài tài chính (m1–m6) và bốn bài thống kê (s1–s4) bám SGK Kết nối tri thức
theo Chương trình 2018: Toán 10 (Bài 12–14), Toán 11 (Bài 8–9), Toán 12
(Bài 9–10). Bài học được xen kẽ theo nhịp làm dự án: mỗi bài thống kê đặt
ngay trước (hoặc ngay sau) bài tài chính cần dùng nó — s1 sau bài lợi suất
(dự báo kèm sai số), s2 trước bài rủi ro (biến động = độ lệch chuẩn), s3
trước bài biểu đồ (bảng tần số nuôi biểu đồ), s4 sau bài mô phỏng (so kết quả
theo giai đoạn). Toàn bộ nội dung và phần chấm điểm nằm cục bộ. Học sinh hoàn thành
được bài mà không cần khóa API hay kết nối tới mô hình ngôn ngữ lớn nào.

Mỗi bài có bảy phần theo yêu cầu chương trình: mục tiêu, giải thích, ví dụ,
phần tương tác, 3–5 câu hỏi, lỗi hiểu sai thường gặp và nguồn học liệu.

Phần tương tác dùng lại đúng bộ tính toán của ứng dụng (``kind`` trỏ tới một
widget đã có), thay vì dựng công cụ riêng cho bản THPT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Cấu trúc dữ liệu
# ---------------------------------------------------------------------------

QUESTION_SINGLE = "chon_mot"
QUESTION_NUMBER = "dien_so"


@dataclass(frozen=True)
class Question:
    """Một câu hỏi có đáp án vàng, chấm được cục bộ."""

    qid: str
    prompt: str
    kind: str
    options: tuple[str, ...] = ()
    answer_index: int | None = None
    answer_value: float | None = None
    tolerance: float = 0.01
    explanation: str = ""

    def check(self, response: Any) -> bool:
        """Chấm một câu trả lời. Sai kiểu hoặc thiếu đều tính là chưa đạt."""

        if self.kind == QUESTION_SINGLE:
            try:
                return int(response) == int(self.answer_index)
            except (TypeError, ValueError):
                return False
        if self.kind == QUESTION_NUMBER:
            try:
                value = float(response)
            except (TypeError, ValueError):
                return False
            if value != value:  # NaN
                return False
            if self.answer_value is None:
                return False
            return abs(value - self.answer_value) <= self.tolerance
        return False


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    order: int
    title: str
    objective: str
    explanation: str
    example: str
    interactive: str
    interactive_kind: str
    questions: tuple[Question, ...]
    misconceptions: tuple[tuple[str, str], ...]
    resources: tuple[tuple[str, str], ...]

    def grade(self, responses: dict[str, Any] | None) -> float:
        """Điểm 0–100 cho bài, chấm cục bộ."""

        if not self.questions:
            return 0.0
        answers = responses or {}
        correct = sum(1 for q in self.questions if q.check(answers.get(q.qid)))
        return round(correct / len(self.questions) * 100, 2)


# Nhãn cho phần tương tác; trỏ tới công cụ sẵn có của ứng dụng.
INTERACTIVE_COMPOUND = "may_tinh_lai_kep"
INTERACTIVE_MARKET = "bang_gia"
INTERACTIVE_RETURN = "may_tinh_loi_suat"
INTERACTIVE_RISK = "do_bien_dong"
INTERACTIVE_CHART = "doc_bieu_do"
INTERACTIVE_PAPER = "giao_dich_mo_phong"
INTERACTIVE_SAI_SO = "may_tinh_sai_so"
INTERACTIVE_DAC_TRUNG = "may_tinh_so_dac_trung"
INTERACTIVE_GHEP_NHOM = "phong_thi_nghiem_ghep_nhom"
INTERACTIVE_PHAN_TAN = "so_sanh_phan_tan"


# ---------------------------------------------------------------------------
# Nội dung mười bài học
# ---------------------------------------------------------------------------

LESSONS: tuple[Lesson, ...] = (
    Lesson(
        lesson_id="m1_tien_ngan_sach",
        order=1,
        title="Tiền, ngân sách, lãi kép và lạm phát",
        objective=(
            "Lập được một ngân sách cá nhân đơn giản, tính được lãi kép sau nhiều "
            "năm và giải thích được vì sao lạm phát làm giảm sức mua của tiền."
        ),
        explanation=(
            "Ngân sách là bảng đối chiếu giữa tiền vào và tiền ra trong một khoảng "
            "thời gian. Phần chênh lệch dương là số tiền bạn có thể để dành. "
            "Không có phần chênh lệch dương thì chưa có gì để đầu tư.\n\n"
            "Lãi kép là lãi được tính trên cả gốc lẫn phần lãi đã sinh ra trước đó. "
            "Công thức: giá trị tương lai bằng số tiền gốc nhân với (1 cộng lãi "
            "suất) lũy thừa số năm. Điểm mạnh của nó nằm ở thời gian, không nằm ở "
            "số tiền ban đầu.\n\n"
            "Lạm phát là mức tăng giá chung của hàng hóa và dịch vụ. Khi giá tăng, "
            "cùng một số tiền mua được ít hơn. Vì vậy phải so lãi suất với lạm "
            "phát, chứ không nhìn lãi suất một mình."
        ),
        example=(
            "Bạn để dành 10 triệu đồng, lãi suất 6% một năm, gửi trong 10 năm.\n\n"
            "Giá trị tương lai = 10.000.000 × (1 + 0,06)^10 ≈ 17.908.000 đồng.\n\n"
            "Nếu lạm phát trung bình 4% một năm thì lãi suất thực chỉ khoảng 2%. "
            "Sức mua thực tế tăng ít hơn nhiều so với con số 79% mà bạn nhìn thấy."
        ),
        interactive=(
            "Nhập số tiền gốc, lãi suất và số năm để xem giá trị tương lai. "
            "Thử đổi số năm trước, rồi đổi lãi suất, xem yếu tố nào làm kết quả "
            "thay đổi mạnh hơn."
        ),
        interactive_kind=INTERACTIVE_COMPOUND,
        questions=(
            Question(
                qid="m1_q1",
                prompt="Gửi 20 triệu đồng, lãi kép 5% một năm, sau 3 năm được bao nhiêu? Nhập đến hai chữ số thập phân, đơn vị triệu đồng.",
                kind=QUESTION_NUMBER,
                answer_value=23.15,
                tolerance=0.1,
                explanation="20 × 1,05³ ≈ 23,15 triệu đồng.",
            ),
            Question(
                qid="m1_q2",
                prompt="Lãi suất tiết kiệm 6% một năm, lạm phát 7% một năm. Sức mua của khoản tiền gửi sẽ thế nào?",
                kind=QUESTION_SINGLE,
                options=(
                    "Tăng, vì vẫn có lãi",
                    "Giảm, vì lạm phát cao hơn lãi suất",
                    "Không đổi",
                ),
                answer_index=1,
                explanation="Lãi suất thực âm nên sức mua giảm dù số dư danh nghĩa tăng.",
            ),
            Question(
                qid="m1_q3",
                prompt="Yếu tố nào làm lãi kép phát huy mạnh nhất?",
                kind=QUESTION_SINGLE,
                options=("Số tiền gốc lớn", "Thời gian dài", "Gửi nhiều ngân hàng"),
                answer_index=1,
                explanation="Số mũ trong công thức là số năm, nên thời gian có sức nặng lớn nhất.",
            ),
            Question(
                qid="m1_q4",
                prompt="Thu nhập một tháng 5 triệu, chi 5,4 triệu. Phần chênh lệch là bao nhiêu triệu đồng?",
                kind=QUESTION_NUMBER,
                answer_value=-0.4,
                tolerance=0.01,
                explanation="5 − 5,4 = −0,4 triệu đồng, tức là thâm hụt.",
            ),
        ),
        misconceptions=(
            (
                "Lãi kép chỉ đáng kể khi có nhiều tiền",
                "Sai. Số mũ là thời gian, nên bắt đầu sớm với số nhỏ thường hơn bắt "
                "đầu muộn với số lớn.",
            ),
            (
                "Có lãi là tiền đã sinh lời thật",
                "Chưa chắc. Phải trừ lạm phát mới ra lãi suất thực; lãi 6% khi lạm "
                "phát 7% là đang mất sức mua.",
            ),
            (
                "Ngân sách là việc của người đi làm",
                "Ngân sách chỉ là bảng tiền vào trừ tiền ra, áp dụng được cho mọi "
                "mức thu nhập.",
            ),
        ),
        resources=(
            ("Khung hiểu biết tài chính PISA 2022 (OECD)",
             "https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html"),
            ("Chương trình giáo dục phổ thông – Bộ Giáo dục và Đào tạo",
             "https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721"),
        ),
    ),
    Lesson(
        lesson_id="m2_co_phieu_thi_truong",
        order=2,
        title="Cổ phiếu và thị trường hoạt động thế nào",
        objective=(
            "Giải thích được cổ phiếu đại diện cho cái gì, lệnh được khớp ra sao và "
            "vì sao giá thay đổi trong phiên."
        ),
        explanation=(
            "Cổ phiếu là chứng nhận sở hữu một phần rất nhỏ của một doanh nghiệp. "
            "Người nắm cổ phiếu chia sẻ cả phần tốt lẫn phần xấu của doanh nghiệp đó.\n\n"
            "Giá không do một ai đặt ra. Nó hình thành khi lệnh mua và lệnh bán gặp "
            "nhau tại cùng một mức giá. Sàn Việt Nam khớp lệnh liên tục trong khung "
            "9:15–11:30 và 13:00–14:30, xen giữa là các phiên khớp lệnh định kỳ.\n\n"
            "Chỉ số như VNINDEX là mức trung bình có trọng số của nhiều cổ phiếu. "
            "Chỉ số tăng không có nghĩa mọi cổ phiếu đều tăng."
        ),
        example=(
            "Cổ phiếu CTG có người đặt mua giá 31,8 và người đặt bán giá 31,9. "
            "Chưa ai chịu nhường thì chưa có giao dịch.\n\n"
            "Khi một người mua chấp nhận trả 31,9 thì lệnh khớp, và 31,9 trở thành "
            "giá khớp gần nhất."
        ),
        interactive=(
            "Mở thẻ Giá trong phiên, chọn một mã và xem bảng lệnh khớp. "
            "Quan sát giá thay đổi theo từng lệnh và đối chiếu với độ trễ dữ liệu "
            "mà ứng dụng hiển thị."
        ),
        interactive_kind=INTERACTIVE_MARKET,
        questions=(
            Question(
                qid="m2_q1",
                prompt="Nắm giữ cổ phiếu nghĩa là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Cho doanh nghiệp vay tiền và chắc chắn được trả lãi",
                    "Sở hữu một phần của doanh nghiệp, chịu cả lãi lẫn lỗ",
                    "Được ngân hàng bảo hiểm khoản đầu tư",
                ),
                answer_index=1,
                explanation="Cổ phiếu là phần vốn chủ sở hữu, không phải khoản vay có bảo đảm.",
            ),
            Question(
                qid="m2_q2",
                prompt="Giá khớp hình thành khi nào?",
                kind=QUESTION_SINGLE,
                options=(
                    "Khi công ty chứng khoán công bố giá",
                    "Khi lệnh mua và lệnh bán gặp nhau tại cùng một mức giá",
                    "Khi hết phiên giao dịch",
                ),
                answer_index=1,
                explanation="Giá là kết quả khớp lệnh, không do một bên ấn định.",
            ),
            Question(
                qid="m2_q3",
                prompt="VNINDEX tăng thì có phải mọi cổ phiếu đều tăng không?",
                kind=QUESTION_SINGLE,
                options=("Đúng", "Không, chỉ số là mức trung bình có trọng số"),
                answer_index=1,
                explanation="Một vài mã vốn hóa lớn có thể kéo chỉ số lên trong khi nhiều mã khác giảm.",
            ),
        ),
        misconceptions=(
            (
                "Giá cổ phiếu thấp nghĩa là rẻ",
                "Giá tuyệt đối không nói lên đắt rẻ. Phải so với lợi nhuận và tài sản "
                "của doanh nghiệp.",
            ),
            (
                "Mua cổ phiếu là được doanh nghiệp trả lãi cố định",
                "Không. Cổ tức phụ thuộc kết quả kinh doanh và quyết định của đại hội "
                "cổ đông, có thể bằng không.",
            ),
            (
                "Chỉ số tăng thì danh mục nào cũng lãi",
                "Danh mục của bạn phụ thuộc các mã bạn nắm, không phụ thuộc chỉ số.",
            ),
        ),
        resources=(
            ("Quy định giao dịch chứng khoán cơ sở hợp nhất (cập nhật 2026)",
             "https://congbaocdn.chinhphu.vn/180507251028987904/2026/5/29/469538-1779683486_v1_1780016834_signed.pdf"),
            ("Danh sách thành viên lưu ký – VSDC", "https://vsd.vn/vi/ms"),
        ),
    ),
    Lesson(
        lesson_id="m3_gia_loi_suat",
        order=3,
        title="Giá, phần trăm thay đổi và lợi suất",
        objective=(
            "Tính được phần trăm thay đổi giá, phân biệt lợi suất đơn với lợi suất "
            "logarit và hiểu vì sao giảm 50% cần tăng 100% mới hòa vốn."
        ),
        explanation=(
            "Phần trăm thay đổi bằng giá mới trừ giá cũ, chia cho giá cũ, rồi nhân "
            "100. Đây là cách đọc biến động quen thuộc nhất.\n\n"
            "Lợi suất logarit là logarit tự nhiên của tỷ số giá mới trên giá cũ. "
            "Ứng dụng dùng dạng này cho phân tích vì nó cộng dồn được qua thời gian "
            "và đối xứng giữa tăng và giảm.\n\n"
            "Phần trăm không đối xứng. Giảm 50% rồi tăng 50% không đưa bạn về chỗ cũ, "
            "vì lần tăng tính trên một nền giá đã nhỏ hơn."
        ),
        example=(
            "Giá từ 20 xuống 10 là giảm 50%.\n\n"
            "Từ 10 muốn về lại 20 thì phải tăng 10/10 = 100%.\n\n"
            "Đây là lý do khoản lỗ lớn khó gỡ hơn nhiều so với cảm giác ban đầu."
        ),
        interactive=(
            "Nhập giá đầu kỳ và giá cuối kỳ để xem cả phần trăm thay đổi lẫn lợi "
            "suất logarit. Thử một cặp giảm mạnh rồi tự tính mức tăng cần thiết để "
            "hòa vốn."
        ),
        interactive_kind=INTERACTIVE_RETURN,
        questions=(
            Question(
                qid="m3_q1",
                prompt="Giá từ 25 lên 30. Phần trăm thay đổi là bao nhiêu (nhập số, ví dụ 20 cho 20%)?",
                kind=QUESTION_NUMBER,
                answer_value=20.0,
                tolerance=0.1,
                explanation="(30 − 25)/25 × 100 = 20%.",
            ),
            Question(
                qid="m3_q2",
                prompt="Một cổ phiếu giảm 50%. Cần tăng bao nhiêu phần trăm để về giá cũ?",
                kind=QUESTION_NUMBER,
                answer_value=100.0,
                tolerance=0.5,
                explanation="Từ nền giá còn một nửa, phải tăng gấp đôi tức 100%.",
            ),
            Question(
                qid="m3_q3",
                prompt="Vì sao phân tích định lượng hay dùng lợi suất logarit?",
                kind=QUESTION_SINGLE,
                options=(
                    "Vì số luôn lớn hơn",
                    "Vì cộng dồn được qua thời gian và đối xứng tăng/giảm",
                    "Vì không cần biết giá cũ",
                ),
                answer_index=1,
                explanation="Tính cộng dồn giúp ghép lợi suất nhiều kỳ bằng phép cộng.",
            ),
            Question(
                qid="m3_q4",
                prompt="Giá 100 giảm 10% rồi tăng 10%. Giá cuối cùng là bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=99.0,
                tolerance=0.01,
                explanation="100 × 0,9 × 1,1 = 99, không quay lại 100.",
            ),
        ),
        misconceptions=(
            (
                "Giảm 20% rồi tăng 20% là hòa vốn",
                "Không. Kết quả là 0,8 × 1,2 = 0,96, tức vẫn lỗ 4%.",
            ),
            (
                "Lợi suất logarit và phần trăm là một",
                "Chúng gần nhau khi biến động nhỏ, nhưng lệch rõ khi biến động lớn.",
            ),
            (
                "Lãi 100% rồi lỗ 100% thì huề",
                "Lỗ 100% là mất sạch, không có đường quay lại.",
            ),
        ),
        resources=(
            ("Khung hiểu biết tài chính PISA 2022 (OECD)",
             "https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html"),
        ),
    ),
    Lesson(
        lesson_id="m4_rui_ro_da_dang_hoa",
        order=6,
        title="Rủi ro, biến động và đa dạng hóa",
        objective=(
            "Đo được mức biến động bằng độ lệch chuẩn, phân biệt rủi ro hệ thống với "
            "rủi ro riêng lẻ và giải thích vì sao đa dạng hóa làm giảm loại thứ hai."
        ),
        explanation=(
            "Biến động đo mức dao động của lợi suất quanh giá trị trung bình, thường "
            "tính bằng độ lệch chuẩn. Biến động cao nghĩa là kết quả khó đoán hơn, "
            "cả theo hướng tốt lẫn hướng xấu.\n\n"
            "Rủi ro riêng lẻ đến từ bản thân một doanh nghiệp: nhà máy cháy, mất hợp "
            "đồng lớn, lãnh đạo sai phạm. Rủi ro hệ thống đến từ toàn thị trường: lãi "
            "suất, tỷ giá, suy thoái.\n\n"
            "Nắm nhiều mã ít liên quan nhau làm các cú sốc riêng lẻ triệt tiêu bớt "
            "lẫn nhau. Nhưng đa dạng hóa **không** xóa được rủi ro hệ thống, vì khi "
            "cả thị trường giảm thì phần lớn cổ phiếu giảm theo."
        ),
        example=(
            "Danh mục chỉ có một mã ngân hàng chịu trọn cú sốc của riêng ngân hàng đó.\n\n"
            "Thêm một mã bán lẻ và một mã công nghệ thì một tin xấu ngành ngân hàng "
            "chỉ ảnh hưởng một phần danh mục.\n\n"
            "Tuy vậy, nếu lãi suất toàn nền kinh tế tăng mạnh thì cả ba mã đều có thể "
            "giảm cùng lúc."
        ),
        interactive=(
            "Chọn hai đến bốn mã rồi xem độ lệch chuẩn của từng mã và của cả danh mục. "
            "So sánh xem danh mục nhiều mã có biến động thấp hơn mã đơn lẻ không."
        ),
        interactive_kind=INTERACTIVE_RISK,
        questions=(
            Question(
                qid="m4_q1",
                prompt="Đa dạng hóa làm giảm loại rủi ro nào?",
                kind=QUESTION_SINGLE,
                options=("Rủi ro hệ thống", "Rủi ro riêng lẻ của từng doanh nghiệp", "Cả hai như nhau"),
                answer_index=1,
                explanation="Cú sốc riêng của từng doanh nghiệp bù trừ lẫn nhau; rủi ro toàn thị trường thì không.",
            ),
            Question(
                qid="m4_q2",
                prompt="Biến động cao có luôn nghĩa là sẽ lỗ không?",
                kind=QUESTION_SINGLE,
                options=("Có", "Không, nó chỉ nói kết quả khó đoán hơn theo cả hai hướng"),
                answer_index=1,
                explanation="Biến động là thước đo độ bất định, không phải dự báo chiều giá.",
            ),
            Question(
                qid="m4_q3",
                prompt="Mua 10 mã cùng ngành ngân hàng thì đã đa dạng hóa tốt chưa?",
                kind=QUESTION_SINGLE,
                options=("Rồi, vì có 10 mã", "Chưa, vì chúng chịu chung cú sốc ngành"),
                answer_index=1,
                explanation="Đa dạng hóa cần các mã ít tương quan, không chỉ cần nhiều mã.",
            ),
        ),
        misconceptions=(
            (
                "Nhiều mã là an toàn",
                "Chỉ đúng khi các mã ít tương quan. Mười mã cùng ngành vẫn cùng lên "
                "cùng xuống.",
            ),
            (
                "Đa dạng hóa xóa hết rủi ro",
                "Không. Phần rủi ro toàn thị trường vẫn còn nguyên dù bạn nắm bao "
                "nhiêu mã.",
            ),
            (
                "Biến động thấp nghĩa là chắc lãi",
                "Biến động thấp chỉ nói dao động hẹp, không bảo đảm chiều đi lên.",
            ),
        ),
        resources=(
            ("Khung hiểu biết tài chính PISA 2022 (OECD)",
             "https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html"),
        ),
    ),
    Lesson(
        lesson_id="m5_bieu_do_nguon_tin",
        order=8,
        title="Biểu đồ, chất lượng nguồn tin, tương quan và nhân quả",
        objective=(
            "Đọc được biểu đồ giá mà không bị đánh lừa bởi cách chia trục, đánh giá "
            "được độ tin cậy của nguồn tin và phân biệt tương quan với nhân quả."
        ),
        explanation=(
            "Cùng một chuỗi giá có thể trông êm ả hay dữ dội tùy cách chia trục tung "
            "và độ dài khoảng thời gian. Luôn nhìn trục trước khi nhìn hình dạng.\n\n"
            "Nguồn tin cần được xét theo ba câu hỏi: ai công bố, họ được lợi gì từ "
            "việc bạn tin, và có thể kiểm chứng ở đâu. Một con số không kèm nguồn thì "
            "chưa dùng được để ra quyết định.\n\n"
            "Tương quan chỉ nói hai đại lượng biến động cùng nhịp. Nhân quả nói cái "
            "này gây ra cái kia. Hai chuỗi có thể tương quan chặt vì cùng chịu tác "
            "động của một yếu tố thứ ba, hoặc hoàn toàn do ngẫu nhiên."
        ),
        example=(
            "Một biểu đồ cắt trục tung từ 30 đến 32 làm biến động 1% trông như một "
            "vách núi.\n\n"
            "Cũng dữ liệu đó vẽ với trục từ 0 sẽ gần như phẳng.\n\n"
            "Tương tự, số lượng kem bán ra và số vụ đuối nước tương quan rất chặt, "
            "nhưng kem không gây đuối nước; cả hai cùng tăng vào mùa hè."
        ),
        interactive=(
            "Mở một biểu đồ giá trong ứng dụng, đổi khoảng thời gian từ một tháng "
            "sang một năm và quan sát cảm giác về mức biến động thay đổi ra sao "
            "dù dữ liệu không đổi."
        ),
        interactive_kind=INTERACTIVE_CHART,
        questions=(
            Question(
                qid="m5_q1",
                prompt="Hai chuỗi số có hệ số tương quan 0,9 thì kết luận được gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Chuỗi này gây ra chuỗi kia",
                    "Chúng biến động cùng nhịp, chưa nói được nguyên nhân",
                    "Chúng độc lập với nhau",
                ),
                answer_index=1,
                explanation="Tương quan mô tả mối liên hệ thống kê, không xác lập nguyên nhân.",
            ),
            Question(
                qid="m5_q2",
                prompt="Việc đầu tiên nên làm khi nhìn một biểu đồ giá là gì?",
                kind=QUESTION_SINGLE,
                options=("Nhìn hình dạng đường", "Đọc trục và khoảng thời gian", "Đếm số đỉnh"),
                answer_index=1,
                explanation="Trục quyết định hình dạng, nên phải đọc trục trước.",
            ),
            Question(
                qid="m5_q3",
                prompt="Một bài đăng hứa 'lãi 30% một tháng, cam kết không lỗ' nên được xử lý thế nào?",
                kind=QUESTION_SINGLE,
                options=(
                    "Làm theo nếu người đăng có nhiều người theo dõi",
                    "Xem là dấu hiệu cảnh báo, không có cam kết lợi nhuận nào là hợp lý",
                    "Thử với số tiền nhỏ",
                ),
                answer_index=1,
                explanation="Cam kết lợi nhuận là dấu hiệu điển hình của lừa đảo tài chính.",
            ),
            Question(
                qid="m5_q4",
                prompt="Số liệu không kèm nguồn thì dùng được để ra quyết định không?",
                kind=QUESTION_SINGLE,
                options=("Được, nếu nghe hợp lý", "Không, vì không kiểm chứng được"),
                answer_index=1,
                explanation="Không kiểm chứng được thì không thể biết sai ở đâu khi kết quả lệch.",
            ),
        ),
        misconceptions=(
            (
                "Tương quan chặt là bằng chứng nhân quả",
                "Không. Cần cơ chế giải thích và loại trừ yếu tố thứ ba.",
            ),
            (
                "Biểu đồ dốc đứng nghĩa là biến động lớn",
                "Độ dốc phụ thuộc cách chia trục; phải đọc thang đo mới biết.",
            ),
            (
                "Nguồn nhiều người theo dõi là nguồn đáng tin",
                "Số người theo dõi không thay thế được nguồn kiểm chứng được.",
            ),
        ),
        resources=(
            ("Khung hiểu biết tài chính PISA 2022 (OECD)",
             "https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html"),
            ("Danh sách thành viên lưu ký – VSDC", "https://vsd.vn/vi/ms"),
        ),
    ),
    Lesson(
        lesson_id="m6_mo_phong_nhat_ky",
        order=9,
        title="Giao dịch mô phỏng và nhật ký quyết định",
        objective=(
            "Thực hiện được một vòng giao dịch mô phỏng đầy đủ, ghi nhật ký quyết "
            "định có điểm vô hiệu và giới hạn lỗ, rồi tự đánh giá lại sau đó."
        ),
        explanation=(
            "Giao dịch mô phỏng là tập bằng tiền giả với giá thật. Mục đích không "
            "phải kiếm điểm số cao, mà để lộ ra thói quen ra quyết định của chính bạn.\n\n"
            "Một mục nhật ký tốt phải viết **trước** khi hành động và gồm bốn phần: "
            "bạn định làm gì, vì sao, điều gì chứng minh bạn sai, và bạn chấp nhận "
            "lỗ tối đa bao nhiêu.\n\n"
            "Viết trước là điểm mấu chốt. Viết sau khi biết kết quả thì trí nhớ sẽ tự "
            "chỉnh lại lý do cho khớp với kết quả, và bài học biến mất."
        ),
        example=(
            "Ghi ngày 07/08: dự định mua CTG quanh 31,5.\n\n"
            "Lý do: kết quả kinh doanh quý cải thiện. Điểm vô hiệu: giá đóng cửa dưới "
            "30,0. Giới hạn lỗ: 2% giá trị danh mục.\n\n"
            "Sau hai tuần, đọc lại và tự hỏi: lý do ban đầu còn đúng không, hay mình "
            "đang tìm cớ mới để giữ lệnh?"
        ),
        interactive=(
            "Mở thẻ Danh mục mô phỏng, thực hiện một lệnh mua và một lệnh bán, "
            "rồi ghi lại mục nhật ký tương ứng ở thẻ Nhật ký và tiến độ."
        ),
        interactive_kind=INTERACTIVE_PAPER,
        questions=(
            Question(
                qid="m6_q1",
                prompt="Nhật ký quyết định nên được viết khi nào?",
                kind=QUESTION_SINGLE,
                options=("Sau khi biết lãi hay lỗ", "Trước khi hành động", "Cuối tháng"),
                answer_index=1,
                explanation="Viết trước mới giữ được lý do gốc để đối chiếu.",
            ),
            Question(
                qid="m6_q2",
                prompt="'Điểm vô hiệu' trong một kế hoạch nghĩa là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Mức giá mà tại đó bạn thừa nhận giả thuyết đã sai",
                    "Mức giá bạn muốn chốt lời",
                    "Ngày hết hạn của tài khoản",
                ),
                answer_index=0,
                explanation="Điểm vô hiệu định trước giúp cắt lỗ theo kế hoạch thay vì theo cảm xúc.",
            ),
            Question(
                qid="m6_q3",
                prompt="Mục đích chính của giao dịch mô phỏng là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Kiếm điểm cao để khoe",
                    "Quan sát và sửa thói quen ra quyết định của bản thân",
                    "Dự đoán chính xác giá tương lai",
                ),
                answer_index=1,
                explanation="Mô phỏng là nơi để sai mà không mất tiền thật.",
            ),
            Question(
                qid="m6_q4",
                prompt="Một tháng mô phỏng có lãi đã đủ để chuyển sang vốn thật chưa?",
                kind=QUESTION_SINGLE,
                options=("Rồi", "Chưa, mẫu quá ngắn để phân biệt kỹ năng với may mắn"),
                answer_index=1,
                explanation="Cần nhiều tháng qua các trạng thái thị trường khác nhau mới có ý nghĩa.",
            ),
        ),
        misconceptions=(
            (
                "Mô phỏng lãi thì tiền thật cũng sẽ lãi",
                "Tiền thật kéo theo áp lực tâm lý khác hẳn, và lệnh thật còn chịu phí, "
                "thuế lẫn trượt giá.",
            ),
            (
                "Nhật ký là thủ tục cho có",
                "Nhật ký viết trước là cách duy nhất để biết mình đúng vì lý do đúng "
                "hay chỉ gặp may.",
            ),
            (
                "Lãi là thước đo duy nhất",
                "Kỷ luật rủi ro và chất lượng lập luận mới là thứ lặp lại được; một "
                "vài lệnh lãi có thể hoàn toàn do may.",
            ),
        ),
        resources=(
            ("Bộ luật Dân sự 2015 (năng lực hành vi dân sự theo độ tuổi)",
             "https://vbpl.vn/nganhangnhanuoc/Pages/vbpq-toanvan.aspx?ItemID=95942"),
            ("Khung hiểu biết tài chính PISA 2022 (OECD)",
             "https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html"),
        ),
    ),
    Lesson(
        lesson_id="s1_sai_so_phi",
        order=4,
        title="Số gần đúng và sai số (Toán 10) — dự báo giá có chính xác không?",
        objective=(
            "Tính được sai số tuyệt đối Δa và sai số tương đối δ của một số gần "
            "đúng; hiểu số quy tròn, độ chính xác d và vì sao sai số tối đa là d/2; "
            "dùng δ để so độ chính xác của hai dự báo giá."
        ),
        explanation=(
            "Trong đời thực ta gần như không bao giờ có con số 'đúng đúng': giá "
            "đóng cửa phải làm tròn đến bước giá, dự báo thì chỉ xấp xỉ. Số dùng "
            "thay số thật gọi là số gần đúng, kí hiệu ā; số thật là a.\n\n"
            "Sai số tuyệt đối: Δa = |a − ā|, cùng đơn vị với dữ liệu. Sai số tương "
            "đối: δ = Δa/|ā| × 100%, không phụ thuộc đơn vị nên cho biết mức độ "
            "chính xác. Số gần đúng của đại lượng lớn mà Δa nhỏ vẫn có thể chưa "
            "chính xác nếu δ lớn.\n\n"
            "Số quy tròn: làm tròn một số đến chữ số thập phân thứ p cho độ chính "
            "xác d = 10^(−p); sai số tuyệt đối của số quy tròn không vượt quá d/2. "
            "Vì thế khi công bố số gần đúng phải đồng thời nêu độ chính xác của nó."
        ),
        example=(
            "Nhóm bạn dự báo giá đóng cửa phiên mai của một mã là 25,0 nghìn đồng "
            "trong khi giá thực tế là 25,5 nghìn đồng.\n\n"
            "Δa = |25,5 − 25,0| = 0,5 nghìn đồng. "
            "δ = 0,5/25,0 × 100% = 2%. Dự báo lệch 2% so với giá thật.\n\n"
            "Một ví dụ khác về quy tròn: bảng điện tử hiển thị giá 27,4 nghìn đồng "
            "(làm tròn đến một chữ số thập phân). Độ chính xác d = 0,1 nên sai số "
            "tuyệt đối của số quy tròn tối đa là 0,05 nghìn đồng."
        ),
        interactive=(
            "Nhập giá dự báo và giá thực tế (đơn vị nghìn đồng) để xem Δa và δ. "
            "Thử hai dự báo có cùng Δa nhưng giá nền khác nhau, quan sát δ đổi "
            "hướng nào theo chiều giá nền."
        ),
        interactive_kind=INTERACTIVE_SAI_SO,
        questions=(
            Question(
                qid="s1_q1",
                prompt="Dự báo 25,0 nghìn đồng, giá thật 25,5 nghìn đồng. Sai số tuyệt đối Δa bằng bao nhiêu (nghìn đồng)?",
                kind=QUESTION_NUMBER,
                answer_value=0.5,
                tolerance=0.001,
                explanation="Δa = |25,5 − 25,0| = 0,5 nghìn đồng.",
            ),
            Question(
                qid="s1_q2",
                prompt="Với dự báo trên (ā = 25,0; Δa = 0,5), sai số tương đối δ bằng bao nhiêu phần trăm?",
                kind=QUESTION_NUMBER,
                answer_value=2.0,
                tolerance=0.01,
                explanation="δ = 0,5/25,0 × 100% = 2%.",
            ),
            Question(
                qid="s1_q3",
                prompt="Giá 27,35 được quy tròn thành 27,4 (một chữ số thập phân). Sai số tuyệt đối tối đa của số quy tròn là bao nhiêu?",
                kind=QUESTION_SINGLE,
                options=("0,05 nghìn đồng", "0,1 nghìn đồng", "0,35 nghìn đồng"),
                answer_index=0,
                explanation="Độ chính xác d = 0,1 nên sai số tuyệt đối tối đa là d/2 = 0,05.",
            ),
            Question(
                qid="s1_q4",
                prompt="Hai dự báo: A sai Δa = 0,4 trên giá 20 nghìn; B sai Δa = 0,4 trên giá 80 nghìn. Dự báo nào chính xác hơn?",
                kind=QUESTION_SINGLE,
                options=(
                    "A, vì giá nền nhỏ hơn",
                    "B, vì sai số tương đối của B nhỏ hơn (0,5% so với 2%)",
                    "Hai dự báo chính xác như nhau vì Δa bằng nhau",
                ),
                answer_index=1,
                explanation="Cùng Δa nhưng δ của B nhỏ hơn, tức độ chính xác cao hơn. So độ chính xác phải dùng sai số tương đối.",
            ),
        ),
        misconceptions=(
            (
                "Δa nhỏ thì chắc chắn chính xác hơn",
                "Phải so δ. Δa = 0,4 nghìn là nhỏ với giá 80 nghìn nhưng lớn với "
                "giá 2 nghìn; tương đối khác hẳn nhau.",
            ),
            (
                "Quy tròn tới bước d thì sai số tối đa là d",
                "Là d/2. Quy tròn đến 0,1 thì lệch tối đa 0,05 vì có thể làm tròn "
                "lên hoặc xuống cùng một lúc nửa bước.",
            ),
            (
                "Dự báo có sai số nghĩa là vô dụng",
                "Mọi mô hình đều có sai số; quan trọng là đo được δ so sánh giữa "
                "các phương pháp — đây cũng là cách nhà đầu tư đánh giá mô hình.",
            ),
        ),
        resources=(
            ("SGK Toán 10 (Kết nối tri thức) - Bài 12: Số gần đúng và sai số, trên SachMem",
             "https://sachmem.vn"),
            ("Thông tư 32/2018/TT-BGDĐT - Chương trình GDPT môn Toán",
             "https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721"),
        ),
    ),
    Lesson(
        lesson_id="s2_so_dac_trung",
        order=5,
        title="Số đặc trưng đo trung tâm và độ phân tán (Toán 10) — hai cổ phiếu cùng trung bình, khác nhau ra sao?",
        objective=(
            "Tính được số trung bình, trung vị, tứ phân vị, mốt; khoảng biến "
            "thiên, khoảng tứ phân vị, phương sai, độ lệch chuẩn của mẫu không "
            "ghép nhóm; phát hiện giá trị bất thường theo quy tắc 1,5·IQR."
        ),
        explanation=(
            "Số đặc trưng đo xu thế trung tâm: số trung bình (bar x) nhạy với giá "
            "trị bất thường; trung vị (Me) là giá trị chính giữa; mốt (Mo) là giá "
            "trị xuất hiện nhiều nhất. Tứ phân vị Q1, Q3 chia mẫu đã sắp xếp thành "
            "bốn phần bằng nhau.\n\n"
            "Số đặc trưng đo độ phân tán: khoảng biến thiên R = x_max − x_min; "
            "khoảng tứ phân vị Δ_Q = Q3 − Q1 (bỏ qua 25% nhỏ nhất và 25% lớn "
            "nhất); phương sai s² = (1/n)×tổng (x_i − bar x)²; độ lệch chuẩn "
            "s = √s², cùng đơn vị với dữ liệu.\n\n"
            "Giá trị bất thường theo quy tắc SGK: nằm ngoài khoảng [Q1 − 1,5·Δ_Q; "
            "Q3 + 1,5·Δ_Q]. Trong thị trường, đó thường là phiên có tin lớn — đáng "
            "dò nguyên nhân, chưa chắc là dữ liệu lỗi."
        ),
        example=(
            "SGK có ví dụ quen thuộc: An với điểm 9,2; 8,7; 9,5; 6,8; 8,0; 8,0; "
            "7,3; 6,5 và Bình với 8,2; 8,1; 8,0; 7,8; 8,3; 7,9; 7,6; 8,1. Cả hai "
            "đều có số trung bình 8,0, nhưng:\n\n"
            "s² của An = 1,045 (s ≈ 1,02); s² của Bình = 0,045 (s ≈ 0,21). Bình "
            "học đều hơn vì điểm của Bình tập trung sát trung bình.\n\n"
            "Ví dụ với lợi suất ngày (%): dãy (−2; 1; 0,5; 3; −1). Số trung bình "
            "= 1,5/5 = 0,3. Phương sai s² = 14,8/5 = 2,96, độ lệch chuẩn "
            "s = √2,96 ≈ 1,72 (%)."
        ),
        interactive=(
            "Nhập một dãy lợi suất (hoặc dán lợi suất thật từ tab Khám phá dữ "
            "liệu) để tính trung tâm và phân tán. So sánh hai dãy có cùng số "
            "trung bình nhưng phân tán khác nhau."
        ),
        interactive_kind=INTERACTIVE_DAC_TRUNG,
        questions=(
            Question(
                qid="s2_q1",
                prompt="Lợi suất ngày (%) của một mã trong 5 phiên: (−2; 1; 0,5; 3; −1). Số trung bình bằng bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=0.3,
                tolerance=0.001,
                explanation="bar x = (−2 + 1 + 0,5 + 3 − 1)/5 = 1,5/5 = 0,3 (%).",
            ),
            Question(
                qid="s2_q2",
                prompt="Với dãy trên, phương sai s² (chia cho n = 5) bằng bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=2.96,
                tolerance=0.005,
                explanation="Tổng (x_i − 0,3)² = 14,8 nên s² = 14,8/5 = 2,96.",
            ),
            Question(
                qid="s2_q3",
                prompt="Độ lệch chuẩn s của dãy trên (làm tròn hai chữ số thập phân) là bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=1.72,
                tolerance=0.01,
                explanation="s = √2,96 ≈ 1,72 (%).",
            ),
            Question(
                qid="s2_q4",
                prompt="An và Bình cùng có số trung bình 8,0 nhưng s của An ≈ 1,02 còn s của Bình ≈ 0,21. Kết luận đúng là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "An học đều hơn vì s lớn hơn",
                    "Bình học đều hơn vì s nhỏ hơn, điểm sát trung bình hơn",
                    "Không thể kết luận gì khi số trung bình bằng nhau",
                ),
                answer_index=1,
                explanation="Cùng trung tâm thì phân tán quyết định 'đều hay không đều': s nhỏ nghĩa là dữ liệu tập trung sát trung bình.",
            ),
        ),
        misconceptions=(
            (
                "Số trung bình cho biết tất cả",
                "Hai mẫu cùng trung bình có thể phân tán khác nhau rất xa — như An "
                "và Bình, hay hai cổ phiếu cùng lợi suất trung bình nhưng một mã "
                "mượt, một mã nhảy loạn.",
            ),
            (
                "Phương sai cùng đơn vị với dữ liệu",
                "s² là bình phương đơn vị (%² chẳng hạn); độ lệch chuẩn s mới cùng "
                "đơn vị với dữ liệu nên được dùng để diễn giải.",
            ),
            (
                "Khoảng biến thiên và khoảng tứ phân vị luôn như nhau",
                "R dùng giá trị lớn nhất - nhỏ nhất nên phụ thuộc hai điểm đầu mút; "
                "Δ_Q bỏ 25% mỗi phía nên bền hơn trước giá trị bất thường.",
            ),
        ),
        resources=(
            ("SGK Toán 10 (Kết nối tri thức) - Bài 13, 14: Số đặc trưng đo xu thế trung tâm và độ phân tán, trên SachMem",
             "https://sachmem.vn"),
            ("Thông tư 32/2018/TT-BGDĐT - Chương trình GDPT môn Toán",
             "https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721"),
        ),
    ),
    Lesson(
        lesson_id="s3_mau_ghep_nhom",
        order=7,
        title="Mẫu số liệu ghép nhóm và số đặc trưng trung tâm (Toán 11) — khi dữ liệu chỉ ghi theo khoảng",
        objective=(
            "Ghép được mẫu lớn thành các nhóm [u_i; u_(i+1)), tính được tần số, "
            "giá trị đại diện (trung điểm) của nhóm; ước lượng số trung bình, "
            "trung vị, mốt của mẫu ghép nhóm."
        ),
        explanation=(
            "Khi mẫu lớn hoặc dữ liệu chỉ được ghi dưới dạng khoảng (ví dụ 'giá "
            "biên động từ 24 đến 28 nghìn'), ta ghép mẫu thành các nhóm liền nhau "
            "[u_i; u_(i+1)) và đếm tần số n_i của mỗi nhóm. Tổng các tần số bằng "
            "cỡ mẫu N.\n\n"
            "Mỗi nhóm được đại diện bởi một giá trị — thường lấy trung điểm "
            "c_i = (u_i + u_(i+1))/2 (một số bộ SGK gọi là tổ trọng tâm). Số trung "
            "bình ghép nhóm: bar x_g = (n_1·c_1 + ... + n_k·c_k)/N.\n\n"
            "Trung vị, tứ phân vị và mốt ghép nhóm được ước lượng từ bảng tần số "
            "(nội suy theo nhóm chứa vị trí N/2, N/4, 3N/4; mốt g thuộc nhóm có "
            "tần số lớn nhất). Số ghép nhóm chỉ là ước lượng vì ta đã mất chi tiết "
            "trong từng nhóm."
        ),
        example=(
            "Bảng lợi suất ngày (%) của 20 phiên được ghép thành hai nhóm: "
            "[−2; 0) có n = 6, c = −1; [0; 2) có n = 14, c = 1.\n\n"
            "bar x_g = (6 × (−1) + 14 × 1)/20 = 8/20 = 0,4 (%).\n\n"
            "Một bảng khác về giá đóng cửa 20 phiên: nhóm (24; 28) n = 5, c = 26; "
            "nhóm (28; 32) n = 15, c = 30. bar x_g = (5 × 26 + 15 × 30)/20 = "
            "580/20 = 29 (nghìn đồng)."
        ),
        interactive=(
            "Kéo số nhóm k và xem bảng tần số, giá trị đại diện thay đổi thế nào; "
            "bảng so sánh cho biết ước lượng ghép nhóm lệch bao nhiêu so với "
            "tính trực tiếp."
        ),
        interactive_kind=INTERACTIVE_GHEP_NHOM,
        questions=(
            Question(
                qid="s3_q1",
                prompt="Bảng ghép nhóm: [−2; 0) n = 6, c = −1; [0; 2) n = 14, c = 1. Số trung bình ghép nhóm bar x_g bằng bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=0.4,
                tolerance=0.001,
                explanation="bar x_g = (6 × (−1) + 14 × 1)/20 = 8/20 = 0,4.",
            ),
            Question(
                qid="s3_q2",
                prompt="Giá đóng cửa 20 phiên: (24; 28) n = 5, c = 26; (28; 32) n = 15, c = 30. bar x_g bằng bao nhiêu (nghìn đồng)?",
                kind=QUESTION_NUMBER,
                answer_value=29.0,
                tolerance=0.01,
                explanation="bar x_g = (5 × 26 + 15 × 30)/20 = 580/20 = 29.",
            ),
            Question(
                qid="s3_q3",
                prompt="Giá trị đại diện của nhóm [1,5; 2,5) lấy theo trung điểm là bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=2.0,
                tolerance=0.001,
                explanation="c = (1,5 + 2,5)/2 = 2.",
            ),
            Question(
                qid="s3_q4",
                prompt="Mốt của mẫu ghép nhóm là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Số trùng nhau trong dữ liệu thô",
                    "Giá trị đại diện của nhóm có tần số lớn nhất",
                    "Trung bình các trung điểm của mọi nhóm",
                ),
                answer_index=1,
                explanation="Với mẫu ghép nhóm, mốt thuộc nhóm có tần số lớn nhất và được ước lượng từ nhóm đó.",
            ),
        ),
        misconceptions=(
            (
                "Ghép nhóm không mất thông tin",
                "Trong mỗi nhóm, các giá trị riêng lẻ bị gộp lại thành một con số "
                "tần số — đó là nguồn gốc của sai số ước lượng (nối với bài sai số).",
            ),
            (
                "bar x_g là trung bình của các tần số",
                "Là trung bình của các giá trị đại diện có trọng số là tần số, "
                "không phải trung bình của n_i.",
            ),
            (
                "Giá trị đại diện bắt buộc là trung điểm",
                "SGK thường lấy trung điểm cho dễ; về nguyên tắc chỉ cần chọn một "
                "giá trị hợp lý trong nhóm, trung điểm là lựa chọn tự nhiên nhất.",
            ),
        ),
        resources=(
            ("SGK Toán 11 (Kết nối tri thức) - Bài 8, 9: Mẫu số liệu ghép nhóm và các số đặc trưng trung tâm, trên SachMem",
             "https://sachmem.vn"),
            ("Thông tư 32/2018/TT-BGDĐT - Chương trình GDPT môn Toán",
             "https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721"),
        ),
    ),
    Lesson(
        lesson_id="s4_phan_tan_ghep_nhom",
        order=10,
        title="Độ phân tán của mẫu số liệu ghép nhóm (Toán 12) — so sánh tính biến động theo từng giai đoạn",
        objective=(
            "Tính được khoảng biến thiên, khoảng tứ phân vị, phương sai và độ lệch "
            "chuẩn ước lượng của mẫu ghép nhóm; so sánh mức phân tán của hai mẫu "
            "cùng đơn vị."
        ),
        explanation=(
            "Với mẫu ghép nhóm, độ phân tán được ước lượng từ bảng tần số:\n\n"
            "- Khoảng biến thiên: R_g xấp xỉ u_max − u_min, hiệu giữa biên lớn "
            "nhất của nhóm cuối và biên nhỏ nhất của nhóm đầu.\n"
            "- Khoảng tứ phân vị: Δ_(Q,g) = Q3g − Q1g với Q1g, Q3g nội suy theo "
            "công thức nhóm chứa vị trí N/4 và 3N/4.\n"
            "- Phương sai: s²_g = (1/N) × tổng n_i (c_i − bar x_g)²; độ lệch chuẩn "
            "s_g = √s²_g.\n\n"
            "So sánh hai mẫu ghép nhóm (cùng đơn vị): mẫu có R_g hay s_g lớn hơn "
            "phân tán mạnh hơn. Đây chính là cách SGK hỏi 'giai đoạn nào biến động "
            "nhiều hơn' — và cũng là cách nhà đầu tư so hai thời kỳ của một mã."
        ),
        example=(
            "So sánh hai tuần của một mã, lợi suất ngày (%):\n\n"
            "Tuần 1: [−1; 1) n = 8; [1; 3) n = 12. R_g = 3 − (−1) = 4.\n"
            "Tuần 2: [−3; −1) n = 4; [−1; 1) n = 8; [1; 3) n = 8. "
            "R_g = 3 − (−3) = 6.\n\n"
            "Tuần 2 có R_g lớn hơn nên biến động mạnh hơn — dù số phiên hai tuần "
            "như nhau. Với s_g cũng vậy: mẫu nào s_g lớn hơn, mức dao động quanh "
            "trung tâm lớn hơn."
        ),
        interactive=(
            "Nhập hai dãy lợi suất của hai giai đoạn (cách nhau bằng dấu chấm "
            "phẩy hai dãy) để xem s_g của từng giai đoạn và nhận xét giai đoạn "
            "nào biến động mạnh hơn."
        ),
        interactive_kind=INTERACTIVE_PHAN_TAN,
        questions=(
            Question(
                qid="s4_q1",
                prompt="Mẫu ghép nhóm có nhóm đầu là [−2; 0) và nhóm cuối là [1; 3]. Khoảng biến thiên ước lượng R_g bằng bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=5.0,
                tolerance=0.001,
                explanation="R_g = 3 − (−2) = 5 (biên trên nhóm cuối trừ biên dưới nhóm đầu).",
            ),
            Question(
                qid="s4_q2",
                prompt="Mẫu ghép nhóm N = 20: n = 6 với c = −1; n = 14 với c = 1; bar x_g = 0,4. Phương sai s²_g bằng bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=0.84,
                tolerance=0.005,
                explanation="s²_g = (6 × (−1,4)² + 14 × (0,6)²)/20 = (11,76 + 5,04)/20 = 16,8/20 = 0,84.",
            ),
            Question(
                qid="s4_q3",
                prompt="Độ lệch chuẩn s_g của mẫu trên (làm tròn hai chữ số thập phân) là bao nhiêu?",
                kind=QUESTION_NUMBER,
                answer_value=0.92,
                tolerance=0.01,
                explanation="s_g = √0,84 ≈ 0,92.",
            ),
            Question(
                qid="s4_q4",
                prompt="Hai mẫu cùng số trung bình nhưng s_g của mẫu A nhỏ hơn mẫu B. Phát biểu đúng là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Mẫu A phân tán mạnh hơn mẫu B",
                    "Dữ liệu của mẫu A tập trung quanh trung tâm chặt hơn mẫu B",
                    "Hai mẫu phân tán như nhau vì cùng trung bình",
                ),
                answer_index=1,
                explanation="s_g nhỏ nghĩa là các giá trị đại diện nằm gần bar x_g hơn: ít dao động, 'đều' hơn.",
            ),
        ),
        misconceptions=(
            (
                "R_g tính từ trung điểm của nhóm đầu và cuối",
                "R_g dùng biên ngoài cùng: biên trên của nhóm cuối trừ biên dưới "
                "của nhóm đầu, không phải hai trung điểm.",
            ),
            (
                "s_g càng lớn càng tốt",
                "Phân tán lớn nghĩa là biến động mạnh — với điểm số là 'học không "
                "đều', với lợi suất là rủi ro lớn hơn. Lớn không mang nghĩa tốt/xấu "
                "tuyệt đối, mà là mức dao động.",
            ),
            (
                "So sánh phân tán của hai mẫu khác đơn vị",
                "Chỉ so sánh trực tiếp khi hai mẫu cùng đơn vị (cùng %, cùng nghìn "
                "đồng); khác đơn vị thì con số s_g không thể đem ra so.",
            ),
        ),
        resources=(
            ("SGK Toán 12 (Kết nối tri thức) - Bài 9, 10: Khoảng biến thiên, khoảng tứ phân vị và phương sai, độ lệch chuẩn của mẫu ghép nhóm, trên SachMem",
             "https://sachmem.vn"),
            ("Thông tư 32/2018/TT-BGDĐT - Chương trình GDPT môn Toán",
             "https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Truy vấn
# ---------------------------------------------------------------------------

def all_lessons() -> tuple[Lesson, ...]:
    return tuple(sorted(LESSONS, key=lambda l: l.order))


def get_lesson(lesson_id: str) -> Lesson | None:
    wanted = str(lesson_id or "").strip()
    for lesson in LESSONS:
        if lesson.lesson_id == wanted:
            return lesson
    return None


def total_questions() -> int:
    return sum(len(lesson.questions) for lesson in LESSONS)


UNLOCK_THRESHOLD = 70.0
UNLOCK_REQUIRED_LESSONS = 4


def should_unlock_advanced(lesson_scores: dict[str, Any] | None) -> bool:
    """Đủ điều kiện mở công cụ nâng cao cho chế độ THPT.

    Cần đạt từ 70 điểm trở lên ở ít nhất bốn trong mười bài học (bất kỳ bài
    nào, kể cả bài thống kê). Ngưỡng này để
    người học chạm tới công cụ định lượng sau khi đã có nền, chứ không phải sau
    khi bấm qua loa.
    """

    scores = lesson_scores or {}
    valid_ids = {lesson.lesson_id for lesson in LESSONS}
    passed = 0
    for lesson_id, score in scores.items():
        if lesson_id not in valid_ids:
            continue
        try:
            if float(score) >= UNLOCK_THRESHOLD:
                passed += 1
        except (TypeError, ValueError):
            continue
    return passed >= UNLOCK_REQUIRED_LESSONS
