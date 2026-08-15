"""Giới thiệu và hướng dẫn dùng cho từng chức năng.

Gom vào một nơi để mọi chức năng có cùng khuôn: *là gì → để làm gì → làm thế
nào → đọc kết quả ra sao → dễ sai ở đâu*. Người dùng mở bất kỳ thẻ nào cũng
biết ngay mình đang ở đâu và phải bấm gì, không phải đoán.

Nội dung là văn xuôi tiếng Việt cho người đọc nên tuân thủ quy tắc biên tập:
mỗi ý một đoạn ngắn, liệt kê từ ba mục trở lên thì dùng gạch đầu dòng.
"""

from __future__ import annotations

from dataclasses import dataclass

import learning_modes as lmode


@dataclass(frozen=True)
class FeatureGuide:
    """Khuôn giải thích thống nhất cho một chức năng."""

    what: str
    why: str
    steps: tuple[str, ...]
    read_result: str
    caution: str

    def __post_init__(self) -> None:
        if len(self.steps) < 2:
            raise ValueError("Hướng dẫn cần ít nhất hai bước.")


# Khóa cho các bảng không nằm trong FEATURES của learning_modes.
PANEL_READINESS = "cong_von_that"
PANEL_PROVIDERS = "noi_mo_tai_khoan"
PANEL_PROGRESS = "tien_do_rubric"
PANEL_JOURNAL = "nhat_ky_quyet_dinh"
PANEL_POLICY = "lich_su_thiet_lap"


GUIDES: dict[str, FeatureGuide] = {
    lmode.FEATURE_INTRADAY: FeatureGuide(
        what="Xem từng lệnh khớp trong phiên của một mã, kèm giá và khối lượng.",
        why=(
            "Giúp bạn thấy giá hình thành ra sao trong ngày, thay vì chỉ nhìn một "
            "con số đóng cửa. Đây là nơi quan sát, không phải nơi ra quyết định mua bán."
        ),
        steps=(
            "Nhập một mã cổ phiếu, ví dụ CTG.",
            "Chọn số lệnh gần nhất muốn xem.",
            "Bấm **Lấy dữ liệu trong phiên**, hoặc bật **Tự làm mới giá** nếu muốn theo dõi liên tục.",
        ),
        read_result=(
            "Bốn ô số ở trên cho giá khớp gần nhất, thời điểm khớp, số lệnh lấy về "
            "và nguồn dữ liệu. Dòng ngay dưới hiện **độ trễ đo được** của lần tải đó."
        ),
        caution=(
            "Đây là dữ liệu có độ trễ, không phải bảng giá tức thời. Chỉ có dữ liệu "
            "trong khung khớp lệnh liên tục 9:15–11:30 và 13:00–14:30; ngoài khung "
            "đó trống là bình thường."
        ),
    ),
    lmode.FEATURE_SIM: FeatureGuide(
        what=(
            "Hồi quy lợi suất một cổ phiếu theo lợi suất chỉ số thị trường để tách "
            "rủi ro thành hai phần."
        ),
        why=(
            "Cho biết cổ phiếu nhạy với thị trường đến mức nào (hệ số beta), và bao "
            "nhiêu phần rủi ro đến từ thị trường chung so với từ riêng doanh nghiệp. "
            "Phần rủi ro riêng có thể giảm bằng đa dạng hóa; phần theo thị trường thì không."
        ),
        steps=(
            "Nhập vài mã và chỉ số ở thanh bên rồi bấm **🚀 Phân tích**.",
            "Đọc bảng tổng quan rủi ro của tất cả các mã.",
            "Chọn một mã ở ô bên dưới để xem biểu đồ hồi quy của riêng mã đó.",
        ),
        read_result=(
            "Beta lớn hơn 1 nghĩa là cổ phiếu dao động mạnh hơn thị trường; nhỏ hơn 1 "
            "là dịu hơn. R² cho biết bao nhiêu phần trăm biến động của cổ phiếu được "
            "giải thích bởi chỉ số."
        ),
        caution=(
            "R² cao không có nghĩa mô hình đúng. Phải xem các kiểm định khuyết tật ở "
            "cùng bảng: phương sai sai số thay đổi làm sai số chuẩn sai, kéo theo mọi "
            "suy diễn thống kê sau đó đều lệch."
        ),
    ),
    lmode.FEATURE_MARKOWITZ: FeatureGuide(
        what=(
            "Tìm tỷ trọng phân bổ vốn giữa các mã sao cho danh mục có biến động thấp "
            "nhất, hoặc có tỷ lệ lợi nhuận trên rủi ro cao nhất."
        ),
        why=(
            "Trả lời câu hỏi thực tế: cùng một số tiền và cùng danh sách mã, chia thế "
            "nào thì hợp lý hơn. Kết quả cho thấy đa dạng hóa làm giảm biến động ra sao."
        ),
        steps=(
            "Nạp dữ liệu cho **ít nhất hai mã** ở thanh bên.",
            "Xem hai danh mục gợi ý: biến động nhỏ nhất và tỷ lệ Sharpe cao nhất.",
            "Đối chiếu vị trí hai danh mục đó trên đường biên hiệu quả.",
        ),
        read_result=(
            "Biểu đồ tròn cho tỷ trọng từng mã. Đường biên hiệu quả cho thấy với mỗi "
            "mức rủi ro thì lợi suất kỳ vọng cao nhất có thể là bao nhiêu."
        ),
        caution=(
            "Tỷ trọng tối ưu rất nhạy với lợi suất kỳ vọng đầu vào. Lệch một chút ở "
            "đầu vào có thể làm đảo lộn toàn bộ kết quả, nên đừng coi tỷ trọng là con "
            "số chính xác tuyệt đối."
        ),
    ),
    lmode.FEATURE_BACKTEST: FeatureGuide(
        what=(
            "Chạy lại một chiến lược trên dữ liệu quá khứ, nhưng chỉ cho phép mỗi "
            "quyết định nhìn thấy dữ liệu có trước ngày thực hiện."
        ),
        why=(
            "Một chiến lược nhìn đẹp trên dữ liệu đã dùng để xây nó thì chưa nói lên "
            "điều gì. Kiểm thử ngoài mẫu cho biết nó còn đứng vững khi gặp dữ liệu chưa từng thấy."
        ),
        steps=(
            "Nạp dữ liệu đủ dài ở thanh bên, tối thiểu vài trăm phiên.",
            "Đặt phí, thuế và độ trượt giá đúng với thực tế bạn sẽ chịu.",
            "Chạy kiểm thử rồi đọc kết quả cùng với đường vốn.",
        ),
        read_result=(
            "Nhìn cả lợi nhuận lẫn mức sụt giảm sâu nhất. Một chiến lược lãi cao nhưng "
            "có lúc âm 40% là thứ rất ít người giữ được tới cuối."
        ),
        caution=(
            "Quyết định tại phiên T phải được thực hiện từ phiên T+1. Trộn lẫn hai mốc "
            "này là rò rỉ thông tin tương lai, và kết quả sẽ đẹp một cách giả tạo."
        ),
    ),
    lmode.FEATURE_INVEST_DESK: FeatureGuide(
        what="Sàng lọc danh sách mã đã nạp và lập kịch bản mua có điều kiện.",
        why=(
            "Buộc bạn viết ra trước: mua vùng giá nào, sai thì thoát ở đâu, và kế hoạch "
            "hết hiệu lực khi nào. Viết trước là cách duy nhất để biết mình đúng vì lý "
            "do đúng hay chỉ gặp may."
        ),
        steps=(
            "Nạp dữ liệu ở thanh bên.",
            "Xem bảng sàng lọc để biết mã nào đang có xu hướng và biến động ra sao.",
            "Lập kịch bản cho một mã: vùng mua, mức dừng lỗ, mục tiêu và ngày hết hiệu lực.",
        ),
        read_result=(
            "Bảng cho biết mã nào đạt điều kiện sàng lọc. Đây là danh sách để nghiên "
            "cứu tiếp, không phải danh sách nên mua."
        ),
        caution=(
            "Không có kịch bản nào bảo đảm sinh lời. Mọi con số ở đây là điều kiện bạn "
            "tự đặt ra, không phải dự báo của ứng dụng."
        ),
    ),
    lmode.FEATURE_PAPER: FeatureGuide(
        what="Sổ danh mục mô phỏng: mua bán bằng tiền giả với giá thật.",
        why=(
            "Đây là nơi để sai mà không mất tiền. Mục đích không phải đạt lãi cao trong "
            "sổ, mà để lộ ra thói quen ra quyết định của chính bạn."
        ),
        steps=(
            "Đặt số vốn mô phỏng ban đầu.",
            "Ghi lệnh mua hoặc bán với đúng giá đã khớp, kèm phí và thuế.",
            "Theo dõi lãi/lỗ đã thực hiện và chưa thực hiện, tải sổ về định kỳ.",
        ),
        read_result=(
            "Sổ tách riêng phần lãi/lỗ đã chốt và phần còn nắm giữ. Tiền mặt, phí và "
            "thuế đều theo đơn vị đồng."
        ),
        caution=(
            "Sổ chỉ tồn tại trong phiên trình duyệt. Đóng trình duyệt là mất nếu bạn "
            "chưa tải bản sao về. Giao dịch mô phỏng nên kéo dài vài tháng mới đủ ý nghĩa."
        ),
    ),
    lmode.FEATURE_ADVISOR: FeatureGuide(
        what=(
            "Tổng hợp các số liệu đã tính được thành một bản nhận xét bằng lời, có thể "
            "nhờ trí tuệ nhân tạo diễn giải."
        ),
        why=(
            "Giúp bạn nối các con số rời rạc thành một câu chuyện mạch lạc, và nhìn ra "
            "chỗ các kết quả mâu thuẫn nhau."
        ),
        steps=(
            "Chạy phân tích và các mô hình trước, vì phần này chỉ diễn giải kết quả đã có.",
            "Nếu muốn dùng trí tuệ nhân tạo, nhập khóa giao diện lập trình ở thanh bên.",
            "Đọc nhận xét và đối chiếu lại với bảng số gốc.",
        ),
        read_result=(
            "Bản nhận xét nêu xu hướng, nhóm mã theo mức nhạy với thị trường và gợi ý "
            "phân bổ. Đây là diễn giải, không phải khuyến nghị mua bán."
        ),
        caution=(
            "Máy tính tạo ra số, trí tuệ nhân tạo chỉ diễn giải. Không có khóa giao diện "
            "lập trình thì phần này vẫn chạy bằng quy tắc dựng sẵn."
        ),
    ),
    lmode.FEATURE_EVIEWS: FeatureGuide(
        what="Môi trường gõ lệnh kiểu EViews bằng tiếng Việt, chạy trên tệp bạn tải lên.",
        why=(
            "Làm lại bài tập trên lớp mà không cần cài EViews. Bảng kết quả hồi quy được "
            "dịch sang tiếng Việt để dễ đối chiếu với giáo trình."
        ),
        steps=(
            "Tải tệp dữ liệu của bạn lên, chọn đúng trang tính.",
            "Gõ lệnh quen thuộc, ví dụ `LS Y C X1 X2` để hồi quy bình phương tối thiểu.",
            "Dùng **Chọn nhanh** nếu chưa nhớ cú pháp.",
        ),
        read_result=(
            "Bảng kết quả có hệ số, sai số chuẩn, thống kê t và xác suất, kèm R², "
            "kiểm định Jarque–Bera và nhân tử phóng đại phương sai."
        ),
        caution=(
            "Đơn vị và tần suất dữ liệu phải khớp đề bài. Sai chỗ này thì hệ số vẫn ra "
            "nhưng ý nghĩa đã khác."
        ),
    ),
    lmode.FEATURE_EXAM: FeatureGuide(
        what="Máy tính bỏ túi cho các công thức hay gặp trong bài kiểm tra kinh tế lượng.",
        why=(
            "Tự kiểm tra đáp án sau khi làm tay, thay vì chờ chữa bài. Mỗi công thức "
            "hiện kèm dạng ký hiệu để đối chiếu với giáo trình."
        ),
        steps=(
            "Nạp dữ liệu ở thẻ **EViews tiếng Việt** trước, phần này dùng chung dữ liệu đó.",
            "Chọn đại lượng cần tính: lợi suất, rủi ro theo mô hình chỉ số đơn, ma trận "
            "hiệp phương sai hay các đại lượng Markowitz.",
            "So kết quả máy tính với bài làm tay của bạn.",
        ),
        read_result=(
            "Mỗi mục hiện công thức trước, kết quả sau, để bạn thấy con số đến từ đâu."
        ),
        caution=(
            "Công cụ tính đúng theo công thức đã lập trình. Nếu đề bài dùng quy ước khác, "
            "phải tự điều chỉnh chứ đừng chép thẳng."
        ),
    ),
    PANEL_READINESS: FeatureGuide(
        what="Bảng tự soát trước khi chuyển từ giao dịch mô phỏng sang tiền thật.",
        why=(
            "Đưa ra danh sách những việc bạn và người đại diện phải tự xác minh với công "
            "ty chứng khoán, và khóa các nhóm sản phẩm không phù hợp với độ tuổi."
        ),
        steps=(
            "Chọn nhóm tuổi của bạn.",
            "Tích các ô xác nhận đúng với thực tế, không tích cho xong.",
            "Đặt hạn mức rủi ro ở phần bên dưới.",
        ),
        read_result=(
            "Phần **Còn thiếu** liệt kê điều kiện chưa đạt. Phần **Nhóm sản phẩm bị khóa** "
            "nêu rõ vì sao từng nhóm bị chặn."
        ),
        caution=(
            "Ứng dụng không xác minh được người đại diện hay chính sách công ty chứng "
            "khoán, nên không bao giờ kết luận bạn đủ điều kiện. Ứng dụng cũng không mở "
            "tài khoản và không gửi lệnh."
        ),
    ),
    PANEL_PROVIDERS: FeatureGuide(
        what="Danh bạ các nơi mở tài khoản, xếp theo bảng chữ cái, không xếp hạng.",
        why=(
            "Cho bạn tên pháp nhân và đường dẫn chính chủ để tự kiểm tra, thay vì tin "
            "vào quảng cáo hay lời giới thiệu."
        ),
        steps=(
            "Đọc bảng để so nhóm sản phẩm của từng nơi.",
            "Mở mục chi tiết của nơi bạn quan tâm.",
            "Đối chiếu tư cách thành viên tại danh sách của cơ quan lưu ký trước khi mở tài khoản.",
        ),
        read_result=(
            "Mục nào ghi *Chưa xác minh* nghĩa là ứng dụng chưa tìm được nguồn chính chủ "
            "cho thông tin đó, bạn phải tự hỏi nhà cung cấp."
        ),
        caution=(
            "Ứng dụng không nhận hoa hồng và không có mã giới thiệu. Điều kiện tuổi, phí "
            "và sản phẩm thay đổi theo thời gian nên phải kiểm lại tại thời điểm mở."
        ),
    ),
    PANEL_PROGRESS: FeatureGuide(
        what="Nơi lưu điểm bài học, điểm kiểm tra và điểm tổng theo thang đánh giá.",
        why=(
            "Cho bạn và giáo viên thấy tiến bộ theo năng lực và kỷ luật, chứ không theo "
            "lợi nhuận ngắn hạn."
        ),
        steps=(
            "Làm bài ở **Lộ trình học**, điểm tự chuyển về đây.",
            "Nhập điểm kiểm tra đầu vào và đầu ra nếu có.",
            "Tải hồ sơ về dạng JSON để giữ lại.",
        ),
        read_result=(
            "Thang đánh giá chia bốn phần: kiến thức 30%, lập luận 30%, kỷ luật rủi ro "
            "và chất lượng nguồn 25%, nhật ký và phản tư 15%."
        ),
        caution=(
            "Hồ sơ chỉ nằm trong phiên trình duyệt. Không tải về thì đóng trình duyệt là mất."
        ),
    ),
    PANEL_JOURNAL: FeatureGuide(
        what="Nơi bạn tự viết lý do trước khi hành động.",
        why=(
            "Viết trước là cách duy nhất giữ lại lý do gốc. Viết sau khi biết kết quả thì "
            "trí nhớ sẽ tự chỉnh lý do cho khớp, và bài học biến mất."
        ),
        steps=(
            "Ghi bạn định làm gì và vì sao, **trước** khi đặt lệnh mô phỏng.",
            "Ghi rõ điều gì chứng minh bạn sai, và mức lỗ tối đa chấp nhận.",
            "Sau vài tuần đọc lại và tự hỏi lý do ban đầu còn đúng không.",
        ),
        read_result="Các mục xếp theo thời gian, mới nhất ở trên.",
        caution=(
            "Khác với **Lịch sử thiết lập** — mục đó do ứng dụng tự ghi khi bạn đổi "
            "thiết lập, còn mục này do bạn viết."
        ),
    ),
    PANEL_POLICY: FeatureGuide(
        what="Nhật ký do ứng dụng tự ghi mỗi khi bạn đổi thiết lập an toàn.",
        why=(
            "Để sau này còn soát lại: hạn mức bị nới lúc nào, ai đó đổi nhóm tuổi ra sao. "
            "Không có nhật ký thì mọi thay đổi đều biến mất không dấu vết."
        ),
        steps=(
            "Đổi nhóm tuổi, xác nhận hay hạn mức ở thẻ **Sẵn sàng dùng vốn thật**.",
            "Quay lại đây xem thay đổi đã được ghi.",
            "Tải nhật ký về nếu cần nộp cho giáo viên hoặc người đại diện.",
        ),
        read_result="Mỗi dòng có thời điểm, mục thiết lập, giá trị cũ và giá trị mới.",
        caution=(
            "Nhật ký không chứa giấy tờ định danh, nên tải về và gửi đi được mà không lộ "
            "thông tin cá nhân."
        ),
    ),
}


def get_guide(key: str) -> FeatureGuide | None:
    return GUIDES.get(key)


def render_guide(key: str, *, expanded: bool = False) -> bool:
    """Hiện hộp hướng dẫn ở đầu một chức năng.

    Mặc định gấp lại để không che nội dung chính, nhưng luôn có mặt nên người
    dùng lần đầu vào thẻ nào cũng biết thẻ đó để làm gì.

    Trả về ``False`` nếu chưa có hướng dẫn cho khóa này, để tầng gọi biết mà bổ
    sung thay vì im lặng bỏ qua.
    """

    import streamlit as st  # nhập cục bộ để tệp này kiểm thử được không cần Streamlit

    guide = get_guide(key)
    if guide is None:
        return False

    with st.expander("ℹ️ Chức năng này là gì và dùng thế nào?", expanded=expanded):
        st.markdown(f"**Là gì.** {guide.what}")
        st.markdown(f"**Để làm gì.** {guide.why}")

        st.markdown("**Các bước**")
        for i, step in enumerate(guide.steps, start=1):
            st.markdown(f"{i}. {step}")

        st.markdown(f"**Đọc kết quả.** {guide.read_result}")
        st.warning(f"**Dễ sai ở đây.** {guide.caution}")
    return True
