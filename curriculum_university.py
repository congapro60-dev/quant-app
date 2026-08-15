"""Bài học cho bậc đại học, bám giáo trình môn học tại chỗ.

Nguồn: tập bài giảng thực tập môn Kinh tế lượng tài chính có sẵn trong thư mục
dự án (chương Lợi suất – Danh mục, chương Mô hình chỉ số đơn, chương Phân tích
trung bình – phương sai).

Ký hiệu bám đúng giáo trình, kể cả khi tài liệu khác dùng chữ cái khác. Sinh
viên đối chiếu bài làm với giáo trình nên đổi ký hiệu là gây rối, dù toán học
tương đương.

Không sao chép nguyên văn tài liệu lưu hành nội bộ. Nội dung ở đây là diễn giải
lại bằng lời của ứng dụng, kèm công thức và ví dụ tự dựng.
"""

from __future__ import annotations

from curriculum import (
    QUESTION_NUMBER,
    QUESTION_SINGLE,
    Lesson,
    Question,
)

# Nhãn phần tương tác, trỏ tới công cụ sẵn có.
INT_RETURN = "may_tinh_loi_suat"
INT_COV = "ma_tran_hiep_phuong_sai"
INT_SIM = "hoi_quy_sim"
INT_DIAG = "chan_doan_mo_hinh"
INT_MARKOWITZ = "bien_hieu_qua"
INT_EVIEWS = "eviews"

# Nguồn là tài liệu môn học bản in/tệp cục bộ, không có đường dẫn công khai.
# Để chuỗi rỗng ở vị trí URL; tầng hiển thị in ra dạng chữ thường thay vì liên
# kết. Không bịa đường dẫn cho tài liệu lưu hành nội bộ.
LOCAL_SOURCE = ""

_SRC_LECTURE = (
    "Bài giảng thực tập Kinh tế lượng tài chính — tài liệu môn học (tệp cục bộ)",
    LOCAL_SOURCE,
)
_SRC_APP = ("Thẻ Ôn thi trong ứng dụng — dùng để đối chiếu đáp án", LOCAL_SOURCE)


UNIVERSITY_LESSONS: tuple[Lesson, ...] = (
    Lesson(
        lesson_id="dh1_loi_suat",
        order=1,
        title="Lợi suất tài sản và lợi suất danh mục",
        objective=(
            "Tính được lợi suất một kỳ và nhiều kỳ, biết khi nào dùng được xấp xỉ "
            "logarit, và tính được lợi suất danh mục theo tỷ trọng."
        ),
        explanation=(
            "Lợi suất một kỳ của tài sản là phần thay đổi giá chia cho giá đầu kỳ: "
            "r_t = (S_t − S_{t−1}) / S_{t−1}. Lợi suất k kỳ thay S_{t−1} bằng S_{t−k}.\n\n"
            "Khi chu kỳ ngắn — theo phiên, ngày hoặc tuần — lợi suất nhỏ nên thường "
            "dùng xấp xỉ logarit r_t = ln(S_t / S_{t−1}). Ưu điểm của dạng này là "
            "cộng dồn được qua thời gian, nên lợi suất k kỳ chính là tổng các lợi "
            "suất từng kỳ.\n\n"
            "Với danh mục, gọi w_i là tỷ trọng giá trị tài sản i trên tổng vốn ban "
            "đầu. Khi đó lợi suất danh mục là trung bình có trọng số: r_P = Σ w_i·r_i, "
            "và lợi suất kỳ vọng cũng vậy: r̄_P = Σ w_i·r̄_i.\n\n"
            "Hai lưu ý của giáo trình: so sánh lợi suất các tài sản thì chu kỳ tính "
            "phải giống nhau, và khi tính lợi suất cổ phiếu thường loại các ngày trả "
            "cổ tức để không lẫn phần chia tiền vào biến động giá."
        ),
        example=(
            "Giá một cổ phiếu đi từ 20,0 lên 21,0 nghìn đồng trong một phiên.\n\n"
            "Lợi suất đơn: (21 − 20)/20 = 5,00%. Lợi suất logarit: ln(21/20) ≈ 4,88%. "
            "Chênh lệch nhỏ vì mức thay đổi nhỏ.\n\n"
            "Danh mục W = (0,3; 0,2; 0,5) với lợi suất kỳ vọng ba tài sản lần lượt "
            "1%, 2% và 3% cho r̄_P = 0,3(1%) + 0,2(2%) + 0,5(3%) = 2,2%."
        ),
        interactive=(
            "Nạp vài mã ở thanh bên rồi mở thẻ Ôn thi để xem chuỗi lợi suất logarit "
            "ứng dụng tính ra. Đối chiếu vài dòng đầu với phép tính tay của bạn."
        ),
        interactive_kind=INT_RETURN,
        questions=(
            Question(
                qid="dh1_q1",
                prompt="Giá đi từ 40 lên 42. Lợi suất đơn một kỳ là bao nhiêu phần trăm?",
                kind=QUESTION_NUMBER, answer_value=5.0, tolerance=0.05,
                explanation="(42 − 40)/40 = 0,05 = 5%.",
            ),
            Question(
                qid="dh1_q2",
                prompt="Vì sao lợi suất logarit thuận tiện khi ghép nhiều kỳ?",
                kind=QUESTION_SINGLE,
                options=(
                    "Vì giá trị luôn lớn hơn lợi suất đơn",
                    "Vì lợi suất nhiều kỳ bằng tổng các lợi suất từng kỳ",
                    "Vì không cần biết giá đầu kỳ",
                ),
                answer_index=1,
                explanation="ln(S_t/S_{t−k}) tách được thành tổng các ln liên tiếp.",
            ),
            Question(
                qid="dh1_q3",
                prompt="Danh mục W = (0,4; 0,6) với r̄ = (10%; 20%). Lợi suất kỳ vọng danh mục là bao nhiêu phần trăm?",
                kind=QUESTION_NUMBER, answer_value=16.0, tolerance=0.05,
                explanation="0,4(10%) + 0,6(20%) = 16%.",
            ),
            Question(
                qid="dh1_q4",
                prompt="Khi so sánh lợi suất hai cổ phiếu, điều kiện bắt buộc là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Hai cổ phiếu phải cùng ngành",
                    "Chu kỳ tính lợi suất phải giống nhau",
                    "Hai cổ phiếu phải cùng mức giá",
                ),
                answer_index=1,
                explanation="Lợi suất theo ngày và theo tuần không so trực tiếp được.",
            ),
        ),
        misconceptions=(
            ("Lợi suất logarit và lợi suất đơn là một",
             "Chúng gần nhau khi biến động nhỏ, nhưng lệch rõ khi biến động lớn."),
            ("Tỷ trọng là số lượng cổ phiếu",
             "Tỷ trọng w_i là phần giá trị tiền, bằng k_i·S_i chia tổng vốn, và tổng các w_i bằng 1."),
            ("Cổ tức không ảnh hưởng gì tới chuỗi lợi suất",
             "Ngày chia cổ tức làm giá giảm kỹ thuật; giáo trình khuyên loại các ngày này ra."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
    Lesson(
        lesson_id="dh2_do_dao_dong",
        order=2,
        title="Độ dao động danh mục và ma trận hiệp phương sai",
        objective=(
            "Viết được phương sai danh mục dưới dạng ma trận và giải thích vì sao "
            "hiệp phương sai giữa các tài sản quyết định mức giảm rủi ro."
        ),
        explanation=(
            "Độ dao động của danh mục là độ lệch chuẩn của lợi suất danh mục, ký "
            "hiệu σ_P. Nó phản ánh mức biến động giá trị danh mục nên được dùng làm "
            "thước đo rủi ro khi nắm giữ.\n\n"
            "Từ r_P = Σ w_i·r_i suy ra phương sai là tổng kép σ² = ΣΣ w_i·w_j·σ_ij, "
            "trong đó σ_ij = cov(r_i, r_j). Viết gọn bằng ma trận hiệp phương sai V "
            "và vector tỷ trọng W: σ_P² = W′VW, do đó σ_P = √(W′VW).\n\n"
            "Điểm cốt lõi nằm ở các số hạng chéo. Nếu hai tài sản có hiệp phương sai "
            "thấp hoặc âm, phần đóng góp chéo nhỏ đi và độ dao động danh mục thấp hơn "
            "trung bình độ dao động từng tài sản. Đó chính là cơ chế toán học của đa "
            "dạng hóa.\n\n"
            "V là ma trận đối xứng, bán xác định dương, nên W′VW luôn không âm — đúng "
            "với thực tế rằng phương sai không thể âm."
        ),
        example=(
            "Hai tài sản cùng độ lệch chuẩn 20%, tỷ trọng bằng nhau 0,5.\n\n"
            "Nếu tương quan bằng 1: σ_P = 20%, đa dạng hóa vô ích.\n\n"
            "Nếu tương quan bằng 0: σ_P = √(0,25·0,04 + 0,25·0,04) ≈ 14,1%. "
            "Cùng hai tài sản, chỉ khác mức tương quan, rủi ro đã giảm gần một phần ba."
        ),
        interactive=(
            "Mở thẻ Ôn thi, tính ma trận hiệp phương sai V cho nhóm mã đã nạp. "
            "So các số hạng chéo giữa hai mã cùng ngành và hai mã khác ngành."
        ),
        interactive_kind=INT_COV,
        questions=(
            Question(
                qid="dh2_q1",
                prompt="Phương sai danh mục viết dưới dạng ma trận là gì?",
                kind=QUESTION_SINGLE,
                options=("W′VW", "V′WW", "W + V"),
                answer_index=0,
                explanation="σ_P² = W′VW với V là ma trận hiệp phương sai.",
            ),
            Question(
                qid="dh2_q2",
                prompt="Yếu tố nào quyết định đa dạng hóa có hiệu quả hay không?",
                kind=QUESTION_SINGLE,
                options=(
                    "Số lượng tài sản, càng nhiều càng tốt",
                    "Hiệp phương sai giữa các tài sản",
                    "Giá tuyệt đối của các tài sản",
                ),
                answer_index=1,
                explanation="Mười mã tương quan chặt vẫn cùng lên cùng xuống.",
            ),
            Question(
                qid="dh2_q3",
                prompt="Hai tài sản cùng độ lệch chuẩn 20%, tỷ trọng 0,5–0,5, tương quan bằng 0. Độ dao động danh mục xấp xỉ bao nhiêu phần trăm?",
                kind=QUESTION_NUMBER, answer_value=14.14, tolerance=0.2,
                explanation="√(2 × 0,25 × 0,04) ≈ 0,1414 = 14,14%.",
            ),
        ),
        misconceptions=(
            ("Rủi ro danh mục là trung bình rủi ro các tài sản",
             "Chỉ đúng khi các tài sản tương quan hoàn hảo; bình thường thì thấp hơn."),
            ("Ma trận hiệp phương sai chỉ cần đường chéo",
             "Các số hạng ngoài đường chéo mới là chỗ đa dạng hóa phát huy tác dụng."),
            ("Phương sai danh mục có thể âm nếu tương quan âm",
             "V bán xác định dương nên W′VW luôn không âm."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
    Lesson(
        lesson_id="dh3_sim_gia_thiet",
        order=3,
        title="Mô hình chỉ số đơn: dạng mô hình và ba giả thiết",
        objective=(
            "Viết đúng dạng mô hình chỉ số đơn, nêu ba giả thiết và giải thích ý "
            "nghĩa kinh tế của từng tham số."
        ),
        explanation=(
            "Mô hình chỉ số đơn mô tả quan hệ tuyến tính giữa lợi suất một tài sản và "
            "lợi suất chỉ số thị trường: r_i = γ_i + β_i·r_I + ε_i.\n\n"
            "Ba giả thiết của mô hình: kỳ vọng nhiễu bằng không E(ε_i) = 0; nhiễu "
            "không tương quan với lợi suất thị trường cov(ε_i, r_I) = 0; và nhiễu của "
            "các tài sản khác nhau không tương quan với nhau cov(ε_i, ε_k) = 0 khi i ≠ k.\n\n"
            "Về ý nghĩa: γ_i là phần lợi suất cố định riêng có của tài sản. β_i đo mức "
            "nhạy cảm của tài sản với biến động thị trường — β_i > 1 gọi là tài sản "
            "năng động vì phản ứng mạnh hơn thị trường, β_i < 1 là tài sản thụ động. "
            "ε_i là phần biến động ngẫu nhiên riêng có.\n\n"
            "Giả thiết thứ hai và thứ ba mới là chỗ đáng chú ý: chúng nói rằng cú sốc "
            "riêng của một doanh nghiệp không liên quan tới thị trường chung, và cũng "
            "không liên quan tới cú sốc riêng của doanh nghiệp khác. Thực tế các doanh "
            "nghiệp cùng ngành thường vi phạm giả thiết thứ ba."
        ),
        example=(
            "Ước lượng cho một cổ phiếu ngân hàng ra kết quả r_i = 0,0005 + 1,07·r_I.\n\n"
            "β = 1,07 lớn hơn 1 nên đây là tài sản năng động: khi chỉ số tăng 1%, lợi "
            "suất cổ phiếu này tăng khoảng 1,07% về mặt trung bình.\n\n"
            "γ = 0,0005 là phần lợi suất cố định riêng, rất nhỏ theo phiên."
        ),
        interactive=(
            "Chạy Phân tích rồi mở Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn. "
            "Đọc β của từng mã và phân loại năng động hay thụ động."
        ),
        interactive_kind=INT_SIM,
        questions=(
            Question(
                qid="dh3_q1",
                prompt="Tài sản có β = 1,4 được gọi là gì?",
                kind=QUESTION_SINGLE,
                options=("Tài sản thụ động", "Tài sản năng động", "Tài sản phi rủi ro"),
                answer_index=1,
                explanation="β > 1 nên tài sản phản ứng mạnh hơn thị trường.",
            ),
            Question(
                qid="dh3_q2",
                prompt="Giả thiết cov(ε_i, ε_k) = 0 với i ≠ k có nghĩa gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Biến động riêng của các tài sản không liên quan với nhau",
                    "Các tài sản có cùng mức rủi ro",
                    "Nhiễu luôn bằng không",
                ),
                answer_index=0,
                explanation="Đây là giả thiết hay bị vi phạm với các mã cùng ngành.",
            ),
            Question(
                qid="dh3_q3",
                prompt="Trong mô hình chỉ số đơn, tham số nào đo độ nhạy với thị trường?",
                kind=QUESTION_SINGLE,
                options=("γ_i", "β_i", "ε_i"),
                answer_index=1,
                explanation="β_i là hệ số của r_I nên đo độ nhạy.",
            ),
            Question(
                qid="dh3_q4",
                prompt="Chỉ số tăng 1%, cổ phiếu có β = 0,6 thì lợi suất kỳ vọng tăng khoảng bao nhiêu phần trăm?",
                kind=QUESTION_NUMBER, answer_value=0.6, tolerance=0.02,
                explanation="0,6 × 1% = 0,6%, thấp hơn thị trường vì là tài sản thụ động.",
            ),
        ),
        misconceptions=(
            ("β lớn thì cổ phiếu tốt hơn",
             "β chỉ đo độ nhạy, không đo chất lượng. β lớn nghĩa là lỗ cũng mạnh hơn khi thị trường giảm."),
            ("γ là lợi nhuận chắc chắn",
             "γ là phần cố định ước lượng được từ mẫu, không phải cam kết cho tương lai."),
            ("Ba giả thiết luôn đúng nên không cần kiểm tra",
             "Giả thiết nhiễu độc lập giữa các mã cùng ngành thường sai; phải kiểm định."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
    Lesson(
        lesson_id="dh4_phan_ra_rui_ro",
        order=4,
        title="Phân tách rủi ro hệ thống và phi hệ thống",
        objective=(
            "Tách tổng rủi ro thành hai phần theo mô hình chỉ số đơn và giải thích vì "
            "sao hệ số xác định chính là tỷ lệ rủi ro hệ thống."
        ),
        explanation=(
            "Từ mô hình chỉ số đơn, lấy phương sai hai vế và dùng giả thiết nhiễu "
            "không tương quan với thị trường, ta được: σ_i² = β_i²·σ_I² + η_i².\n\n"
            "Trong đó σ_i² là tổng rủi ro của tài sản, β_i²·σ_I² là **rủi ro hệ thống** "
            "do thị trường chung gây ra, còn η_i² là phương sai của nhiễu, tức **rủi ro "
            "phi hệ thống** đặc thù riêng của tài sản. Nói gọn: rủi ro tài sản bằng "
            "rủi ro hệ thống cộng rủi ro phi hệ thống.\n\n"
            "Hệ quả quan trọng: hệ số xác định R² của hồi quy chính là **tỷ lệ rủi ro "
            "hệ thống trong tổng rủi ro**. R² bằng 0,43 nghĩa là khoảng 43% biến động "
            "của cổ phiếu đến từ thị trường, phần còn lại là riêng của doanh nghiệp.\n\n"
            "Với danh mục, hệ số γ và β bằng bình quân gia quyền theo tỷ trọng của các "
            "tài sản thành phần, và σ_P² = β_P²·σ_I² + η_P² với η_P² = Σ w_i²·η_i². "
            "Chính dạng bình phương của w_i giải thích vì sao chia nhỏ tỷ trọng làm "
            "rủi ro phi hệ thống co lại nhanh."
        ),
        example=(
            "Hồi quy một cổ phiếu cho độ lệch chuẩn biến phụ thuộc 0,0185 và sai số "
            "chuẩn hồi quy 0,0141.\n\n"
            "Tổng rủi ro: σ² ≈ 0,0185² ≈ 0,000344. Rủi ro phi hệ thống: η² ≈ 0,0141² "
            "≈ 0,000198.\n\n"
            "Rủi ro hệ thống là phần còn lại ≈ 0,000146, chiếm khoảng 42% tổng rủi ro — "
            "khớp với R² của mô hình."
        ),
        interactive=(
            "Trong Phòng thí nghiệm mô hình → Rủi ro chỉ số đơn, đối chiếu ba cột "
            "rủi ro hệ thống, phi hệ thống và tổng rủi ro với R² của cùng dòng."
        ),
        interactive_kind=INT_SIM,
        questions=(
            Question(
                qid="dh4_q1",
                prompt="Công thức phân tách rủi ro theo mô hình chỉ số đơn là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "σ_i² = β_i²·σ_I² + η_i²",
                    "σ_i² = β_i·σ_I + η_i",
                    "σ_i² = σ_I² − η_i²",
                ),
                answer_index=0,
                explanation="Lấy phương sai hai vế mô hình, phần chéo triệt tiêu nhờ giả thiết.",
            ),
            Question(
                qid="dh4_q2",
                prompt="R² của hồi quy chỉ số đơn cho biết điều gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Tỷ lệ rủi ro hệ thống trong tổng rủi ro",
                    "Xác suất cổ phiếu tăng giá",
                    "Mức lợi suất kỳ vọng",
                ),
                answer_index=0,
                explanation="Đây là cách đọc R² riêng trong bối cảnh mô hình chỉ số đơn.",
            ),
            Question(
                qid="dh4_q3",
                prompt="Tổng rủi ro 0,000400 và rủi ro phi hệ thống 0,000150. Rủi ro hệ thống bằng bao nhiêu (nhập dạng 0.00025)?",
                kind=QUESTION_NUMBER, answer_value=0.00025, tolerance=0.000005,
                explanation="0,000400 − 0,000150 = 0,000250.",
            ),
            Question(
                qid="dh4_q4",
                prompt="Loại rủi ro nào giảm được bằng đa dạng hóa?",
                kind=QUESTION_SINGLE,
                options=("Rủi ro hệ thống", "Rủi ro phi hệ thống", "Cả hai như nhau"),
                answer_index=1,
                explanation="η_P² = Σ w_i²·η_i² co lại khi chia nhỏ tỷ trọng; phần thị trường thì không.",
            ),
        ),
        misconceptions=(
            ("R² thấp nghĩa là mô hình sai",
             "R² thấp chỉ nói cổ phiếu ít chịu ảnh hưởng thị trường, phần riêng lớn. Đó là thông tin, không phải lỗi."),
            ("Đa dạng hóa đủ nhiều thì hết rủi ro",
             "Phần β_P²·σ_I² vẫn còn nguyên dù nắm bao nhiêu mã."),
            ("Beta danh mục là trung bình cộng beta các mã",
             "Là bình quân **gia quyền theo tỷ trọng**, không phải trung bình cộng."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
    Lesson(
        lesson_id="dh5_quy_trinh_uoc_luong",
        order=5,
        title="Quy trình ước lượng và kiểm định mô hình chỉ số đơn",
        objective=(
            "Thực hiện đúng thứ tự: kiểm định tính dừng, hồi quy, rồi kiểm định dạng "
            "hàm; và biết phải làm gì khi một bước không đạt."
        ),
        explanation=(
            "Chuỗi lợi suất là chuỗi thời gian, nên trước khi hồi quy phải kiểm tra "
            "tính dừng để tránh hồi quy giả mạo. Giáo trình dùng kiểm định "
            "Dickey–Fuller mở rộng với giả thiết H là chuỗi **không** dừng; nếu trị "
            "tuyệt đối thống kê τ lớn hơn giá trị tới hạn thì bác bỏ H, kết luận chuỗi dừng.\n\n"
            "Đạt tính dừng rồi mới hồi quy. Dùng bình phương tối thiểu thông thường "
            "nếu các giả thiết được thỏa mãn. Nếu vi phạm — phương sai sai số thay đổi "
            "hoặc tự tương quan — phải hiệu chỉnh, hoặc chuyển sang lớp mô hình "
            "ARCH/GARCH cho phần phương sai thay đổi theo thời gian.\n\n"
            "Bước cuối là kiểm định dạng hàm bằng kiểm định Ramsey, xem mô hình tuyến "
            "tính đã đúng dạng chưa hay còn bỏ sót thành phần phi tuyến.\n\n"
            "Thứ tự này không đảo được. Hồi quy trên chuỗi không dừng cho hệ số đẹp và "
            "thống kê t rất cao nhưng vô nghĩa, và mọi kiểm định sau đó đều mất giá trị."
        ),
        example=(
            "Kiểm định Dickey–Fuller mở rộng cho một chuỗi lợi suất cho τ = −9,90 "
            "trong khi giá trị tới hạn 1% là −3,45.\n\n"
            "Vì |−9,90| > |−3,45| nên bác bỏ giả thiết chuỗi không dừng: chuỗi lợi "
            "suất là dừng, đủ điều kiện hồi quy.\n\n"
            "Nếu kiểm định Ramsey sau đó cho p-value nhỏ, phải xem lại dạng hàm trước "
            "khi dùng β để kết luận."
        ),
        interactive=(
            "Mở EViews tiếng Việt, chạy `ADF` trên chuỗi lợi suất, rồi `LS` để hồi "
            "quy. Đối chiếu kết luận tính dừng với bảng giá trị tới hạn."
        ),
        interactive_kind=INT_DIAG,
        questions=(
            Question(
                qid="dh5_q1",
                prompt="Trong kiểm định Dickey–Fuller, giả thiết H là gì?",
                kind=QUESTION_SINGLE,
                options=("Chuỗi dừng", "Chuỗi không dừng", "Chuỗi có xu thế tuyến tính"),
                answer_index=1,
                explanation="Bác bỏ H mới kết luận chuỗi dừng.",
            ),
            Question(
                qid="dh5_q2",
                prompt="Hồi quy trên chuỗi không dừng dẫn tới hậu quả gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Hồi quy giả mạo, hệ số và thống kê t mất ý nghĩa",
                    "Hệ số luôn bằng không",
                    "Không chạy được",
                ),
                answer_index=0,
                explanation="Đây là lý do phải kiểm định tính dừng trước.",
            ),
            Question(
                qid="dh5_q3",
                prompt="Kiểm định Ramsey dùng để làm gì trong quy trình này?",
                kind=QUESTION_SINGLE,
                options=(
                    "Kiểm tra định dạng mô hình có đúng không",
                    "Kiểm tra tính dừng",
                    "Kiểm tra phân phối chuẩn của phần dư",
                ),
                answer_index=0,
                explanation="Ramsey xét xem dạng hàm tuyến tính đã đủ chưa.",
            ),
            Question(
                qid="dh5_q4",
                prompt="τ = −2,10 và giá trị tới hạn 5% là −2,87. Kết luận là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Bác bỏ H, chuỗi dừng",
                    "Chưa bác bỏ được H, chuỗi coi như không dừng",
                ),
                answer_index=1,
                explanation="|−2,10| < |−2,87| nên chưa đủ cơ sở bác bỏ.",
            ),
        ),
        misconceptions=(
            ("Thống kê t càng lớn thì mô hình càng đáng tin",
             "Trên chuỗi không dừng, t rất lớn là dấu hiệu hồi quy giả mạo chứ không phải mô hình tốt."),
            ("Kiểm định khuyết tật là bước tùy chọn",
             "Vi phạm giả thiết làm sai số chuẩn sai, kéo theo mọi khoảng tin cậy và kiểm định đều lệch."),
            ("Chuỗi giá và chuỗi lợi suất dùng thay nhau được",
             "Chuỗi giá thường không dừng, chuỗi lợi suất thì thường dừng. Phải hồi quy trên lợi suất."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
    Lesson(
        lesson_id="dh6_markowitz",
        order=6,
        title="Phân tích trung bình – phương sai và biên duyên",
        objective=(
            "Phát biểu được bài toán biên duyên, tính bốn đại lượng A, B, C, D theo "
            "ký hiệu giáo trình và suy ra độ dao động của danh mục biên duyên."
        ),
        explanation=(
            "Bài toán biên duyên: với mức lợi suất kỳ vọng r̄_P cho trước, tìm vector "
            "tỷ trọng W sao cho ½·W′VW nhỏ nhất, thỏa hai ràng buộc W′r̄ = r̄_P và "
            "W′[1] = 1. Đây là quy hoạch lồi toàn phương trên tập compact nên nghiệm "
            "tồn tại và duy nhất.\n\n"
            "Giải bằng nhân tử Lagrange dẫn tới W = λ·(V⁻¹r̄) + μ·(V⁻¹[1]). Đặt bốn "
            "đại lượng theo ký hiệu giáo trình:\n\n"
            "• A = [1]′V⁻¹[1]\n"
            "• B = [r̄]′V⁻¹[1]  (số hạng chéo)\n"
            "• C = [r̄]′V⁻¹[r̄]\n"
            "• D = A·C − B²\n\n"
            "Nghiệm viết gọn thành W(r̄_P) = g + r̄_P·h, nghĩa là mọi danh mục biên "
            "duyên đều nằm trên một đường thẳng trong không gian tỷ trọng. Hệ quả: "
            "biết hai danh mục biên duyên là dựng được toàn bộ phần còn lại.\n\n"
            "Phương sai của danh mục biên duyên: σ_P²(r̄_P) = (A·r̄_P² − 2B·r̄_P + C)/D. "
            "Đây là một parabol theo r̄_P, và chính dạng parabol này tạo ra hình quả "
            "chuông quen thuộc của đường biên hiệu quả."
        ),
        example=(
            "Với r̄_P = 0 ta được W(0) = g, tức danh mục biên duyên ứng với lợi suất "
            "kỳ vọng bằng không.\n\n"
            "Với r̄_P = 1 ta được W(1) = g + h. Từ hai danh mục này suy ra mọi danh "
            "mục biên duyên khác theo W(r̄_P) = W(0) + r̄_P·[W(1) − W(0)].\n\n"
            "Thay r̄_P = 35% vào công thức phương sai để có độ dao động tương ứng."
        ),
        interactive=(
            "Mở thẻ Ôn thi, chọn phần đại lượng Markowitz để ứng dụng tính A, B, C, D "
            "từ dữ liệu đã nạp. Đối chiếu với bài làm tay của bạn."
        ),
        interactive_kind=INT_MARKOWITZ,
        questions=(
            Question(
                qid="dh6_q1",
                prompt="Hàm mục tiêu của bài toán biên duyên là gì?",
                kind=QUESTION_SINGLE,
                options=(
                    "Cực tiểu ½·W′VW",
                    "Cực đại W′r̄",
                    "Cực tiểu tổng tỷ trọng",
                ),
                answer_index=0,
                explanation="Tối thiểu phương sai với lợi suất kỳ vọng cho trước.",
            ),
            Question(
                qid="dh6_q2",
                prompt="Theo ký hiệu giáo trình, định thức D được tính thế nào?",
                kind=QUESTION_SINGLE,
                options=("D = A·C − B²", "D = A·B − C²", "D = B·C − A²"),
                answer_index=0,
                explanation="Với A = [1]′V⁻¹[1], B = [r̄]′V⁻¹[1], C = [r̄]′V⁻¹[r̄].",
            ),
            Question(
                qid="dh6_q3",
                prompt="Bài toán biên duyên có mấy ràng buộc?",
                kind=QUESTION_NUMBER, answer_value=2, tolerance=0.01,
                explanation="Ràng buộc lợi suất kỳ vọng và ràng buộc tổng tỷ trọng bằng 1.",
            ),
            Question(
                qid="dh6_q4",
                prompt="Vì sao biết hai danh mục biên duyên là dựng được toàn bộ đường biên?",
                kind=QUESTION_SINGLE,
                options=(
                    "Vì nghiệm có dạng tuyến tính W(r̄_P) = g + r̄_P·h",
                    "Vì đường biên là đường tròn",
                    "Vì mọi danh mục đều có cùng tỷ trọng",
                ),
                answer_index=0,
                explanation="Tuyến tính theo r̄_P nên hai điểm xác định cả đường thẳng.",
            ),
        ),
        misconceptions=(
            ("Ký hiệu A, B, C, D giống nhau ở mọi tài liệu",
             "Nhiều sách hoán đổi vai trò B và C. Khi làm bài, bám ký hiệu của giáo trình "
             "đang dùng và ghi rõ định nghĩa trước khi tính."),
            ("Danh mục biên duyên nào cũng đáng đầu tư",
             "Nửa dưới của biên duyên bị chi phối: cùng mức rủi ro nhưng lợi suất thấp hơn. "
             "Chỉ nửa trên mới là biên hiệu quả."),
            ("Tỷ trọng tối ưu là con số chắc chắn",
             "Nghiệm rất nhạy với ước lượng lợi suất kỳ vọng, vốn sai số lớn trong thực tế."),
        ),
        resources=(_SRC_LECTURE, _SRC_APP),
    ),
)


def all_lessons() -> tuple[Lesson, ...]:
    return tuple(sorted(UNIVERSITY_LESSONS, key=lambda l: l.order))


def get_lesson(lesson_id: str) -> Lesson | None:
    wanted = str(lesson_id or "").strip()
    for lesson in UNIVERSITY_LESSONS:
        if lesson.lesson_id == wanted:
            return lesson
    return None


def total_questions() -> int:
    return sum(len(l.questions) for l in UNIVERSITY_LESSONS)
