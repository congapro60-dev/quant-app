# Bàn giao: sửa nút tour + thiết kế bước 2 (Firebase)

Viết ngày 25/10/2026. Người nhận: Codex (hoặc agent khác tiếp nhận).
Người viết: phiên OpenCode trước. Mục đích: chuyển giao minh bạch, gồm cả phần
**chưa làm được** và lý do, để người sau không lặp lại đường cụt.

---

## PHẦN A — Việc đã làm, và việc còn treo

### A1. Trạng thái repo

- Repo: `github.com/congapro60-dev/quant-app`, nhánh `master`.
- Commit cuối: `647e1e7` (docs). Commit code cuối: `1480f6b`.
- Test: `pytest` **787 passed**.
- Python: `C:\Users\ADMIN\.venv\Scripts\python.exe`, đặt `PYTHONIOENCODING=utf-8`.
- Production: https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app

### A2. Đã sửa nhưng CHƯA VERIFY ĐƯỢC — đây là việc treo ưu tiên 1

**Triệu chứng người dùng báo:** nút **"Đi làm bài Đầu vào"** ở bước 4/4 của tour
mở đầu, bấm vào **không chạy tiếp**. Tái hiện được trên production: dialog vẫn ở
bước 4/4, tab vẫn ở Tổng quan.

**Hai lỗi đã tìm ra và đã sửa (commit `1480f6b`):**

1. **Cờ không lưu.** `workspace_ui._mark_tour_seen()` sửa dict tại chỗ:
   ```python
   state = st.session_state.get("progress_profile")
   state["seen_tour"] = True          # SAI: Streamlit không đánh dấu thay đổi
   ```
   Sửa thành tạo bản sao rồi gán lại key:
   ```python
   updated = dict(state); updated["seen_tour"] = True
   st.session_state["progress_profile"] = updated
   ```

2. **Đích đến không tồn tại.** `_finish_tour` gọi `navigate_to(lmode.AREA_JOURNAL)`
   không kèm feature. `navigate_to` chỉ tự chọn tab con cho `AREA_LEARNING`; khu
   Nhật ký thì không, nên rơi vào tab mặc định và không thấy form chẩn đoán.
   Sửa: thêm hằng `PROGRESS_TAB_LABEL = "Tiến độ và tiêu chí đánh giá (rubric)"`
   trong `workspace_ui.py`, truyền vào `navigate_to(...)`, và
   `learning_ui.render_journal_area` dùng cùng hằng để nhãn không lệch.

**Test đã thêm** (`tests/test_workspace_ui.py`):
- `test_first_tour_finish_marks_seen_and_navigates` — thêm assertion
  `session_state["tools_nhat_ky_tien_do"] == PROGRESS_TAB_LABEL`.
- `test_tour_finish_lands_on_the_tab_that_has_the_diagnostic_form` — sau khi bấm
  phải thấy chữ "Đầu vào (pre-test)" trong nội dung.
- `test_progress_tab_label_matches_the_real_tab_title`.

Đã kiểm chứng test bắt được lỗi: gỡ fix điều hướng → đúng 2 test đỏ; khôi phục → xanh.

**VÌ SAO CHƯA VERIFY ĐƯỢC TRÊN PRODUCTION:** công cụ browser của phiên trước
không bấm được **bất kỳ** nút nào trong `st.dialog`. Bằng chứng: nút **"Để sau"**
(vốn hoạt động từ trước, không liên quan fix này) cũng không phản ứng. Đã thử ba
cách, đều thất bại:

| Cách | Kết quả |
|---|---|
| `element.click()` | không ăn |
| Chuỗi `pointerdown → mousedown → pointerup → mouseup → click` | không ăn |
| `browser.click` với `ref` từ snapshot (`@e110010` = nút Close) | lỗi `UnknownVizError` |

Chẩn đoán: `st.dialog` chạy như **fragment** trong iframe; handler Streamlit không
nhận sự kiện tổng hợp. Đây là giới hạn công cụ, **không phải bằng chứng app đúng**.

**Quan sát thêm cần điều tra:** sau lần bấm đầu, hai nút "Đi làm bài Đầu vào" và
"← Trước" **biến mất** khỏi dialog, chỉ còn "Để sau". Nghĩa là sự kiện có tới được
app (handler đã chạy, đã rerun). Nhưng dialog dựng lại ở bước 4/4 và thiếu nút.
Có thể là **triệu chứng thứ ba** mà fix hiện tại chưa chạm tới.

**Việc cần làm cho người nhận:**
1. Mở production trên Chrome thật, xoá localStorage (để tour hiện lại).
2. Bấm hết 4 bước, bấm "Đi làm bài Đầu vào".
3. Ghi lại: dialog có đóng không? Có sang khu Nhật ký và thấy "Đầu vào (pre-test)" không?
4. Nếu vẫn kẹt: **đề xuất bỏ `st.dialog` cho bước cuối**, dùng trang thường thay
   vì fragment. Lý do: fragment là gốc của **ba lần lỗi liên tiếp** (`2cbe4e5`,
   `3a69dbc`, `1480f6b`). Đã vá ba lần quanh cùng một chỗ mà vẫn chưa đóng được.
   Bỏ fragment là cách cắt vòng lặp, không phải vá thêm.

### A3. Việc khác đã làm trong phiên (đã verify, không cần đụng)

Tab **"Chứng khoán trên MoMo"** trong khu Đầu tư — `momo_guide.py`, đã lên production
và đã đọc trực tiếp trên UI. Chi tiết ở `HANDOFF.md` mục `0y`, `0z2`–`0z6`. Tóm tắt
những gì **không được sửa ngược**:

- CVS yêu cầu **đủ 18 tuổi** mới mở tài khoản qua MoMo (nguồn: trang blog chính chủ
  momo.vn). Luật cho phép 15–17 nhưng **nhà cung cấp không nhận** — hai chuyện khác nhau.
- **Không được viết** "ứng dụng khoá chứng quyền trong mô phỏng": `readiness_gate.py`
  không có sản phẩm chứng quyền. Câu này từng là lỗi bịa, đã xoá.
- Ký quỹ (margin) **có** bị khoá với người dưới 18 (`PRODUCT_MARGIN` trong
  `MINOR_HARD_BLOCKED`) — câu trong tab phải khớp code này.
- Mỗi dòng phí phải ghi nguồn (trang sản phẩm vs trang blog) — hai trang khác nội dung.

### A4. Luật làm việc bắt buộc

Đọc `AGENTS.md` trước khi sửa. Ba luật quan trọng nhất:

1. **Reboot production phải xin phép trước.** `git push` chỉ là `deployed`, chưa
   phải `verified`. Streamlit Cloud **không tự rebuild**.
2. **Không khẳng định tính năng của app khi chưa đọc code.** Nếu nội dung nói
   "ứng dụng khoá/cho phép X" thì phải chỉ ra file + hằng số làm việc đó.
3. **Không `st.error`** ở lần mở đầu (`tests/test_app_smoke.py` cấm).

---

## PHẦN B — Ý tưởng bước 2: nộp bài cuối khoá cho giáo viên bằng Firebase

### B1. Yêu cầu gốc của người dùng

> "C dựng hẳn hệ thống" + "Firebase đi, ko cần đâu" (ý: không cần tuân thủ quy định
> nội bộ nào thêm).

Người dùng muốn: học sinh nộp bài, giáo viên đọc báo cáo cuối khoá — thay vì hiện
tại phải trao đổi file JSON thủ công.

### B2. Hiện trạng liên quan (đã đọc code, không phải phỏng đoán)

- **Không có máy chủ lưu dữ liệu.** Điểm nằm trong `localStorage` trình duyệt qua
  component `components/qa_progress_store` (`progress_store.py`).
- Đã có sẵn cơ chế gói lớp học: `classroom_packages.py` — giáo viên tạo gói giao bài
  `.json`, học sinh nạp rồi xuất kết quả. Nộp bài hiện vẫn qua file.
- **`classroom_packages.py` có bộ lọc PII nghiêm ngặt** (`_PII_MARKERS`), cấm cả:
  `ho_ten`, `full_name`, `email`, `phone`, `ngay_sinh`, `dob`, `school_id`,
  `student_name`, `teacher_name`, `cccd`, `address`… cùng `_SECRET_MARKERS` cho
  api_key/token và `_PRIVATE_FINANCE_MARKERS`.
- **App cố ý không hỏi họ tên hay ngày sinh** — `workspace_ui.py` ghi rõ: *"Ứng dụng
  không hỏi họ tên, ngày sinh hay giấy tờ."* Đây là quyết định thiết kế, không phải
  thiếu sót.
- Định danh duy nhất hiện có cho học sinh là **`student_code`** (tối đa 32 ký tự,
  học sinh tự đặt — xem `MAX_STUDENT_CODE_LEN`).

### B3. Vấn đề thiết kế phải giải trước khi viết code

**Đây là chỗ quan trọng nhất của file này.**

**B3.1. Không có định danh thì không nộp được bài.**
Hiện `student_code` là mã tự đặt, không kiểm chứng. Nếu nhiều học sinh cùng đặt
`hs01` thì dữ liệu đè lên nhau, giáo viên không biết ai là ai. Ba lựa chọn:

| Cách | Ưu | Nhược |
|---|---|---|
| Mã lớp + mã số do giáo viên phát | Không cần PII, khớp posture hiện tại | Giáo viên phải phát mã, phải có danh sách lớp |
| Email trường | Dễ đăng nhập, tự nhiên | **Vi phạm `_PII_MARKERS` hiện có**, phải sửa cả bộ lọc |
| Ẩn danh + mã nộp (receipt code) | Riêng tư nhất | Giáo viên không biết bài của ai, trừ khi học sinh đưa mã |

**Đề xuất:** mã lớp + mã số giáo viên phát. Giữ nguyên posture "không thu thập PII",
không phải nới lỏng `_PII_MARKERS`.

**B3.2. Firebase client SDK là công khai theo thiết kế.**
Khoá cấu hình Firebase (apiKey, projectId…) **không phải bí mật** — chúng nằm trong
app client và ai cũng đọc được. Nghĩa là: **bảo vệ dữ liệu hoàn toàn phụ thuộc
Firestore Security Rules**, không phụ thuộc việc giấu khoá.

Nếu rules viết sai, **mọi học sinh đọc được điểm của nhau**. Đây là rủi ro thật,
không phải lý thuyết.

Rules tối thiểu phải đảm bảo:
- Học sinh chỉ **ghi được** vào document của chính mình (theo mã lớp + mã số).
- Học sinh **không đọc được** bài của bạn khác.
- Giáo viên (một UID cụ thể hoặc custom claim) đọc được toàn bộ lớp mình.

Gợi ý dùng **Firebase Auth anonymous** cho học sinh (không cần email), rồi áp
rules theo UID — nhưng như vậy phải ánh xạ UID ↔ mã số ở đâu đó, và đó lại là
dữ liệu cần bảo vệ.

**B3.3. Vấn đề pháp lý — người dùng nói "không cần", nhưng phải ghi lại.**
Dữ liệu học sinh là dữ liệu cá nhân, và đa số là **người chưa thành niên**:

- Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân: cần có sự đồng ý, và với
  người chưa thành niên cần xem xét riêng.
- Firebase đặt máy chủ ngoài Việt Nam → việc chuyển dữ liệu ra nước ngoài cần
  đánh giá riêng theo nghị định này.

Người dùng đã nói không cần tuân thủ thêm. Người nhận **không nên tự quyết thay**,
nhưng phải ghi rõ trong code comment và trong UI rằng dữ liệu được gửi ra ngoài máy
học sinh, và hỏi lại một lần trước khi bật tính năng cho lớp thật.

**B3.4. Không được gửi gì lên Firebase ngoài mức cần thiết.**
Nguyên tắc: chỉ gửi **kết quả đã tổng hợp** (điểm bài, số lần chẩn đoán, nhật ký đã
khử định danh, mã lớp/mã số), **không** gửi danh mục mô phỏng, không gửi cấu hình,
không gửi API key. Giữ đúng tinh thần `_PRIVATE_FINANCE_MARKERS` đã có.

### B4. Kiến trúc đề xuất

```
Học sinh (trình duyệt)
  └─ localStorage: toàn bộ dữ liệu học tập (như hiện tại, KHÔNG đổi)
       └─ [nút "Nộp bài"] ──► dựng payload đã lọc PII
                                └─► Firestore (qua Firebase client SDK)

Giáo viên (trình duyệt)
  └─ đăng nhập Firebase Auth (email/Google — chỉ giáo viên)
       └─ đọc Firestore theo mã lớp
            └─ bảng tổng hợp + xuất CSV/JSON
```

**Vì sao giữ localStorage làm nguồn chính:** app đang chạy tốt, học sinh không mất
điểm khi mạng lỗi, và không phụ thuộc Firebase để học. Firebase chỉ là **kênh nộp**,
không phải nơi lưu duy nhất. Nếu Firebase chết, học sinh vẫn dùng app bình thường.

**Module mới đề xuất** (tách khỏi phần học, dễ revert):

```
classroom_submit.py        # dựng payload, lọc PII, gọi Firestore
  build_submission(profile, assignment, class_code, student_code) -> dict
  submit(submission) -> receipt
  # không import streamlit; thuần dữ liệu để test được

tests/test_classroom_submit.py
  - payload không chứa PII (dùng lại _PII_MARKERS của classroom_packages)
  - không chứa số dư/danh mục/API key
  - thiếu mã lớp/mã số thì từ chối
  - payload quá lớn thì từ chối (giữ giới hạn kiểu MAX_IMPORT_BYTES)
```

**UI:** thêm vào tab hiện có **"Gói lớp học"** trong khu Nhật ký, không tạo tab mới.
Giữ nguyên đường file JSON làm phương án dự phòng — **không xoá**.

### B5. Thứ tự làm đề xuất

1. **Chốt B3.1** (định danh bằng gì) — không có câu trả lời thì không viết code.
2. Viết `classroom_submit.py` + test, **chưa nối Firebase**. Test payload sạch PII.
3. Người dùng tạo Firebase project, gửi **tên project** (không gửi key vào chat/repo).
4. Viết Security Rules, **kiểm bằng Firebase Rules Playground** trước khi bật thật:
   thử một học sinh đọc bài học sinh khác → phải bị từ chối.
5. Nối UI nút "Nộp bài", mặc định **tắt** bằng feature flag trong secrets.
6. Bật thử với **một lớp nhỏ**, rồi mới mở rộng.

**Không bật mặc định** cho tới khi rules đã được kiểm bằng Rules Playground.

### B6. Câu hỏi chặn — phải trả lời trước khi code

1. **Định danh học sinh bằng gì?** Mã lớp + mã số giáo viên phát (đề xuất), email
   trường, hay ẩn danh + mã nộp?
2. **Ai được đọc dữ liệu?** Chỉ một giáo viên, hay nhiều giáo viên và mỗi người chỉ
   thấy lớp mình?
3. **Firebase project đã có chưa?** Tên project là gì (không đưa key)?
4. **Có sự đồng ý của phụ huynh cho việc gửi dữ liệu ra ngoài chưa?** Nếu chưa, nên
   bật chế độ chỉ tổng hợp điểm, không gửi nội dung nhật ký.

### B7. Điều người viết muốn nhắn người nhận

Người dùng ban đầu nói "có API key rồi thì tự tạo báo cáo cuối khoá gửi GV". Cần
phân biệt hai việc hoàn toàn khác nhau:

- **API key = gọi mô hình ngôn ngữ để viết chữ.** Không phải cơ chế vận chuyển dữ liệu.
- **Nộp bài = chuyển dữ liệu từ máy học sinh sang máy giáo viên.** Cần nơi lưu hoặc
  đường truyền, không cần AI.

Nếu dùng AI để "viết báo cáo cuối khoá" thì báo cáo đó là **văn bản do mô hình tạo**,
không phải dữ liệu thật, không truy vết được. Nếu muốn AI hỗ trợ, hướng an toàn là
**AI tóm tắt dữ liệu thật đã tổng hợp**, chạy sau khi giáo viên đã có số liệu — không
phải để AI thay dữ liệu.

Trong phiên trước, người viết đã ba lần vá cùng một lỗi fragment mà không đóng được.
Đề nghị người nhận: nếu lần verify tay thứ nhất vẫn kẹt, **đổi cách làm (bỏ dialog)**,
đừng vá lần thứ tư.
