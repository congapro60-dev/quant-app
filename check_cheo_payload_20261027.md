# HANDOFF QA AUDIT — TÍNH NĂNG HS/GV TỰ ĐĂNG KÝ VÀ QUẢN LÝ THEO LỚP

## 1. Bối cảnh & Mục tiêu kiểm tra
Agent vừa triển khai tính năng tự đăng ký và quản lý theo lớp trên repo `quant-app` (`C:\Users\ADMIN\quant-app-link`), commit `a4d6028` và `91f2cc3`.
Nhiệm vụ của bạn (Codex / Senior Security & QA Reviewer độc lập): **Soi kỹ từng dòng mã, rules Firestore, bảo mật, tính toàn vẹn dữ liệu và hồi quy (regression)**. Báo cáo độc lập, khách quan, không nể nang.

## 2. Ràng buộc kiểm tra (Read-only)
- **KHÔNG** sửa mã nguồn, không commit, không push.
- **KHÔNG** gọi API làm thay đổi dữ liệu Firestore production nếu không được yêu cầu.

## 3. Các tệp đã thay đổi cần thẩm tra
- `classroom_self.py` (MỚI): Bộ validator, chuẩn hóa (username NFC/casefold, block 10/11/12, class_name regex `^[A-Z0-9]{1,16}$`, password >= 8), payload builders, `sort_roster`.
- `firebase_classroom.py`: Thêm `self_email`, `login_self`, `register_teacher`, `register_student`, `self_profile`, `list_teachers`, `join_teacher` (atomic commit), `leave_teacher`, `roster`, `remove_student`, `_delete_write`; sửa `_make_write` nhận `timestamp_field`.
- `firestore.rules`: 3 match block mới:
  - `teacher_directory/{uid}`: get/list signed; create signed && uid == request.auth.uid && keys hasOnly ['display_name', 'created_at'] && self_name && created_at == request.time.
  - `student_state/{uid}`: get signed && uid == auth.uid; list false; create/update signed && uid == auth.uid && keys hasOnly && self_name && block && class_name && teacher_uid exists in teacher_directory && updated_at == request.time.
  - `rosters/{tuid}/members/{suid}`: get tuid == auth.uid || suid == auth.uid; list tuid == auth.uid; create suid == auth.uid && tuid != suid && exists(teacher_directory/tuid); delete suid == auth.uid || tuid == auth.uid; update false.
- `classroom_self_ui.py` (MỚI): Giao diện tự đăng ký, đăng nhập riêng, khu HS (chọn/đổi/rút GV), khu GV (danh sách xếp lớp + xóa HS).
- `learning_ui.py`: Điểm mount `render_self_service()` trước `render_online_classroom` trong `_render_classroom_packages`.
- `tests/test_classroom_self.py` (MỚI): 17 unit tests.
- `tests/test_firebase_rules_emulator.py`: Test emulator tích hợp quy tắc Firestore.

## 4. Danh mục thẩm tra (Audit Checklist)

### A. An ninh & Phân quyền Firestore Rules
1. **Cô lập giữa các giáo viên**: GV A có thể đọc hoặc xóa danh sách học sinh của GV B không?
2. **Quyền hạn học sinh**: HS có thể ghi đè `student_state` của HS khác không? HS có thể tự tạo member doc trong roster của GV mà không qua kiểm tra tồn tại của GV không?
3. **Chống giả mạo**: HS có thể đặt `teacher_uid` bằng chính UID của mình để tự làm GV hướng dẫn cho chính mình không (`tuid != suid`)?
4. **Giới hạn trường (hasOnly)**: Có kẽ hở nào để client nhét thêm trường lạ (ví dụ PII, quyền admin, token) vào Firestore không?
5. **Kênh cũ**: Các rules của `classes/{c}`, `submissions/{receipt}`, `teachers/{uid}` có bị ảnh hưởng hay nới lỏng không?

### B. Tính toàn vẹn dữ liệu & Race Conditions
1. **Commit nguyên tử khi đổi GV**: Trong `join_teacher`, khi HS đổi từ GV 1 sang GV 2, thao tác (xóa ở roster cũ + tạo ở roster mới + update `student_state`) có nằm trong 1 commit duy nhất không? Nếu một phần fail thì Firestore xử lý thế nào?
2. **Dọn tài khoản mồ côi (Orphan Auth Cleanup)**: Trong `_register`, nếu tạo Auth user thành công nhưng ghi Firestore fail (do rules hoặc mạng), tài khoản vừa tạo có được xóa ngay bằng `_auth("delete")` không? Có rủi ro xóa nhầm tài khoản của user khác không?
3. **Xóa học sinh vs Trạng thái học sinh**: Khi GV xóa HS khỏi roster, con trỏ `teacher_uid` của HS chưa cập nhật ngay. UI học sinh xử lý trường hợp này thế nào khi render (bấm "Làm mới trạng thái" có bắt được 404 để cảnh báo không)?

### C. Chuẩn hóa & Xác thực dữ liệu (Input Validation)
1. **Tên đăng nhập**: Có chặn khoảng trắng ở giữa không? Có xử lý ký tự tổ hợp Unicode (NFC vs NFD) để tránh 2 tài khoản trùng tên hiển thị giống nhau không? Độ dài min/max có hợp lý không?
2. **Khối và Lớp**: Ràng buộc khối ∈ {'10', '11', '12'} và regex tên lớp `^[A-Z0-9]{1,16}$` có chặt chẽ và nhất quán giữa Python và Firestore rules không?
3. **Mật khẩu**: Kênh tự đăng ký dùng `validate_password` (8-128 ký tự). Có xung đột gì với kênh cũ của giáo viên cấp mã (mật khẩu >= 12 ký tự) không?

### D. Tương thích ngược & Rủi ro hồi quy (Regression)
1. Luồng cũ nộp bài trực tuyến qua `classroom_ui.py` có bị ảnh hưởng gì không?
2. Các bài test cũ trong `tests/test_firebase_classroom.py` và suite 914 tests có bị vỡ không?
3. UI mới có tuân thủ nguyên tắc không gọi mạng lúc render tự nhiên (chỉ gọi qua click nút / submit form) để không làm vỡ AppTest với api key giả không?

## 5. Lệnh thực thi để tự kiểm chứng
Chạy các lệnh sau trong thư mục repo:
```powershell
& "$HOME\.venv\Scripts\python.exe" -m py_compile classroom_self.py classroom_self_ui.py firebase_classroom.py learning_ui.py tests/test_classroom_self.py tests/test_firebase_rules_emulator.py
& "$HOME\.venv\Scripts\python.exe" -m pytest tests/test_classroom_self.py -v
& "$HOME\.venv\Scripts\python.exe" -m pytest -q
git diff HEAD~2 HEAD
```

## 6. Định dạng phản hồi yêu cầu
Trả lời rõ ràng từng mục:
- **Verdict từng mục**: `[PASS]` / `[FAIL]` / `[WARN]` kèm dẫn chứng file:dòng cụ thể.
- **Lỗ hổng / Bất cập tìm thấy** (nếu có): mô tả hiện tượng, mức độ nghiêm trọng (Cao / Trung bình / Thấp) và khuyến nghị sửa.
- **Kết luận chung**: Có đủ độ tin cậy để đưa vào sử dụng thực tế chưa?
