# HANDOFF — Quant App

**Cập nhật**: 2026-11-02 · **Repo**: https://github.com/congapro60-dev/quant-app · **Branch chuẩn**: `master` · **Production**: https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app

Luật làm việc trong repo: `AGENTS.md` (Reboot phải xin phép, deployed khác verified, nội dung pháp lý phải có nguồn).

## 1. Trạng thái hiện tại

App Streamlit dạy tài chính cho học sinh THPT và sinh viên; đích của dự án là học sinh đầu tư thật số vốn nhỏ qua MoMo dưới sự kiểm soát của gia đình. Đã có: lộ trình 11 bài THPT + 6 bài đại học, phòng học thống kê, danh mục mô phỏng, tab MoMo, tài khoản tự đăng ký Firebase, GV xem điểm.

Đợt 01–02/11/2026, sau QA tổng hợp hai phiên OpenCode và Codex:

- **Nút "Đi làm bài Đầu vào" đã sửa.** `st.rerun()` nằm trong `on_click` là no-op, nên nút chỉ rerun riêng dialog và đứng ở bước 4/4. Giờ xử lý trong thân dialog; đích đến đi qua `request_navigation` / `apply_pending_navigation`. Kiểm trên Edge qua Playwright (local), 2/2 lần.
- **Vốn ảo 0–500 triệu, mặc định 5 triệu, mua được lô lẻ.** Vốn 0 thì tắt nút khởi tạo vì `PortfolioLedger` từ chối 0; `portfolio.py` không đổi.
- **Mã mời giáo viên dùng một lần** chống giả danh, do Rules kiểm, không cần quyền quản trị. Tạo mã: `tools/teacher_invites.py`.
- **Test Rules chạy thật lần đầu**: `tools/run_rules_tests.py`.
- **Rules production đã deploy 02/11/2026**; smoke trên Firebase thật 7/7 (mã bịa bị chặn, dùng lại bị chặn, HS không đọc được mã), dữ liệu thử đã dọn. 3 mã mời đầu tiên nằm trong `~/.quant-app-classroom/teacher-invites-20261102-085158.json`.
- **Thẻ Hướng dẫn** (`user_guide.py`): các bước cho HS, GV, bản đồ chức năng sinh từ `FEATURES`, câu hỏi thường gặp. Đổi tên nút mà quên sửa hướng dẫn thì `tests/test_user_guide.py` đỏ.
- **Quên mật khẩu**: hướng dẫn ở form đăng nhập (`account_help.FORGOT_PASSWORD_STEPS`). Chủ dự án đã chọn KHÔNG đưa khoá quản trị lên app; không ai đặt lại được mật khẩu. Điểm nằm trong trình duyệt nên đăng ký lại trên cùng máy không mất.

- **Giao diện sáng/tối** (`theme_ui.py`, `[theme.light]`/`[theme.dark]` trong config): theo thiết bị, đổi ở menu ⋮ → Settings → Theme.
- **Trọng số âm** (bán khống) được nhận ở công cụ danh mục trong thẻ Ôn thi, cần cho đề có W âm. Trợ lý học tập `safe_ai_tools.py` vẫn từ chối W âm.

## 2. Đang dở / đừng đụng

- **Trạng thái production 02/11:** thẻ Hướng dẫn `verified`. Mục "Quên mật khẩu?" ở form đăng nhập mới `deployed`, chưa hiện vì `classroom_self_ui` cũ còn trong bộ nhớ; hết sau khi Reboot (phải xin phép) hoặc khi app ngủ rồi thức lại.
- `docs/thiet_ke_onboarding.html` chưa track, cố ý để đó.
- Luồng bấm nút nộp bài của HS tự đăng ký chưa chạy trọn trên trình duyệt; đã phủ bằng AppTest và smoke Firebase thật ngày 29/10.

## 3. Cái sắp cắn người sau

- **Java không đọc được đường dẫn tiếng Việt**: `firebase emulators:exec` chạy thẳng trong repo sẽ chết lúc khởi động. Luôn dùng `tools/run_rules_tests.py`.
- **`pytest` thường tự bỏ qua test Rules** (skip khi thiếu `FIRESTORE_EMULATOR_HOST`). Xanh không có nghĩa Rules đúng. Đổi `firestore.rules` thì phải chạy công cụ trên. Có một lần đỏ không rõ nguyên nhân trong 6 lần chạy ngày 01/11 (log bị ghi đè), chưa tái hiện được.
- **Streamlit Cloud kéo code mới mà KHÔNG khởi động lại tiến trình; module cũ vẫn trong bộ nhớ.** Module mới đọc hằng số vừa thêm vào module cũ ngay lúc import sẽ làm sập cả trang tới khi Reboot (đã xảy ra 02/11, `dce3183`, sửa bằng `4ec46c0`). Test local không bắt được vì luôn khởi động mới. Hằng số dùng lúc import thì đặt trong module mới.
- **Không gọi `st.rerun()` trong `on_click`**: Streamlit bỏ qua và test giả lập `st.rerun` vẫn xanh. Nút trong `st.dialog` cần rerun toàn app thì viết `if st.button(...)`. `test_tour_exit_buttons_are_not_callbacks` chặn việc này cho nút tour.
- **AI dùng chung bật mặc định, không giới hạn lượt, không cần đăng nhập** (`app.py`, `SHARED_PROVIDER_OPTION`). Chủ dự án chủ động chọn mở cho mọi người; tiêu hao hạn mức thì xem lại đây.
- **Tour đôi khi không hiện ở phiên đầu trên server vừa bật** (gặp 2 lần local khi máy tải nặng, tour thường hiện sau khoảng 30 giây). Chưa rõ nguyên nhân, không chặn việc dùng app.
- **App ngủ khi không có người vào**: màn hình "Zzzz" tiếng Anh, đánh thức khoảng 20 giây. Mở link 5–10 phút trước giờ học.
- **Python của app khoá lúc deploy trên Cloud** (phải là 3.12). `vnstock_ezchart>=1.0.2` chặn `numpy<2.3`, không có wheel cho 3.14. Đừng nới ràng buộc numpy.
- **Đường dẫn tiếng Việt**: dùng junction `C:\Users\ADMIN\quant-app-link` hoặc đường dẫn 8.3 khi thao tác file; PowerShell 5.1 và cmd đọc sai.
- **Thông tin MoMo/CVS chỉ đúng ở ngày đọc** (25/10/2026). Điều kiện 18 tuổi lấy từ blog chính chủ không ghi ngày; muốn chắc phải gọi CVS.

## 4. Lệnh nghiệm thu

```powershell
$env:PYTHONIOENCODING='utf-8'; cd C:\Users\ADMIN\quant-app-link
C:\Users\ADMIN\.venv\Scripts\python.exe -m pytest -q --ignore=smoke_test.py   # khoảng 14 phút
C:\Users\ADMIN\.venv\Scripts\python.exe tools\run_rules_tests.py              # 4 test Rules trên emulator
firebase.cmd deploy --only firestore:rules --project quant-app-classroom-20261026   # sau khi đổi Rules
curl.exe -s https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app/_stcore/health   # "ok"
```

Tạo mã mời giáo viên (mã ghi vào tệp riêng trong `~/.quant-app-classroom`, không in ra màn hình):

```powershell
C:\Users\ADMIN\.venv\Scripts\python.exe tools\teacher_invites.py create --count 3 --note "GV truong X"
```

## 5. File/khái niệm cốt lõi

- `app.py` — entrypoint; `workspace_ui.py` — điều hướng, tour; `learning_ui.py` — bài học, nhật ký.
- `curriculum.py`, `curriculum_university.py` — bài học; `stats_classroom.py` — phòng học thống kê.
- `investment_ui.py` + `portfolio.py` — danh mục mô phỏng; giá bảng là nghìn VND, ledger là VND.
- `firebase_classroom.py` + `firestore.rules` — REST bằng ID token, Rules là lớp bảo vệ duy nhất.
- `classroom_self*.py`, `account_ui.py` — tài khoản tự đăng ký, nút tài khoản góc phải.
- `momo_guide.py`, `provider_directory.py`, `readiness_gate.py` — nội dung pháp lý, phải có nguồn.

## 6. Lịch sử

Các phiên trước: xem `docs/HANDOFF-ARCHIVE.md` và `git log`.
