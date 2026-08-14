"""Sáu mô-đun nền tảng cho học sinh trung học phổ thông.

Toàn bộ nội dung và phần chấm điểm nằm cục bộ. Học sinh hoàn thành được bài mà
không cần khóa API hay kết nối tới mô hình ngôn ngữ lớn nào.

Mỗi bài có bảy phần theo yêu cầu chương trình: mục tiêu, giải thích, ví dụ,
phần tương tác, 3–5 câu hỏi, lỗi hiểu sai thường gặp và nguồn học liệu.

Phần tương tác dùng lại đúng bộ máy tính toán của ứng dụng (``kind`` trỏ tới
một widget đã có), thay vì dựng công cụ riêng cho bản THPT.
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


# ---------------------------------------------------------------------------
# Nội dung sáu mô-đun
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
                prompt="Gửi 20 triệu đồng, lãi kép 5% một năm, sau 3 năm được bao nhiêu (làm tròn triệu đồng)?",
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
        order=4,
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
        order=5,
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
        order=6,
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

    Cần đạt từ 70 điểm trở lên ở ít nhất bốn trong sáu mô-đun. Ngưỡng này để
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
