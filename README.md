# Quant App

Ứng dụng Streamlit cho hai mục tiêu tách biệt:

- **Học tập:** SIM, Markowitz, EViews tiếng Việt, công cụ ôn thi và trợ lý tính toán an toàn.
- **Nghiên cứu đầu tư:** kiểm định dữ liệu, backtest ngoài mẫu, quản trị rủi ro và paper portfolio.

Ứng dụng không cam kết lợi nhuận và không tự đặt lệnh. Kết quả chỉ được xem là tín hiệu nghiên cứu khi dữ liệu đạt kiểm định, backtest có chi phí và paper trading đủ dài.

## Cài đặt

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Gemini dùng SDK `google-genai`. Model Pro trong giao diện là `gemini-3.1-pro-preview`.

## Kiểm thử

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python smoke_test.py
```

## Nguyên tắc an toàn

- Không thực thi Python do LLM sinh; AI chỉ diễn giải kết quả tính cục bộ.
- Không giữ kết quả cũ khi lần tải dữ liệu mới thất bại.
- Không tối ưu nếu mẫu quá nhỏ, dữ liệu ngoài khoảng ngày, NaN/vô cực hoặc solver lỗi.
- “Tự làm mới” là dữ liệu OHLCV lịch sử/EOD, không phải báo giá realtime.
- Danh mục không vượt lãi suất phi rủi ro có thể trả 100% tiền mặt.
- File upload giới hạn 25 MB và được kiểm tra trước khi parse.

## Trước khi dùng vốn thật

1. Backtest walk-forward qua nhiều chế độ thị trường.
2. Tính đủ phí, thuế, slippage và benchmark.
3. Paper trade tối thiểu 3–6 tháng.
4. Đặt giới hạn lỗ, tỷ trọng mỗi mã/ngành và max drawdown.
5. Người dùng xác nhận mọi lệnh; không tự động giao dịch.

Vnstock dùng giấy phép tùy chỉnh. Cần xác nhận quyền thương mại và quyền dữ liệu trước khi bán dịch vụ hoặc triển khai cho tổ chức.
