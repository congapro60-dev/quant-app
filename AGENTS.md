# Luật làm việc trong repo này

## Production là của người dùng thật

App đang chạy tại https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app và có
người dùng thật (học sinh, giáo viên) bất kỳ lúc nào.

### Reboot / khởi động lại — PHẢI hỏi trước

Streamlit Community Cloud **không tự rebuild sau `git push`** (dù trang chủ họ ghi
ngược lại). Muốn bản mới lên production thì phải vào `share.streamlit.io` → menu
⋮ của app → **Reboot**, và thao tác này hiện hộp thoại *"This will disrupt all
current users."*

Trước khi bấm, phải:

1. **Xin phép người dùng** và nói rõ sẽ ngắt phiên người đang dùng. Chỉ bấm khi
   đã được đồng ý cho lần đó — đồng ý một lần không áp dụng cho lần sau.
2. Nếu được bảo "chờ giờ vắng" thì chờ, không tự quyết là đêm khuya.
3. Ghi lại thời điểm Reboot trong `HANDOFF.md`.

Ngoại lệ duy nhất: chưa ai dùng app (mới triển khai lần đầu, hoặc người dùng đã
xác nhận không có ai đang dùng).

### Deploy chỉ là `deployed`, chưa phải `verified`

- `git push` xong ⇒ trạng thái `deployed`.
- Reboot xong và **đọc được nội dung mới trên UI production** ⇒ mới là `verified`.
- Ghi đúng trạng thái vào `HANDOFF.md`. Không gọi là `verified` khi mới `deployed`.

## Nội dung pháp lý: không được khẳng định suông

- Mỗi con số, mỗi điều kiện phải chỉ ra được **nó nằm ở trang nào** (trang sản
  phẩm khác trang blog khác trang hỏi đáp — thiếu một trang là kết luận sai).
- **Không được suy ra** từ việc một trang thiếu thông tin rằng cả website không có.
  Muốn viết "không nêu X" thì phải kiểm hết các trang chính chủ liên quan.
- Không được khẳng định một tính năng của ứng dụng khi chưa đọc code. Nếu câu
  trong nội dung nói "ứng dụng khoá/cho phép X" thì phải chỉ ra được file và hằng
  số làm việc đó, và nên có test đối chiếu với code.
- Không có nguồn thì viết **"chưa xác minh"** hoặc **"KHÔNG TÌM THẤY"**, không viết
  "có lẽ", "thường thì", "theo hiểu biết chung" rồi để trong tab.

## Hộp đỏ

`tests/test_app_smoke.py` cấm mọi `st.error` ở lần mở đầu — học sinh thấy khung đỏ
sẽ tưởng ứng dụng hỏng. Dùng `st.warning` cho cảnh báo, kể cả cảnh báo nặng.

## Test

- Chạy `pytest` sạch trước khi commit. Python: `C:\Users\ADMIN\.venv\Scripts\python.exe`,
  đặt `PYTHONIOENCODING=utf-8`.
- Test chống tái phát: khi sửa một câu sai, nên **chèn lại câu sai** để xác nhận
  test đỏ, rồi khôi phục. Test không đỏ được với lỗi cũ là test vô dụng.
- Không sửa dữ liệu cho vừa test; sửa test theo dữ liệu thật.

## Commit

- Commit message **không dấu**.
- Mỗi mục một commit, revert được độc lập.
- Không commit API key, token, hay dữ liệu học sinh.
- Không `reset --hard`, `clean`, hay force-push.

## Kiểm UI production bằng browser

- Snapshot không vào được iframe Streamlit → dùng `browser.frames` lấy frame id.
- `element.click()` bị React bỏ qua → bắn đủ `pointerdown → mousedown → pointerup
  → mouseup → click`.
- **Nút trong `st.dialog` bấm được bằng `element.click()`** — nhưng fragment rerun
  CHẬM (15–20 giây). Bấm xong phải đợi đủ lâu rồi mới đọc trạng thái; kiểm sau
  3–8 giây sẽ tưởng nút "không ăn" (bài học thật 26/10/2026, sửa lại kết luận sai
  của 25/10: từng kết luận "công cụ không bấm được nút dialog" — SAI, chỉ là chậm).
- Viewport tool hẹp → Streamlit rơi vào chế độ di động: sidebar KHÔNG nằm trong
  DOM cho tới khi bấm "Main menu" ở header; click đó chưa ăn được bằng tool. Đừng
  kết luận "app mất sidebar" — máy người dùng vẫn có (xem ảnh 0z7 trong HANDOFF).
- Tab con báo `aria-selected="true"` **dù tab cha chưa mở** (phần tử cao 0px).
  Mở tab cha trước, kiểm `width > 0`, rồi mới bấm tab con.
- Có thể có `stMarkdown` đè lên thanh tab → `elementFromPoint` trả về markdown và
  cú bấm mất. Bắn sự kiện **trực tiếp lên element tab**, không qua `elementFromPoint`.
- Bảng `st.dataframe` vẽ bằng **canvas** nên `innerText` luôn rỗng. Đừng kết luận
  "bảng trống" — đếm `[data-testid="stDataFrame"]` có width > 0.
- Bấm radio trong tab làm app rerun về Tổng quan; phải mở lại tab sau đó.
- Giữ 1–2 tab, mở nhiều tab làm browser treo.
