# HANDOFF — Quant App

**Cập nhật**: 2026-10-23 · **Repo**: https://github.com/congapro60-dev/quant-app · **Branch chuẩn**: `master` · **Production**: https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app

## 1. Trạng thái hiện tại

App production **không khởi động được từ 16/10/2026**. Người xem thấy vòng xoay
"Hmm... looks like it's taking longer than normal"; endpoint `/_stcore/health` không trả lời,
tức container chưa bao giờ lên — không phải app chạy chậm.

Nguyên nhân: app trên Streamlit Cloud chạy **CPython 3.14** (chọn lúc deploy, sau đó không đổi được).
Commit `e9eac4e` đổi sang `vnstock==4.0.9` + `vnstock_ezchart==1.0.2`; ezchart 1.0.2 chặn
`numpy<2.3`, mà **không bản NumPy 2.2.x nào có wheel cho CPython 3.14**. Pip buộc phải build NumPy
từ source, build không xong trong hạn mức của Cloud, nên app treo vĩnh viễn.

Bản chạy được trước đó (đến 16/10) là `vnstock==4.0.2` + `vnstock_ezchart==0.0.3` — ezchart 0.0.3
không ràng buộc NumPy nên pip lấy được NumPy 2.5.2 có wheel cp314, cài trong vài phút.

Đã thêm `--only-binary=numpy` vào `requirements.txt`: nếu ai deploy lại trên 3.14, pip báo lỗi
trong vài giây thay vì treo hàng chục phút.

## 2. Đang dở / đừng đụng

- **Việc còn lại là của chủ dự án**: xoá app trên Streamlit Cloud và deploy lại bằng Python 3.12
  (đúng các bước ở mục 4). Không có file nào trong repo ép được phiên bản Python.
- `venv/` (Python 3.14, bộ deps trước 16/10) chỉ còn giá trị tham chiếu. `.venv/` là 3.12, khớp CI.
- Chưa chốt có nên xin Streamlit nâng hạn mức tài nguyên hay không; chưa có dấu hiệu thiếu RAM.

## 3. Cái sắp cắn người sau

- Python của app **bị khoá tại thời điểm deploy**. Deploy bằng nút mặc định là đang cược vào
  phiên bản mới nhất của Cloud, không phải bản repo đã kiểm.
- `vnstock` đã bị gỡ khỏi PyPI; kho chính thức chỉ còn 4.0.8 và 4.0.9, **cả hai** đều kéo
  `vnstock_ezchart>=1.0.2` → `numpy<2.3`. Nghĩa là Python 3.14 sẽ hỏng lại ngay cả khi đổi pin.
- `requirements.txt` dùng `--extra-index-url` cho **mọi** gói, nên thời gian build phụ thuộc
  `vnstocks.com`. Nếu index này chậm, build chậm theo.
- `numpy>=2.2.6,<3` là ràng buộc của repo, không phải của vnstock. Đừng nới thành `>=2.3` khi
  ezchart vẫn còn chặn — hai dòng sẽ đá nhau và pip báo `ResolutionImpossible`.

## 4. Lệnh nghiệm thu

```powershell
# 1. Bộ test (632 test, ~8 phút trên máy này)
py -3.12 -m pytest -q --ignore=smoke_test.py

# 2. Kiểm tra bộ phụ thuộc cài được bằng wheel trên Python mục tiêu
py -3.12 -m pip install --dry-run --only-binary=:all: -r requirements.txt    # phải in "Would install"
py -3.14 -m pip install --dry-run --only-binary=:all: -r requirements.txt    # phải báo lỗi ngay (đúng như thiết kế)

# 3. App sống lại sau khi deploy
curl.exe -s https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app/_stcore/health   # "ok"
```

Deploy lại (chỉ chủ app làm được):

1. Mở https://share.streamlit.io, chọn workspace `congapro60-dev`.
2. Ghi lại **custom subdomain** hiện tại (`quant-app-nnqcr8uwb6mjyonxod8nzu`) để dùng lại.
3. Xoá app → **Deploy an app** → chọn repo `congapro60-dev/quant-app`, branch `master`,
   entrypoint `app.py`.
4. Mở **Advanced settings** → **Python version: 3.12** → Save → Deploy.
5. Điền lại subdomain cũ ở bước deploy để giữ nguyên đường link.
6. Sau khi app lên, chạy lệnh (3) ở trên.

## 5. File/khái niệm cốt lõi

- `requirements.txt` — nơi duy nhất quyết định bộ phụ thuộc; đọc cả phần chú thích cuối file.
- `app.py` — entrypoint Streamlit.
- `data_loader.py` — chỗ duy nhất gọi `vnstock` (`Quote`), import lazy trong hàm.
- `.github/workflows/qa.yml` — CI chạy Python 3.11 và 3.12; đây là căn cứ để chọn 3.12 cho Cloud.
- `tests/` — 632 test, không cần mạng.

## 6. Lịch sử

- 2026-07-24: commit đầu.
- 2026-08-03: `854387d` — né NumPy thiếu wheel cp314 bằng cách hạ `vnstock` xuống 4.0.2.
- 2026-10-16: `59ad66b`, `e9eac4e` — PyPI gỡ vnstock, chuyển sang kho chính thức; đổi sang
  4.0.9 + ezchart 1.0.2 và **vô tình đưa ràng buộc `numpy<2.3` trở lại** → app chết.
- 2026-10-23: thêm `--only-binary=numpy`, ghi lại chẩn đoán này.
