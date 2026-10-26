# Nộp bài Firebase thật — 26/10/2026

Status: deployed; teacher + student browser flows verified on production (student E2E done 26/10, see HANDOFF 0z12).
User: “Làm thật cho xong”, sau bốn câu đã trả lời.
Repo: master, d5fbccf. Không dùng Astra. Không sửa bộ máy tài chính hoặc tour.

## Thiết kế đã rà soát

- Project riêng `quant-app-classroom-20261026`, Firestore Standard; không billing.
- Firebase Auth email/password bằng định danh tổng hợp, không email HS thật:
  `{role}-{sha256(role:class_code:student_code)}@quant-app.invalid`; mật khẩu ngẫu nhiên GV phát.
  Giáo viên cũng dùng mã/tài khoản tổng hợp do chủ project cấp. Không có nút
  tự nâng quyền giáo viên; `/teachers/{uid}` chỉ chủ project ghi.
- Python stdlib REST gọi bằng ID token người đăng nhập; không dùng admin key
  trong Streamlit. Firestore Rules áp dụng cho mọi đọc/ghi của ứng dụng.
- `/classes/{code}` owner_uid bất biến; GV chỉ query lớp owner_uid bằng UID mình.
- `/classes/{code}/students/{studentCode}` gắn UID do GV tạo, HS chỉ đọc bản thân.
- `/classes/{code}/submissions/{sha256(assignmentId:studentCode)}` ghi lại payload đã
  allowlist, owner_uid, thời điểm server. HS chỉ tạo/cập nhật bài chính mình;
  GV sở hữu lớp đọc danh sách. Không cho HS tự ghi member/role hoặc sửa owner.
- Điều chỉnh sau kiểm thử giới hạn Rules: điểm từng mô-đun nằm trong
  `submissions/{receipt}/lessons/{index}`; header và toàn bộ điểm ghi trong MỘT
  commit nguyên tử. Mỗi document được kiểm schema riêng, tránh trần 1.000 biểu
  thức khi kiểm một mảng dài. Giới hạn giữ đúng `classroom_packages.MAX_LESSONS`
  (200); UI/JSON vẫn dùng cùng cấu trúc summary, transport tự ghép lại.
- Không gửi văn bản nhật ký, danh mục, khóa AI hoặc PII. Chỉ tóm tắt có sẵn.
- Auth sống trong session Streamlit; khi đổi máy HS đăng nhập lại bằng mã GV phát.
  Không thay localStorage học tập; Firebase lỗi vẫn xuất JSON được.
- Tính năng mặc định tắt nếu thiếu Secrets `[classroom_firebase] enabled=true`.
  Thêm UI trong Gói lớp học, không thêm tab. Thông báo dữ liệu ra ngoài máy.

## Thứ tự / cổng kiểm tra

1. Cài hạ tầng Auth/Firestore kín trên project riêng, tạo tài khoản GV chủ app.
2. REST transport + xác thực + giao diện GV tạo lớp/phát mã/đọc bài, HS nộp bài.
3. Firestore Rules; Emulator test: HS A đọc/ghi B bị chặn, GV ngoài lớp bị chặn,
   nâng role và đổi owner bị chặn; học sinh không đăng nhập bị chặn.
4. Deploy Rules vào project mới, kiểm Rules Playground theo yêu cầu người dùng;
   live canary chỉ dữ liệu giả. Chưa bật production trước khi cổng này đạt.
5. Full pytest + compile + diff/secret scan; commit theo mục, push. Ghi bằng chứng.
6. Cấu hình Cloud qua phần Secrets, không in khóa lên chat/repo. Reboot app đang
   có người dùng cần xác nhận riêng trước lần reboot đó theo AGENTS.md.

## Bằng chứng 26/10/2026

- Project Spark, không liên kết billing; Firestore Standard `asia-southeast1`.
- Live canary 12:48 UTC: gửi/đọc bài giả thành công, học sinh B đọc/ghi bài A bị
  từ chối, giáo viên ngoài lớp bị từ chối. Bằng chứng riêng ngoài repo:
  `C:\Users\ADMIN\.quant-app-classroom\live-canary.json`.
- Rules Playground trên Console: GET cùng bài của HS A, UID B nhận
  `Simulated read denied`; đổi sang UID A nhận `Simulated read allowed`.
- Full pytest cuối: 888 passed, 1 skipped (149,70 giây); emulator chạy riêng.
- Emulator: toàn bộ 200 mô-đun có điểm, phân trang, refresh token, gửi lặp,
  dữ liệu sai, truy cập chéo học sinh/GV, nâng role đều kiểm đạt.
- Live canary schema mới 13:11 UTC: ghi/đọc bài, refresh token, chặn đọc/ghi
  chéo đạt. Rules mới deploy thành công; Playground bản mới tiếp tục từ chối B.
- Phát hiện bằng kiểm tra đủ 20 mô-đun: Rules vượt trần 1000 biểu thức. Các lần
  tối giản biểu thức không giải quyết đủ; thay bằng bản ghi con từng mô-đun.
  Không giữ phương án hạ trần 12 mô-đun; kiểm lại toàn bộ 200 mô-đun có điểm.
- Secrets Cloud đã lưu, giữ nguyên cấu hình AI cũ. Người dùng đã duyệt reboot
  ngay trong lượt này. Chưa verified UI production trước kiểm giao diện mới.
- Reboot 20:17:55 giờ Việt Nam. Sau đó browser production đã hiện UI mới, đăng
  nhập GV-QA01, chọn lớp QA-E31FF0DA, đọc bài HS-QA01 đạt 80 điểm, có CSV/JSON.
  Đã đăng xuất. HS nạp JSON rồi bấm nộp chưa kiểm xuyên suốt bằng browser;
  đã có AppTest bước consent/receipt và REST thật. Không đánh đồng các lớp bằng chứng.

## Dùng thử một lớp nhỏ

1. Mở Nhật ký và tiến độ → Gói lớp học → chọn Giáo viên, đăng nhập GV-001 bằng
   tệp riêng; mã lớp để trống khi đăng nhập GV.
2. Tạo mã lớp, cấp tài khoản HS, tải và phát riêng tệp tài khoản từng em.
3. Tạo gói giao bài JSON ở ngay bên dưới, gửi cho HS (không gửi tệp tài khoản
   của em này cho em khác).
4. HS nạp gói, học như cũ, đăng nhập kênh nộp bài bằng mã lớp/mã HS/mật khẩu,
   xem dữ liệu sẽ gửi, đồng ý rồi nộp. Giữ biên nhận hoặc JSON dự phòng.
5. GV chọn lớp → Tải danh sách bài nộp → đọc bài / xuất CSV hoặc JSON.

Mã GV đầu tiên `GV-001`; mật khẩu chỉ trong tệp riêng
`C:\Users\ADMIN\.quant-app-classroom\teacher-GV-001.json`. Không commit tệp này.
Giáo viên mới được chủ project cấp qua `tools/provision_classroom.py`.

Không khẳng định điểm cục bộ đã được server/giáo viên xác minh. Không dùng AI
để chuyển dữ liệu. Không bật lớp thật trước thử một lớp nhỏ.
