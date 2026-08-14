# Quant App

Ứng dụng Streamlit cho hai mục tiêu tách biệt:

- **Học tập:** SIM, Markowitz, EViews tiếng Việt, công cụ ôn thi và trợ lý tính toán an toàn.
- **Nghiên cứu đầu tư:** kiểm định dữ liệu, kiểm thử quá khứ ngoài mẫu
  (out-of-sample backtest), quản trị rủi ro và danh mục mô phỏng (paper portfolio).

Ứng dụng không cam kết lợi nhuận và không tự đặt lệnh. Kết quả chỉ được xem là tín hiệu nghiên cứu khi dữ liệu đạt kiểm định, kiểm thử quá khứ (backtest) có chi phí và giao dịch mô phỏng (paper trading) đủ dài.

Các tính năng lớn chưa triển khai được ghi rõ trong [lộ trình phát triển](ROADMAP.md).

## Cài đặt

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Gemini dùng SDK `google-genai`. Model Pro trong giao diện là
`gemini-3.1-pro-preview`; dự án dùng hạn mức miễn phí (Free Tier) có thể không được
cấp dung lượng sử dụng (quota) cho mô hình này. Ứng dụng phân loại lỗi hạn mức/tầng
dịch vụ (quota/tier) và hướng dẫn dùng Flash hoặc bật tầng trả phí (Paid Tier),
không tự động đổi model làm thay đổi kết quả.

## Kiểm thử

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python smoke_test.py
```

## Nguyên tắc an toàn

- Không thực thi Python do mô hình ngôn ngữ lớn (LLM) sinh; trí tuệ nhân tạo (AI)
  chỉ diễn giải kết quả tính cục bộ.
- Không giữ kết quả cũ khi lần tải dữ liệu mới thất bại.
- Không tối ưu nếu mẫu quá nhỏ, dữ liệu ngoài khoảng ngày, NaN/vô cực hoặc bộ giải
  (solver) lỗi.
- “Tự làm mới” là dữ liệu mở-cao-thấp-đóng cửa-khối lượng (OHLCV) lịch sử/cuối ngày
  (EOD), không phải báo giá thời gian thực (realtime).
- Dữ liệu khớp lệnh trong phiên phải đúng mã, đúng ngày giao dịch Việt Nam và còn trong
  ngưỡng độ trễ an toàn; dữ liệu mơ hồ, cũ hoặc có thời điểm tương lai bị từ chối.
- Nguồn lỗi diện rộng được đưa vào thời gian chờ (cooldown) ngắn bằng bộ ngắt mạch
  (circuit breaker); ứng dụng vẫn thử nguồn dự phòng nhưng không lưu bộ nhớ đệm
  (cache) giá hoặc kết quả lỗi.
- Giá bảng Việt Nam hiển thị theo **nghìn VND/cổ phiếu**; định cỡ vị thế (position
  sizing), phí, thuế, tiền mặt và sổ danh mục mô phỏng (paper ledger) lưu theo **VND**.
  Việc đổi đơn vị chỉ diễn ra ở biên vào/ra của sổ.
- Kiểm thử quá khứ (backtest) mặc định ra quyết định tại giá đóng cửa kỳ T, thực thi
  từ kỳ T+1 và chỉ ghi
  nhận lợi suất đủ điều kiện sau khi lệnh có thể được khớp; nhật ký lưu riêng các mốc này.
- Danh mục không vượt lãi suất phi rủi ro có thể trả 100% tiền mặt.
- Tệp tải lên (file upload) giới hạn 25 MB và được kiểm tra trước khi đọc (parse).

## Trước khi dùng vốn thật

1. Kiểm thử cuốn chiếu (walk-forward backtest) qua nhiều chế độ thị trường.
2. Tính đủ phí, thuế, độ trượt giá (slippage) và điểm chuẩn so sánh (benchmark).
3. Tải bản sao JSON của danh mục mô phỏng (paper portfolio) định kỳ; dữ liệu này chỉ tồn tại theo phiên
   Streamlit nếu không chủ động sao lưu. Bảng giám sát vị thế dùng giá đánh dấu cuối
   ngày (EOD mark)/giá nhập tay, mức dừng lỗ (stop) và mục tiêu (target) của kế hoạch;
   không phải báo giá thời gian thực (realtime). Giao dịch mô phỏng (paper trade) tối thiểu
   3–6 tháng.
4. Đặt giới hạn lỗ, tỷ trọng mỗi mã/ngành và mức sụt giảm tối đa (maximum drawdown).
5. Người dùng xác nhận mọi lệnh; không tự động giao dịch.

Vnstock dùng giấy phép tùy chỉnh. Cần xác nhận quyền thương mại và quyền dữ liệu trước khi bán dịch vụ hoặc triển khai cho tổ chức.
