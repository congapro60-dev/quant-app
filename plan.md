# Quant App: giao diện theo việc cần làm

Ngày: 2026-10-15. Trạng thái: đã kiểm thử, người dùng đã yêu cầu push.

Người dùng yêu cầu cải thiện giao diện, tính năng và đối chiếu luồng Muse
`01a13816-85b6-7142-a505-6dec2b85f5cc`; cho phép code trực tiếp bằng
`gpt-6-astra`, mức `xhigh`, kể cả tác nhân phụ. Không gọi model ngoài.
Quyết định thực hiện sau rà soát: giữ Streamlit và bộ máy tài chính; sửa đường
đi và phản hồi trước khi bổ sung mô hình. Nền kiểm tra: master `f7c76dc`, sạch.

## Phạm vi

1. Trang Tổng quan: ba đường vào Học, Phân tích, Mô phỏng; trạng thái dữ liệu,
   tiến độ và đường quay lại công việc. Điều hướng có trạng thái, dùng nút thật.
2. Thu gọn đầu trang/thanh bên; giữ phong cách xanh đậm, cải thiện tương phản,
   nhịp chữ và giao diện điện thoại. Thuật ngữ tiếng Anh đi kèm tiếng Việt.
3. Khám phá dữ liệu: thêm lịch sử giá cuối ngày cho cả THPT, bảng/biểu đồ/xuất
   dữ liệu có đơn vị và nguồn. Không trộn giá cổ phiếu với điểm chỉ số.
4. Bài học: tiếp tục bài chưa đạt, trước/sau, giữ phản hồi chấm qua lần chạy lại,
   nối bản đồ học tới đúng công cụ. Không đổi cách chấm hoặc điều kiện mở khóa.
5. Muse: tạo bản yêu cầu học liệu từ bài học hiện có, ba mục tiêu tự học
   (chuẩn bị, ôn tập, học mới), kèm tiêu chí kiểm chứng và tải tệp. Chỉ soạn trên
   máy; người dùng tự gửi. Không tự truyền hồ sơ, điểm, danh mục hoặc API key.

## Giới hạn và bằng chứng

- `app.py` dựng thẻ lồng, hướng dẫn bắt đầu ở sau bài học dài.
- `learning_ui.py` mất phản hồi sau `st.rerun`; bản đồ học chỉ dẫn bằng chữ.
- Streamlit 1.60.0 có thẻ với key và callback; giữ render các công cụ hiện có
  để tránh mất trạng thái widget khi đổi thẻ. Không chuyển framework.
- Luồng Muse mô tả tạo học liệu, nghiên cứu, ảnh/video và công cụ nối ngoài.
  Chưa xác minh API tự động hay quyền từng tài khoản; không xây tích hợp giả.
- Giữ `data_loader.py`, `analytics.py`, `backtesting.py`, `portfolio.py`,
  cổng vốn thật, hạn mức, đơn vị VND và các điều kiện chặn dữ liệu không hợp lệ.
- Không đặt lệnh, thêm dependency hoặc gửi Muse. Sau bản xem trước, người dùng
  yêu cầu sửa font tiếng Việt và push toàn bộ bản cải thiện lên GitHub.

## Thứ tự và kiểm chứng

| Việc | Người làm | Kiểm chứng | Trạng thái |
|---|---|---|---|
| Rà soát UX và rủi ro điều hướng | Astra xhigh, chỉ đọc | Đối chiếu code và API runtime | pass |
| Tổng quan, điều hướng, lịch sử giá | Chính | AppTest; nút chuyển khu trên Edge; đơn vị chỉ số/giá tách riêng | pass |
| Luồng học và phản hồi | Tác nhân phụ + chính hoàn thiện | Chấm, rerun, chuyển bài, mở khóa | pass |
| Bản yêu cầu Muse | Chính | 12 bài, 3 mục tiêu; kiểm tra không xuất thông tin riêng | pass |
| Kiểm thử cuối và review | Chính + tác nhân phụ chỉ đọc | 608 kiểm thử toàn bộ; 95 kiểm thử lại sau chỉnh cuối; compile, pip check, diff | pass |

Review trước triển khai: tránh đổi thẻ thành render có điều kiện khi chưa bảo
toàn widget; giữ công cụ cũ, bổ sung nút chuyển có key. Dữ liệu lịch sử nằm
riêng với giá khớp trong phiên. Không diễn giải khả năng Muse thành bảo đảm
chất lượng tài chính. Người dùng đã cho phép thực hiện tự chủ sau rà soát.

## Bằng chứng bàn giao

- Đã xem trực tiếp `https://muse.ai/` trên Edge: có Mục tiêu, Thư viện,
  Phê duyệt, Sắp tới; có hoạt động tạo tài liệu và nhắc lịch. Chưa gửi yêu cầu,
  chưa tạo tác vụ định kỳ, chưa kiểm chứng quyền tạo ảnh/video của tài khoản.
- Giao diện thật: trang tổng quan desktop, nút chuyển tới Lịch sử giá,
  điện thoại 390×844 không tràn ngang (scrollWidth = 390), tab cao 44px.
  Edge ngắt kết nối sau đó: chưa kiểm thử trực tuyến đủ quy trình nạp giá,
  giao dịch mô phỏng và tải tệp bằng trình duyệt trong đợt này.
- AppTest kiểm tra các luồng điều hướng, học/chấm/mở khóa, lịch sử giá,
  xuất nội dung Muse không chứa thông tin riêng. Nguồn giá thật không được
  giả lập thành thành công trong báo cáo.
- Đợt kiểm lại có một timeout AppTest mặc định 3 giây khi dựng Plotly;
  tăng giới hạn kiểm thử lên 30 giây, 95/95 đạt. Không tăng thời gian chờ trong app.
- Reviewer phát hiện đếm sai nguồn sổ giao dịch, CTA học quay lại Muse,
  trục `time` chưa Việt hóa; đã sửa và kiểm thử hồi quy.
- Tác nhân phụ được yêu cầu `gpt-6-astra`/`xhigh`. Hai phiên bị lỗi xác thực,
  thông báo backend ghi `gpt-6-luna`; không xác nhận toàn bộ model thực phục vụ.
  Phiên chính hoàn thiện phần còn lại. Không gọi model khác hãng/9router thủ công.
- Không thay bộ máy tài chính, cổng vốn thật, dependency, cấu hình triển khai.
  Bản xem trước cục bộ: `http://127.0.0.1:8599/`.
- Sửa font trước phát hành: bỏ ép Georgia/Times New Roman ở tiêu đề; dùng
  Source Sans có sẵn của Streamlit. Kiểm tra trực tiếp trên trình duyệt trong
  Codex: chữ “muốn” hiển thị đúng; computed font = `"Source Sans", sans-serif`.
  Chạy lại toàn bộ suite sau sửa: 608/608 đạt trong 187.08 giây.

## Đợt 1 đã duyệt: nền tảng lớp học

Người dùng duyệt hướng nâng cấp để dạy trên lớp và cho học sinh tự luyện.
Đợt này chỉ làm nền tảng học tập có thể kiểm chứng:

- kiểm tra đầu vào thật, không cho nhập điểm giả;
- lưu lịch sử lần làm, lỗi từng câu và tiến bộ;
- tách tự phản tư khỏi điểm giáo viên;
- gói bài tập giáo viên → học sinh và gói kết quả học sinh → giáo viên;
- giữ app chạy không cần API, tài khoản hoặc model ngoài.

Chưa làm trong đợt này: cơ sở dữ liệu tài khoản, bảng điều khiển trực tuyến,
đồng bộ lớp qua Internet, cảnh báo nền, API môi giới, tự động giao dịch.

### Kết quả đợt 1

- Đã làm: chẩn đoán cục bộ, lịch sử lần làm, tự phản tư tách rubric, thực hành
  THPT có nút/chức năng thật, gói lớp học JSON an toàn, bộ dữ liệu minh họa
  offline, liên kết tham khảo Agents AI không tự truyền dữ liệu.
- Chưa làm: tài khoản/đồng bộ trực tuyến và dashboard giáo viên. Đây là bước kế
  tiếp vì cần quyết định lưu trữ, phân quyền và quyền truy cập dữ liệu học sinh.
- Kiểm thử đợt: 629 kiểm thử toàn bộ đạt; thêm kiểm tra AppTest bộ mẫu chạy được
  SIM/Markowitz sau lỗi nguồn dữ liệu.
