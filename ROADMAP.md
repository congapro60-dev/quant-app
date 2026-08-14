# Lộ trình phát triển Quant App

> Trạng thái: **kế hoạch, chưa triển khai**. Tài liệu này không mô tả các tính năng
> đang có, trừ mục “Đã hoàn thành”. Mục tiêu là tiếp tục sau khi quota được làm mới.

## Định vị sản phẩm

Một bộ máy phân tích dùng chung, hai lộ trình trình bày:

- **Nền tảng THPT (High-school foundation):** học tài chính, nghiên cứu dữ liệu,
  đầu tư mô phỏng, sau đó mới mở khóa vốn thật có kiểm soát.
- **Chuyên sâu đại học (University advanced):** SIM, OLS, Markowitz, kiểm thử
  ngoài mẫu, EViews và chẩn đoán mô hình đầy đủ.

Ứng dụng hỗ trợ quyết định; không cam kết lợi nhuận, không giữ tiền và chưa tự đặt
lệnh tại công ty chứng khoán.

## Đã hoàn thành trong đợt hiện tại

- Sửa hợp đồng đơn vị: giá bảng theo nghìn VND/cổ phiếu; tiền, phí, thuế và sổ
  danh mục theo VND.
- Bổ sung phí/thuế, sao lưu JSON, xuất CSV và giám sát vị thế sau mua.
- Sửa sai lệch thời điểm trong kiểm thử quá khứ; quyết định T, thực thi T+1.
- Khóa dữ liệu trong phiên sai mã, sai ngày, quá cũ hoặc có thời điểm tương lai;
  thêm bộ ngắt nguồn dữ liệu lỗi.
- Cải thiện lỗi Gemini, kiểm định nghiên cứu và Việt hóa song ngữ giao diện.

## Ưu tiên ngay khi quota được làm mới

### P0 — Hai chế độ học và hồ sơ người dùng

- Chọn THPT/đại học, lớp, mức kiến thức và mục tiêu.
- Điều hướng theo năm khu vực: Lộ trình học; Khám phá dữ liệu; Phòng thí nghiệm
  mô hình; Đầu tư; Nhật ký và tiến độ.
- Dùng sổ thuật ngữ tập trung: tiếng Việt trước, tiếng Anh trong ngoặc; thêm kiểm
  thử tự động phát hiện nhãn tiếng Anh đứng một mình.

**Nghiệm thu:** đổi chế độ không mất dữ liệu phiên; THPT không thấy tham số đại
học khi chưa mở bài nâng cao; toàn bộ thuật ngữ có giải thích song ngữ.

### P0 — Sáu mô-đun nền tảng THPT

1. Tiền, ngân sách, lãi kép và lạm phát.
2. Cổ phiếu và thị trường hoạt động thế nào.
3. Giá, phần trăm thay đổi và lợi suất.
4. Rủi ro, biến động và đa dạng hóa.
5. Dữ liệu, biểu đồ, tương quan và quan hệ nhân quả.
6. Đầu tư mô phỏng, nhật ký quyết định và phản tư.

Mỗi bài có mục tiêu, ví dụ, tương tác, 3–5 câu kiểm tra, lỗi hiểu sai thường gặp và
nguồn/trang học liệu. Không công khai PDF “lưu hành nội bộ” khi chưa có quyền.

**Nghiệm thu:** học sinh hoàn thành không cần API; phép tính có đáp án vàng; tiến
độ và nhật ký tải xuống được.

### P0 — Cổng sẵn sàng dùng vốn thật cho học sinh

- Thu thập tuổi theo nhóm, không lưu giấy tờ định danh trong Streamlit.
- Dưới 15 tuổi: chỉ mô phỏng trong app; mọi giao dịch thật do người đại diện thực
  hiện ngoài app.
- Từ 15 đến dưới 18 tuổi: kiểm tra kiến thức/rủi ro, xác nhận người đại diện, xác
  minh chính sách công ty chứng khoán, chỉ cổ phiếu/chứng chỉ quỹ bằng tiền có sẵn.
- Dưới 18 tuổi: khóa phái sinh theo quy định; khóa ký quỹ, bán khống, CFD và tài
  sản mã hóa theo **chính sách an toàn của sản phẩm**.
- Hạn mức vốn, tỷ trọng mỗi mã/ngành, mức lỗ ngày/tháng, thời gian chờ trước lệnh
  và xác nhận hai bước với kế hoạch vượt ngưỡng.

**Nghiệm thu:** không thể bỏ qua cổng bằng URL/session state; mọi thay đổi chính
sách có nhật ký; không hiện nút “đủ điều kiện” nếu chưa xác minh tuổi, đại diện và
điều khoản của nhà cung cấp tại thời điểm mở tài khoản.

### P0 — Danh bạ nơi mở tài khoản hợp pháp

- Chỉ liên kết website/app chính chủ của thành viên đang hoạt động tại VSDC/sở
  giao dịch; không mã giới thiệu, không tiếp thị liên kết.
- Hiển thị sản phẩm, phí công bố, yêu cầu tuổi/người đại diện, tên miền, tổng đài,
  ngày kiểm tra và liên kết nguồn.
- Tách rõ cổ phiếu cơ sở, chứng chỉ quỹ và phái sinh; không suy diễn một chính sách
  tuổi áp dụng cho mọi sản phẩm.

**Nghiệm thu:** mỗi mục có ít nhất một nguồn quản lý và một nguồn nhà cung cấp;
liên kết hết hạn hoặc chính sách chưa xác minh bị ẩn/đánh dấu.

Danh sách khởi tạo trung lập, không xếp hạng và không liên kết tiếp thị:

- [SSI iBoard](https://iboard.ssi.com.vn/),
  [MBS Mobile/Web](https://www.mbs.com.vn/huong-dan-mo-tai-khoan/),
  [TCInvest](https://help.tcbs.com.vn/tai-khoan-chung-khoan-va-tieu-khoan-giao-dich/),
  [VNDIRECT DStock](https://dstock.vndirect.com.vn/),
  [Vietcap](https://www.vietcap.com.vn/mo-tai-khoan) và
  [HSC ONE](https://www.hsc.com.vn/vi/tai-khoan): kênh chính chủ để người dùng
  trưởng thành tham khảo; điều kiện người dưới 18 phải hỏi và nhận xác nhận từ
  chính nhà cung cấp trước khi mở.
- [VNSC](https://invest.vnsc.vn/): điều khoản công bố có hiệu lực 01/01/2026 yêu
  cầu khách hàng cá nhân từ đủ 18 tuổi.
- [DragonX](https://dautu.dragoncapital.com.vn/): kênh chứng chỉ quỹ, không phải
  tài khoản môi giới cổ phiếu; có hướng dẫn chính chủ cho tài khoản dưới 18 tuổi
  với cha/mẹ hoặc người giám hộ.

Trước khi dẫn người dùng đi, đối chiếu pháp nhân/trạng thái tại
[danh sách thành viên VSDC](https://vsd.vn/vi/ms), mở app từ website chính chủ,
kiểm tra nhà phát hành trên kho ứng dụng và không chuyển tiền vào tài khoản cá
nhân của môi giới.

## Giai đoạn kế tiếp

### P1 — Tài khoản, lưu trữ và lớp học

- Xác thực, phân quyền học sinh/giáo viên/người đại diện.
- Cơ sở dữ liệu phía máy chủ cho tiến độ, nhật ký, danh mục và lịch sử đồng ý.
- Giáo viên giao bài, xem tiến độ và chấm giả thuyết, bằng chứng, phép tính, kỷ
  luật rủi ro, phản tư; không xếp hạng theo lợi nhuận tuyệt đối.

### P1 — Cố vấn vị thế có điều kiện

- Hồ sơ mục tiêu, thời hạn, sức chịu lỗ và danh mục hiện có.
- Kế hoạch mua theo vùng giá/điều kiện, định cỡ vị thế, mức vô hiệu, chốt lời từng
  phần và nhật ký thay đổi giả thuyết.
- Cảnh báo khi dữ liệu, rủi ro hoặc luận điểm thay đổi; luôn nêu nguồn, độ trễ và
  độ bất định. Trí tuệ nhân tạo chỉ diễn giải kết quả đã được tính và kiểm định.

**Nghiệm thu:** khuyến nghị không qua cổng nghiên cứu sẽ bị chặn; kiểm thử chống
rò rỉ tương lai; tái lập được từ dữ liệu, cấu hình và phiên bản mô hình.

### P1 — Giám sát và thông báo nền

- Tách dịch vụ nền khỏi Streamlit để chạy theo lịch khi người dùng đóng trình duyệt.
- Cảnh báo EOD/trong phiên qua kênh người dùng chọn; chống gửi trùng và có lịch sử.
- Mua quyền dữ liệu phù hợp trước khi gọi “thời gian thực” hoặc bán dịch vụ.

### P2 — Chương trình đại học và EViews

- Ánh xạ bài học tới giáo trình local và số trang; kiểm tra quyền sử dụng.
- Chuyển bộ dữ liệu `.wf1` được phép sang CSV/Parquet có siêu dữ liệu.
- Bổ sung đáp án vàng cho OLS, SIM, Markowitz, ADF, White, Breusch–Godfrey,
  Ramsey RESET và VIF.

### P2 — Kết nối công ty chứng khoán

- Trước mắt chỉ mở liên kết chính chủ/deep link và yêu cầu người dùng tự xác nhận
  lệnh.
- Chỉ cân nhắc truyền lệnh qua API sau khi có hợp đồng nhà cung cấp, rà pháp lý,
  bảo mật khóa, nhật ký kiểm toán và phê duyệt riêng. Không đưa vào bản THPT đầu.

## Điều kiện trước khi thương mại hóa

- Xác nhận giấy phép `vnstock`, quyền dữ liệu và quyền sử dụng học liệu.
- Rà soát pháp lý bởi chuyên gia tại thời điểm phát hành, nhất là tài khoản người
  chưa thành niên và tư vấn đầu tư.
- Kiểm thử bảo mật, sao lưu/khôi phục, quyền riêng tư trẻ em và kế hoạch ứng cứu.
- Thử nghiệm có giám sát với nhóm nhỏ; đo năng lực tài chính và kỷ luật rủi ro,
  không dùng lợi nhuận ngắn hạn làm thước đo chất lượng sản phẩm.

## Nguồn thiết kế và pháp lý cần kiểm tra lại khi triển khai

- [Khung hiểu biết tài chính PISA 2022](https://www.oecd.org/en/publications/pisa-2022-assessment-and-analytical-framework_dfe0bf9c-en/full-report/component-4.html)
- [Chương trình giáo dục phổ thông của Bộ GDĐT](https://vbpl.vn/bogiaoducdaotao/Pages/vbpq-toanvan.aspx?ItemID=146721)
- [Bộ luật Dân sự 2015](https://vbpl.vn/nganhangnhanuoc/Pages/vbpq-toanvan.aspx?ItemID=95942)
- [Quy định giao dịch chứng khoán cơ sở hợp nhất, cập nhật 2026](https://congbaocdn.chinhphu.vn/180507251028987904/2026/5/29/469538-1779683486_v1_1780016834_signed.pdf)
- [Quy định chứng khoán phái sinh hợp nhất hiện hành](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/10/46509/59573-1-20251555-155643-vbhn-btc.pdf)
- [Hướng dẫn tài khoản dưới 18 tuổi của Dragon Capital](https://dautu.dragoncapital.com.vn/kien-thuc/huong-dan-tao-tai-khoan-cho-con-dragonx)

Các điều kiện tuổi và sản phẩm có thể thay đổi. Ngày triển khai phải xác minh lại
với văn bản hiện hành và nhà cung cấp; tài liệu này không phải ý kiến pháp lý.
