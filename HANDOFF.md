# HANDOFF — Quant App

**Cập nhật**: 2026-10-27 · **Repo**: https://github.com/congapro60-dev/quant-app · **Branch chuẩn**: `master` · **Production**: https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app

## 0z15. 28/10/2026 — Nút tài khoản góc phải trên + trang HS/GV riêng + nhớ đăng nhập

- Vấn đề: khối "Tài khoản tự đăng ký" nằm lẫn trong tab **Nhật ký và tiến độ →
  Gói lớp học** nên bị ẩn, không thấy ai đang đăng nhập.
- Nút tài khoản: `account_ui.render_account_bar()` — `st.container(key="qa_account_bar")`
  ghim `position: fixed; top: 3.4rem; right: 1rem; z-index: 999980` (dưới thanh
  công cụ Streamlit, dưới lớp hộp thoại để tour/dialog vẫn che đúng thứ tự; màn
  ≤900px trả về dòng thường). Nhãn hiện người đang đăng nhập: `👤 Khách` /
  `👤 Cô Hồng · GV` / `👤 Nguyễn An · HS`. Bấm ra popover theo vai trò: khách →
  form đăng nhập + đăng ký; học sinh → **Trang học sinh**; giáo viên →
  **Trang giáo viên**; luôn có **Đăng xuất**.
- Trang riêng: `account_ui.render_account_page()` gọi trong `app.py` trước hero;
  có yêu cầu trang thì vẽ trang tài khoản rồi `st.stop()` (không dựng tab).
  Điều hướng bằng `st.query_params["account"]` = `student|teacher|login|register`
  + `st.session_state["_account_page"]`; có nút "← Quay lại ứng dụng".
- Nhớ đăng nhập (kiểu Gmail, có kiểm soát): `account_store.py` +
  `components/qa_account_store/index.html` — cầu nối localStorage key
  `quantapp.account.v1` (cùng khuôn `qa_progress_store`, không thêm gói pip).
  Lưu `username, uid, kind, display_name, refresh_token, saved_at`; đọc lại thì
  `session_from_refresh` đổi refresh token lấy phiên mới. Hạn 30 ngày
  (`MAX_AGE_DAYS`), `sanitize` từ chối mọi dấu sai khoá/kiểu/độ dài. Refresh
  token được Firebase luân chuyển nên `FirebaseClassroom(on_refresh=...)` ghi
  lại sau mỗi lần làm mới. Nút **Đăng xuất** xoá dấu; **Quên tài khoản trên máy
  này** chỉ xoá dấu, giữ phiên. Lỗi mạng khi khôi phục thì **giữ** dấu để thử lại.
- Bỏ `render_self_service()` khỏi `learning_ui._render_classroom_packages` (một
  cửa duy nhất); các hàm panel tách công khai
  (`classroom_self_ui.entry/student_panel/teacher_panel`) để `account_ui` bọc lại,
  không viết lại giao diện. Móc `on_login(session, profile, username)` để lưu dấu.
- Bài học khi test: nút tài khoản và trang tài khoản **cùng hiện một màn hình**,
  nên mọi khoá widget phải tách phạm vi (`account_bar_*` vs `account_page_*`) —
  trùng khoá là `StreamlitDuplicateElementKey` và trắng trang. Khách đang mở trang
  tài khoản thì nút chỉ hiện lối đi, không vẽ lại form (tránh trùng khoá).
- Test: `tests/test_account_store.py` (7 test dấu/hạn dùng) +
  `tests/test_account_ui.py` (16 test: nút khoá theo vai trò, đăng xuất, ghi dấu
  khi đăng nhập, khôi phục/hết hạn/lỗi mạng, 4 trang riêng, chống trùng khoá,
  app.py boot, và chốt "tab Gói lớp học không còn mount khối cũ").
  Full pytest **954 passed, 2 skipped**.
- Chưa verify browser production trong bản này (cần Reboot, xin phép riêng):
  việc cần nhìn tận mắt là vị trí nút ở góc phải trên và luồng nhớ đăng nhập
  (đăng nhập → F5/mở tab mới → vẫn còn tên tài khoản).

## 0z14. 27/10/2026 — HS/GV tự đăng ký tài khoản + chọn GV hướng dẫn

- Feature mới cạnh kênh "mã cấp sẵn" (giữ nguyên 100%): HS tự đăng ký
  (tên đăng nhập 4-32 không khoảng trắng, casefold+NFC; tên hiển thị; khối
  10/11/12 + tên lớp chuẩn `^[A-Z0-9]{1,16}$`; mật khẩu ≥8 — riêng kênh nộp
  bài cũ vẫn ≥12) và chọn GV từ danh bạ. GV tự đăng ký, tên hiện ngay trong
  dropdown chọn GV của HS. HS đổi/rút GV linh động; GV xóa HS khỏi danh sách
  của mình (chỉ xóa, không sửa); sắp xếp danh sách theo khối→lớp→tên. 1 người
  mở nhiều tài khoản bình thường. Không email/SĐT; quên mật khẩu giai đoạn 1
  = đăng ký tài khoản mới, GV xóa bản cũ.
- Kiến trúc: `classroom_self.py` (validators thuần + `sort_roster`),
  `firebase_classroom.py` thêm `self_email` (synthetic
  `self-{sha256(username)}@quant-app.invalid`), `login_self`,
  `_register` (signUp + viết hồ sơ, hủy tài khoản mồ côi nếu viết hỏng),
  `register_teacher/register_student`, `self_profile` (student_state →
  teacher_directory → none), `list_teachers`, `join_teacher` (1 commit: xóa
  member cũ + tạo member mới + cập nhật con trỏ), `leave_teacher`, `roster`,
  `remove_student`, `_delete_write`; `_make_write` tổng quát hóa
  `timestamp_field`. Firestore mới: `teacher_directory/{uid}` (mọi signed user
  đọc), `student_state/{uid}` (chỉ chủ sở hữu get/update; teacher_uid phải
  trỏ tới directory có thật), `rosters/{tuid}/members/{suid}` (HS create/delete
  doc của mình, GV list/delete; update false; tuid != suid).
- UI: `classroom_self_ui.py` — `render_self_service(config=None)` gọi trước
  `render_online_classroom` trong `_render_classroom_packages`
  (learning_ui.py ~891). Tách module để không vỡ AppTest cũ; mọi fetch mạng
  đều sau nút/form (render tự nhiên không gọi mạng — AppTest với key giả vẫn
  xanh). Disabled → caption, không widget.
- Test: `tests/test_classroom_self.py` 17 unit (validators, commit nguyên tử,
  hủy tài khoản mồ côi, parse uid bằng `rsplit`, AppTest: entry 9 text_input,
  panel HS/GV không mạng lúc render, luồng join/remove/đăng ký qua form).
  Emulator: `test_rules_self_service_registration_roster_and_denials` —
  đăng ký, trùng username bị chặn, join/leave/đổi GV, xóa HS, chặn chéo GV,
  chặn khối/lớp sai schema, chặn tự-làm-GV-của-chính-mình. Full pytest
  **931 passed, 2 skipped** (2:03 phút).
- Bài học mock: `document_data` cần `fields` dạng {trường: wrapper} — mock
  sai kiểu `fc._value(dict)` làm `document_data` trả {} (test bắt được).
- Phản biện độc lập từ Codex QA (27/10) và khắc phục toàn diện:
  1. Rules `student_state/{uid}`: bổ sung `teacher != uid` chặn HS tự làm GV của chính mình.
  2. Bắt lỗi mạng chuẩn: tách `ClassroomNotFoundError` (404); không nuốt lỗi mạng/500
     thành "tài khoản không tồn tại" hoặc "GV đã xóa".
  3. Dọn Auth an toàn: chỉ dọn khi có mã từ chối chắc chắn (400, 403, 409) từ máy chủ.
  4. Validator: chặn ký tự tàng hình (Zero-width space `\u200b`, control chars) trong username;
     đối chiếu số khối khớp với tiền tố tên lớp ("khối 10 nhưng lớp 11A1" bị từ chối).
  5. UI: hiển thị tiền tố mã UID giáo viên (`Cô ... (mã: abcd1234)`) để học sinh dễ đối chiếu
     với mã GV cấp thật, tránh chọn nhầm tài khoản GV mạo danh; thêm thông báo bảo mật PII.
  6. Sửa test emulator: sửa lệnh xóa chéo gửi đúng path `rosters/{t2}/members/{s2}` của GV khác.
- Verify production `a4d6028` đã hoàn tất 100% trên browser thật sau Reboot
  (user cho phép):
  1. Backend Firestore Rules đã deploy lên Firebase thật (`quant-app-classroom-20261026`),
     smoke test 8 bước đạt 100%.
  2. Browser E2E: đăng ký GV `gv-brw-x8601` ("Cô Giáo X8601") → đăng xuất → đăng ký
     HS `hs-brw-x8601` ("Nguyễn Hoàng An", khối 10, lớp 11A1) → HS mở dropdown thấy
     tên GV "Cô Giáo X8601" → bấm "Vào danh sách của giáo viên này" thành công.
  3. GV đăng nhập lại → "Tải danh sách học sinh" hiển thị đúng dòng "Nguyễn Hoàng An —
     khối 10 lớp 11A1" → bấm "Xóa khỏi danh sách" thành công.
  4. HS đăng nhập lại → bấm "Làm mới trạng thái" thấy đúng cảnh báo "Giáo viên đã
     xóa em khỏi danh sách... Chọn lại giáo viên bên dưới nhé." + nút chọn lại GV.
  5. Dọn dẹp sạch: đã xóa 2 tài khoản Auth thử nghiệm, dọn localStorage seed.

## 0z13. 27/10/2026 — công thức SGK LaTeX + hướng dẫn bấm máy Casio cho Phòng học thống kê

- Feature: `684934a` (Phòng học thống kê 3 phòng Toán 10/11/12) + `9dc0492`
  (LaTeX + Casio). `StepSpec` thêm `latex_note` (caption dưới `st.latex`) và
  `casio` (expander "Bấm máy Casio fx-580VN X / fx-880BTG"); 14/14 bước có
  đủ latex bám SGK + note + casio; 2 test khóa mới. Full pytest **914 passed,
  1 skipped** (2,5 phút).
- Quy ước latex trong repo: số thập phân `{,}` (`1{,}5`), chữ Việt trong
  `\text{}`, `\%` escape, chuỗi latex là raw-string KHÔNG f-string; inline
  `$...$` chỉ dùng trong chuỗi hint/question thuần (st.markdown tự render).
- Casio xác thực từ PDF manual chính thức (fx-580VNX_VI.pdf, fx-880BTG_VI.pdf):
  fx-580VN X đọc kết quả `OPTN` → `1-Variable Calc`; fx-880BTG `TOOLS` →
  `1-Var Results`, bật tần số `TOOLS` → `Frequency` → `On` (fx-580VN X:
  `SHIFT` → `MENU` (SETUP) → `Statistics` → `On`). Bảng ký hiệu SGK ↔ máy:
  x̄=`x̄`; s² (chia n)=`σ²x`; s′² (chia n−1)=`s²x`; Me=`Med`; Q₁/Q₃=`Q1`/`Q3`;
  Mo=không có; x_max/minX=`maxX`/`minX`.
- Ký hiệu thống nhất theo SGK phổ thông: SGK không dùng chỉ số "g" — trung
  bình/phương sai/độ lệch chuẩn/khoảng biến thiên/tứ phân vị của mẫu ghép nhóm
  viết x̄, s², s, R, ΔQ, Q₁/Q₃ (phân biệt bằng lời "của mẫu ghép nhóm"). Đã
  sửa cả stats_classroom, stats_tools (công thức + metric "Meg/Mog/sg"),
  curriculum, learning_ui, feature_guides; các câu so sánh diễn đạt lại thành
  "x̄ ghép nhóm" vs "x̄ dãy thô".
- Hai cảnh báo dạy đúng SGK: (1) máy chia `σ²x` cho n (khớp SGK Toán 10),
  dòng `s²x` chia n−1 là phương sai hiệu chỉnh Toán 12 — đừng nhầm;
  (2) mẫu ghép nhóm máy chỉ tính được x̄, s từ trung điểm + tần số; `Med`/
  `Q1`/`Q3` trên màn hình khi có Freq là số từ dãy trung điểm lặp, KHÔNG phải
  nội suy theo biên nhóm — bước Me/Mo/Q làm tay; quy tắc tứ phân vị nội suy
  của Casio không công bố trong tài liệu → số máy chỉ tham khảo.
- Verify production `9dc0492` đã live: phòng 10 `.katex`=7, bảng ký hiệu bước 1
  đủ; phòng 11 `.katex`=9, Me/Q₁Q₃/s² gathered + cảnh báo "không nội suy";
  phòng 12 `.katex`=5, bước 4 latex quy đổi tiền. Seed localStorage đã dọn
  (removeItem `quantapp.progress.v1`).
- Verify production `50216cc` (4 chỗ câu chữ theo QA Codex) đã live sau Reboot
  lần 2 (user cho phép; dashboard tab browser tích hợp vẫn đăng nhập sau restart
  server). Phòng 11, bước 5, bấm "Đối chiếu" + mở 5 expander "Công thức bám SGK":
  render nguyên văn "Chốt: độ lệch chuẩn s của mẫu B lớn hơn của mẫu A — cùng
  trung bình, B rủi ro hơn." và "…s² có đơn vị là bình phương đơn vị dữ liệu
  (bị bình phương); s giữ lại đúng đơn vị của dữ liệu."; không còn "mất đơn vị %";
  `.katex`=9; token cũ x̄g/s_g/s²g/R_g = 0. Seed đã dọn. Lưu ý: 2 câu còn lại
  (learning_ui phân tán, curriculum s4_q4) là chuỗi tĩnh trong phần không chạm
  được trên production — đã qua compile + pytest, không spot-check riêng.
- Sau server restart: chrome-devtools MCP mất rồi quay lại nhưng `list_pages`
  chỉ còn about:blank (profile cũ mất); app public nên điều hướng thẳng URL là
  verify được, không cần login. Browser tích hợp thì báo "No desktop browser is
  connected" — cần user mở desktop app để nối lại.
- Verify production `0d4f8fa` (ký hiệu SGK) đã live sau khi Reboot qua dashboard
  share.streamlit.io (auto-deploy kẹt 40+ phút; đăng nhập Google do user thực
  hiện trên browser tích hợp). Phòng 10 `.katex`=7; phòng 11 `.katex`=9 + câu
  Casio mới "máy chỉ tính được x̄ và s"; phòng 12 `.katex`=5; đếm token
  x̄g/s_g/s²g = 0 cả 3 phòng (lưu ý false positive: bảng ký hiệu dồn text thành
  "x̄x̄giống nhau" — chữ g là đầu từ "giống", không phải ký hiệu cũ). Công cụ
  "Máy tính số đặc trưng": Me/Mo/s²/s/Q1/Q3 sạch; "Phòng thí nghiệm ghép nhóm"
  đủ metric mới x̄/Me nội suy/Mo/s/R/ΔQ. Seed đã dọn.
- Kỹ thuật selectbox Streamlit Cloud mới (react-aria ComboBox): synthetic
  dispatchEvent không ăn — phải dùng chrome-devtools `take_snapshot` lấy uid nút
  "Open" cạnh combobox, `click` native, rồi `press_key` ArrowDown/ArrowUp +
  Enter (list ảo chỉ render khi có sự kiện thật). Sau đổi Lớp/phòng, app reset
  tab về Tổng quan → điều hướng lại. Enter khi focus nhầm vào combobox "Lớp:"
  sẽ đổi lộ trình — kiểm `aria-label` trước khi bấm phím.
- Kỹ thuật browser mới (dùng lại được): browser tích hợp lỗi
  `ERR_TUNNEL_CONNECTION_FAILED` → dùng chrome-devtools; nếu kêu
  "browser is already running" thì kill các tiến trình chrome.exe có
  CommandLine chứa `chrome-devtools-mcp` rồi `list_pages` lại (cookie phiên
  đăng nhập share.streamlit.io còn trên đĩa profile). App nằm trong iframe
  `title="streamlitApp"` — mọi thao tác qua `f.contentDocument`; nav chính là
  `st.tabs` key `workspace_tabs` (tab = `div[data-testid="stTab"]`), tab con
  "Phòng học thống kê" tương tự; selectbox mở bằng click con trực tiếp của
  `div[data-baseweb="select"]`, option là `li[role="option"]`; Code Mode
  runtime không có setTimeout — dùng `new Promise(res => setTimeout(...))`
  trong `evaluate_script`; chi tiết tool là `evaluate_script` (không phải
  `evaluate`), tra catalog bằng `search()` trước khi gọi.
- Kỹ thuật đọc manual Casio (tái sử dụng): `Invoke-WebRequest` tải PDF chính
  thức của Casio → pypdf (đã cài trong `~/.venv`) extract text từng trang →
  grep "phân vị/Freq/1-Var". File text tạm: `$TEMP\opencode\fx580_stat.txt`,
  `fx880_stat.txt` (có thể xóa).

## 0z12. 26/10/2026 — verify browser E2E luồng học sinh trên production (phần Codex bỏ ngỏ)

- Hoàn tất mục "Student browser end-to-end pending" trong
  `docs/firebase-classroom-plan.md`. Kiểm trọn luồng trên production bằng
  browser tích hợp, 1 lớp QA nhỏ: lớp `LOP-QA-BROWSER` do GV-001 tạo, cấp
  `HS-CB581D2958A0`, gói `bai-01` (1 mô-đun `m1_tien_ngan_sach`, track thpt).
- Luồng HS đạt từng bước: upload JSON gói giao bài → "Gói hợp lệ. Làm các
  mô-đun được giao trong Lộ trình học." → đăng nhập kênh nộp (radio Học sinh,
  mã lớp + mã HS + mật khẩu) → "Xem dữ liệu sẽ gửi" hiển thị đúng payload
  (mã lớp/HS/bài giao, điểm NULL, 0 lượt làm, journal_count 0; không PII) →
  tick đồng ý → "Nộp bài lên Firebase" → biên nhận `Đã lưu bài ·
  2026-10-26T14:11:49.704836Z` + `receipt_id 31524be5…7829`.
- Luồng GV đọc lại đạt: đăng nhập lại GV-001 → chọn lớp → "Tải danh sách bài
  nộp" → CSV `tong_hop_LOP-QA-BROWSER.csv` đúng dòng
  `HS-CB581D2958A0,bai-01,1,2026-10-26T14:11:49.647Z` (khớp biên nhận) → JSON
  `bai_nop_LOP-QA-BROWSER.json` đủ `owner_uid` (UID HS, khác UID GV) và
  summary khớp 100% với dữ liệu HS đã xem trước khi đồng ý.
- Xác nhận lại với chủ project: HS không đăng nhập vẫn dùng được toàn bộ web;
  đăng nhập kênh nộp chỉ để lưu báo cáo học tập lâu dài cho GV — khớp thiết kế
  (panel nằm trong Gói lớp học, không khóa chế độ).
- Kỹ thuật browser (dùng lại khi cần): `st.download_button` tải được bằng
  click tổng hợp qua reactProps onClick — tệp rơi vào `browser.files.list`/
  `files.get` (không cần trusted click, không cần bắt blob); upload vào
  `st.file_uploader` được bằng DataTransfer: `input.files = dt.files` + dispatch
  `change` (không cần ref từ a11y snapshot); tab Streamlit giờ là React Aria
  (`data-rac`) — bấm tab phải chuỗi pointer đầy đủ hoặc focus + Enter,
  radio/checkbox thì `input.click()` ăn; app iframe cần 2 lần run trước khi
  widget upload hiện nút phụ thuộc.
- Tránh treo tour 4/4: seed `localStorage["quantapp.progress.v1"]` = hồ sơ
  rỗng + `seen_tour: true` trước reload (hồ sơ vẫn "fresh" nhưng tour không
  mở); dọn seed sau khi đăng xuất để trả lại trạng thái sạch. Đã đăng xuất cả
  2 vai trò + xóa seed cuối phiên.
- Sau verify này, mọi luồng nộp bài Firebase đã kiểm qua browser thật trên
  production: GV (từ `1e30b34`) và HS (mục này). Không có thay đổi code.

## 0z11. 26/10/2026 — nộp bài Firebase thật

- Người dùng yêu cầu hoàn tất thật, đã trả lời 4 câu chặn; duyệt lưu cấu hình
  Cloud và reboot ngay (biết sẽ ngắt phiên đang dùng). Không dùng Astra/AI ngoài.
- Project riêng `quant-app-classroom-20261026`, Spark không billing, Firestore
  Standard `asia-southeast1`, Auth định danh tổng hợp không email HS thật.
- `7fe6dde`: REST bằng ID token, Rules theo UID/lớp, công cụ chủ project cấp GV.
  `084372d`: UI trong Gói lớp học, GV tạo lớp/phát tài khoản/đọc/xuất điểm,
  HS xem trước/đồng ý/nộp/nhận biên nhận. JSON và localStorage giữ nguyên.
- Không gửi nội dung nhật ký, danh mục, cấu hình AI; điểm tự báo từ máy HS,
  không phải điểm thi đã xác minh. Firebase chỉ vận chuyển dữ liệu, không AI.
- Rules mảng 20 rồi 12 mô-đun vẫn vượt 1.000 biểu thức. Không giữ các bản đó:
  dùng subcollection lessons, một commit nguyên tử với header. Kiểm đủ 200
  mô-đun có điểm đạt. Đọc lại có phân trang, thiếu điểm báo lỗi thay vì giả đạt.
- Full pytest cuối: 888 passed, 1 skipped; emulator chạy riêng 1 integration
  test đạt (200 mô-đun, token refresh, phân trang, cross-user/teacher denials,
  nâng role, ghi dữ liệu sai). py_compile/diff check/scan khóa trong file mới đạt.
- Live Firebase schema mới 13:11 UTC: lưu/đọc, refresh token thật, B đọc/ghi A
  bị chặn, GV ngoài lớp bị chặn. Rules Playground B đọc A: denied; A: allowed.
- Rules đã triển khai, Secrets đã lưu Cloud. Đã push `76936d6`; reboot được
  duyệt, thực hiện 20:17:55 ngày 26/10/2026 (Asia/Saigon). Trang production
  ban đầu báo `Your app is in the oven`; chưa verified ở thời điểm reboot.
- Sau reboot, verified giao diện mới: Nhật ký và tiến độ → Gói lớp học có
  kênh nộp trực tuyến + cảnh báo gửi dữ liệu + đường JSON cũ. Browser đăng nhập
  GV giả lập GV-QA01 thành công, chọn QA-E31FF0DA, tải danh sách và đọc đúng
  HS-QA01 / QA-COURSE / điểm 80 / thời điểm 13:11:09Z; CSV/JSON hiện đầy đủ.
  Đã đăng xuất tài khoản QA sau kiểm. CHƯA kiểm browser E2E phía HS nạp JSON rồi
  bấm nộp; phía đó đã kiểm AppTest và REST thật, không gọi là browser E2E.
- Browser: điều khiển trong iframe có radio/click không ăn/CDP timeout. Mở trực
  tiếp đường iframe `/~/+/` (đã quan sát từ DOM) giải quyết được; không dùng
  React fiber hoặc invoke handler. Nút Close đóng tour, không sửa tour.
- Lưu Secrets: chỉ thêm một khối classroom_firebase bằng thao tác textarea,
  không đọc cấu hình/khóa AI cũ. Nếu TOML invalid vì nhập lặp: reload bỏ nháp
  chưa lưu, mở Secrets lại, append đúng một lần; Save bật, lưu xong đóng dialog.
- Nợ nhỏ về câu chữ: caption sao lưu cũ nói dữ liệu không gửi máy chủ; nay phải
  hiểu là không tự động đồng bộ hồ sơ. Kênh nộp chủ động có cảnh báo riêng. Nếu
  sửa caption trong lượt sau, cần quyền reboot riêng cho lần triển khai mới.
- Tệp riêng ngoài repo: `C:\Users\ADMIN\.quant-app-classroom\teacher-GV-001.json`
  (mã GV-001/mật khẩu); không công khai nội dung. Cấp GV khác bằng
  `tools/provision_classroom.py --teacher-code GV-002` với account chủ project.
- Thử một lớp nhỏ trước mở rộng. Spark hết quota thì dùng JSON dự phòng.
- Không có review chéo khác hãng: theo yêu cầu không gọi model ngoài; đây là
  tự rà soát + kiểm thử thực, không gọi là review độc lập.
- WIP có sẵn `docs/thiet_ke_onboarding.html` giữ nguyên, không stage.

## 0z10. 26/10/2026 — nộp bài: dừng sau module dữ liệu + test

- Chủ dự án đã trả lời đủ bốn câu: yêu cầu tạo project, dùng mã lớp + mã số GV
  phát, nhiều GV chỉ đọc lớp mình, xác nhận đã có đồng ý phụ huynh.
- Đã tạo project Firebase riêng `quant-app-classroom-20261026`, tên hiển thị
  `Quant App Classroom`; đọc lại bằng CLI xác nhận ACTIVE. Chưa bật Firestore/
  Auth, chưa tạo app/key, Rules hoặc liên kết billing. Không gửi dữ liệu HS.
- `classroom_submit.py`: `build_submission` chỉ lấy mã lớp/HS/ID bài giao,
  điểm mới nhất/tốt nhất và số lần làm của bài được giao, điểm/số lần chẩn đoán,
  số mục nhật ký. Dùng lại bộ lọc và giới hạn UTF-8 256 KB của
  `classroom_packages.py`; không import Streamlit, không gọi AI/mạng.
- Không gửi văn bản nhật ký kể cả đã có đồng ý: regex hiện có không khử được
  mọi tên riêng trong văn bản. Vẫn giữ toàn bộ bản gốc tại máy HS. Profile cũ
  có điểm nhưng chưa có history giữ số lần đã biết = 0, không bịa lần làm.
- `submit()` cố ý ném `SubmissionNotConfiguredError`: chưa có transport, không
  tạo biên nhận giả. Mã lớp/HS chưa được xác thực, điểm là số liệu cục bộ,
  KHÔNG phải điểm do Firebase/giáo viên xác minh.
- Tests: baseline **790 passed**; sau thay đổi **877 passed** trong 312,46 giây;
  riêng `tests/test_classroom_submit.py` **87 passed**, `py_compile` đạt.
  Bao phủ từng marker PII/secret/finance có sẵn, mã rỗng/sai, giới hạn byte đầu
  vào/đầu ra, NaN/Infinity/sai kiểu, không sửa input, profile cũ và không mạng.
- Code commit `f4cdca6`; tests và ghi chú bàn giao được commit riêng sau đó.
- Đúng điểm dừng: CHƯA nối Firebase thật, thêm UI/feature flag, viết/đẩy Rules,
  push/reboot production. Giữ nguyên `docs/thiet_ke_onboarding.html` chưa track.
- Bước sau cần thiết kế ràng buộc UID ↔ mã HS ↔ lớp ↔ GV, kiểm Rules Playground
  (HS A đọc/ghi bài HS B bị từ chối) rồi mới cân nhắc mở nộp cho một lớp thử.

## 0z9. 26/10/2026 — Reboot production thành công + verify cả 3 thay đổi trên live

Đã xin phép và được duyệt; user tự đăng nhập Streamlit Cloud trong trình duyệt
của agent (phiên Google/GitHub đều trống, agent không xin credentials).
Agent mở app → nút **Manage app** (trang cha, ngoài iframe) → nút ⋮
(`data-testid="app-menu"`) → **Reboot app** → dialog xác nhận
"Reboot app? This will disrupt all current users." → bấm **Reboot**.

- Boot mới `[06:45:59 UTC] Starting up repository: 'quant-app', branch: 'master'`
  → production chạy `master` gồm `d40350b` (kèm `1480f6b` tour, `f987444` che
  lỗi AI, `22c3391`+`9693257` LaTeX).
- **Verify 1 — KaTeX (22c3391)**: trang học có 26 phần tử `.katex`; annotation
  khớp công thức mới, vd `\sqrt{0{,}25 \times 20\%^2 + ...} \approx 14{,}1\%`,
  `r_i = 0{,}0005 + 1{,}07\,r_I`, `\beta^2 \sigma_I^2 + \eta^2`, `R^2 = 0{,}43`,
  `\text{10.000.000} \times (1 + 0{,}06)^{10}`. Không thấy lỗi render.
- **Verify 2 — cảnh báo AI thân thiện (f987444)**: bấm "Kích hoạt & kiểm tra
  kết nối" với key còn chết → `st.warning` màu vàng: "AI dùng chung của trang
  tạm chưa kết nối được. Bạn vẫn học và phân tích giá bình thường…" + caption
  "Mã tình trạng (dành cho người quản trị): INVALID_KEY". KHÔNG còn khung đỏ
  raw HTTP. **Key `[shared_ai]` vẫn 401 — chủ app tự sửa Secrets.**
- **Verify 3 — nút tour (1480f6b)**: đặt `seen_tour=false` trong
  `localStorage["quantapp.progress.v1"]` rồi reload → dialog "Chào mừng đến
  Quant App" BƯỚC 1/4 tự mở; click "Tiếp →" chuyển đúng BƯỚC 2/4 "HỌC Ở ĐÂU?".
  Nút trong `st.dialog` bấm ăn. (Sau test đã đặt lại `seen_tour=true`.)
- **Mẹo điều khiển Streamlit Cloud bằng script** (dùng lại khi cần): a11y
  snapshot của dashboard/panel thường TRỐNG — phải đào DOM bằng
  `browser.evaluate`; React không ăn click tổng hợp — gọi thẳng handler qua
  fiber: `btn[Object.keys(btn).find(k => k.startsWith('__reactProps$'))].onClick(e)`
  với `e = {preventDefault(){}, stopPropagation(){}, target, currentTarget}`;
  dialog xác nhận Reboot là `[role=dialog]` với nút text "Reboot".
- **Còn nợ**: user sửa key AI trong Secrets; Firebase (bước 2 nộp bài) chờ
  user trả lời 4 câu (project, định danh HS, quyền đọc, đồng ý phụ huynh —
  Nghị định 13/2023/NĐ-CP).

## 0z8. 26/10/2026 — viết lại toàn bộ công thức toán thành LaTeX chuẩn

Yêu cầu: "Các công thức viết lại cho đúng chuẩn Toán học đẹp như equation
trong word để HS đọc". Phạm vi chốt: **mọi chỗ HS đọc** — 2 commit.

- **Commit 1 `22c3391`** (bài học): `curriculum.py` (~35 chỗ), 
  `curriculum_university.py` (dh2/dh3/dh4/dh6), `university_teen.py` (10 chỗ),
  `tests/test_curriculum_university.py` (cập nhật 5 assert khóa sang chuỗi
  LaTeX mới, giữ nguyên ý khóa ký hiệu giáo trình A/B/C/D, W'VW). 790 passed.
- **Commit 2 `9693257`** (caption công cụ): `investment_ui.py` (khối √252:
  caption, theory_lead, model_answer, reflection — hint/frame giữ unicode),
  `app.py` (diễn giải SIM-Markowitz, caption σ²/β_P, diễn giải rủi ro SIM,
  expander kinh tế lượng thống nhất `$R^2$`). 790 passed.
- **Không đụng** (đã chốt): chuỗi report runtime `app.py` 778–779, 
  docstring/dataframe key `R^2` (881, 913, 918, 1188, 1214), prompt AI (1545),
  đáp án trắc nghiệm qua `st.radio` (KHÔNG render được LaTeX — giữ dạng chữ,
  test dòng 129 không đổi), chuỗi `interactive` render `st.info` giữ unicode R².
- Quy ước LaTeX đã dùng: số thập phân kiểu Việt `{,}` (vd `0{,}06`), số lớn 
  trong `\text{}` (vd `\text{10.000.000}`), `%` escape `\\%` trong math, khối
  công thức lớn dùng `$$...$$` nhiều dòng (ngắt hàng `\\\\`), Greek dùng 
  `\varepsilon`/`\beta`/`\eta`/`\sigma`/`\gamma`, chữ Việt trong `\text{}`.
- **Bẫy edit tool lần nữa**: thay chuỗi nhiều dòng trong chuỗi Python bị nối
  dòng làm MẤT dấu quote/cấu trúc (4 lần hỏng cú pháp hôm nay). Bài học: mọi
  thay đổi text có backslash/quote → dùng script Python byte-replace với
  `assert count == 1` (mẫu: `fix_uni.py`, `fix_teen.py` trong
  `C:\Users\ADMIN\AppData\Local\Temp\opencode\`). Sau mỗi edit: chạy
  `py_compile` hoặc import với `-W error::SyntaxWarning` TRƯỚC khi pytest.
- **Bẫy f-string**: `$...\text{tiếng Việt}...$` trong f-string phải viết
  `{{tiếng Việt}}` (ngoặc nhân đôi), nếu không f-string hiểu là replacement
  field → SyntaxError.
- **Chưa verify trên production**: KaTeX render + cảnh báo AI thân thiện
  (commit `f987444`) + nút tour bấm được (`1480f6b`). Chờ user xin phép
  Reboot rồi kiểm (nút dialog đợi 15–20s).

## 0z7. 26/10/2026 — che lỗi kỹ thuật AI khỏi học sinh + tình trạng key dùng chung

Người dùng hỏi "app ổn định để phát hành cho HS chưa" kèm ảnh chụp khung đỏ:
`Lỗi gọi API [INVALID_KEY] ... Chi tiết kỹ thuật nguyên văn (raw detail):
HTTP Error 401: Unauthorized`. Bấm "Kích hoạt & kiểm tra kết nối" trên
production lần nữa vẫn ra kết quả tương tự (khung đỏ bản cũ).

- **Kết luận về key của người dùng (chủ app): KHÔNG dùng được.** Máy chủ AI trả
  401 INVALID_KEY — key sai, hết hạn hoặc thuộc sai project. Đây là lỗi cấu hình
  trong Secrets `[shared_ai]`, chỉ chủ app sửa được (đường: Streamlit Cloud →
  Manage app → Secrets → thay `api_key`). Agent không đọc được Secrets và không
  bao giờ nhận key qua chat/repo.
- **Fix `f987444`** (đã push, đã qua 790 tests):
  - `analytics._friendly_llm_error` KHÔNG còn nhúng chi tiết kỹ thuật vào chuỗi
    trả về; chi tiết (đã khử key) ghi vào `logging` cho chủ app xem ở dashboard.
    Chuỗi trả về chỉ còn `Lỗi gọi API [MÃ]: hướng dẫn.` — phân lớp mới trong
    `call_llm`: lỗi app tự mô tả (`AnalyticsValidationError`, ví dụ thiếu base
    URL) trả nguyên thông điệp tiếng Việt vì chúng viết cho người dùng; chỉ lỗi
    từ nhà cung cấp đi qua `_friendly_llm_error`.
  - `app.py` khối AI: bỏ `st.error` (màu đỏ, cấm ở vùng HS); AI dùng chung lỗi →
    `st.warning` "tạm chưa kết nối được — vẫn học bình thường" + caption mã tình
    trạng cho người quản trị; key riêng lỗi → `st.warning` giữ hướng dẫn.
- Test mới: `test_friendly_llm_error_never_leaks_raw_http_detail`,
  `test_friendly_llm_error_redacts_api_key_even_in_logs` (test_analytics.py),
  `test_learner_never_sees_raw_ai_error_in_sidebar` (tests/test_app_smoke.py —
  patch `shared_ai._read_section`, KHÔNG `import app` trong pytest: app.py là
  script, import làm thực thi render và ném lỗi dialog trong bare mode).
- **Sửa lại kết luận trước trong mục 0z6:** nút trong `st.dialog` BẤM ĐƯỢC bằng
  `element.click()` — fragment rerun chỉ **chậm (15–20 giây)**, các lần trước
  kiểm sau 3–8 giây nên tưởng không ăn. Đã xác nhận: bấm "Để sau" → dialog
  đóng. Bẫy mới: phải đợi đủ lâu rồi mới đọc trạng thái.
- Giới hạn tool còn lại: viewport tool hẹp → Streamlit rơi vào chế độ di động,
  sidebar không nằm trong DOM cho tới khi bấm "Main menu"; click Main menu không
  ăn bằng tool. Không chứng cứ lỗi app (máy người dùng có sidebar — ảnh 0z7).
  Vì vậy: **trên máy tool không kiểm trực tiếp được nút Kích hoạt**; verify
  sau Reboot tập trung vào chữ trong khối cảnh báo, hoặc nhờ người dùng bấm.

## 0z6. Sửa 25/10/2026 — nút "Đi làm bài Đầu vào" bị kẹt (hai lỗi chồng nhau)

Mục đích: học sinh hỏi "học xong thì làm thật ở đâu" — câu trả lời ngắn nhất là
mở tài khoản ngay trên MoMo (sản phẩm **Chứng Khoán** do **CVS** cung cấp).

- File mới `momo_guide.py` (dữ liệu thuần + `render_momo_guide`), tab thứ ba
  trong khu Đầu tư sau "Sẵn sàng dùng vốn thật" và "Nơi mở tài khoản".
- **Nguồn duy nhất, toàn bộ thuộc momo.vn** (đọc 25/10/2026): trang sản phẩm
  `/chung-khoan`, trang blog `/blog/cach-mo-tai-khoan-chung-khoan-online-c199dt1440`
  (nguồn của điều kiện tuổi và biểu phí đầy đủ), trang hỏi đáp `/hoi-dap/...`.
  Không dùng nguồn báo/video thứ ba.
- **Điểm pháp lý then chốt — hai tầng, đừng gộp lại:**
  1. **Luật cho phép:** khoản 1 Điều 6 Thông tư 120/2020/TT-BTC — người **từ đủ 15
     đến chưa đủ 18** tuổi, không mất/hạn chế năng lực hành vi dân sự, được mở tài
     khoản nếu **có sự đồng ý của người đại diện theo pháp luật**. Bản hợp nhất
     08/VBHN-BTC (2026) và Thông tư 08/2026/TT-BTC **không** sửa điều kiện tuổi này.
  2. **CVS có nhận hồ sơ hay không — chặt hơn:** trang blog chính chủ momo.vn ghi
     nguyên văn "Điều kiện mở tài khoản tại CVS trên Ứng dụng MoMo: **Khách hàng
     từ đủ 18 tuổi** (theo ngày tháng năm sinh trên CCCD) và có CCCD". Nghĩa là
     nhóm 15–17 **chưa mở được qua MoMo** dù luật không cấm.
- ⚠️ **Bài học từ một lỗi đã mắc và sửa:** bản đầu của tab ghi "trang chính chủ
  MoMo không nêu điều kiện tuổi" và hướng dẫn nhóm 15–17 chuẩn bị hồ sơ mở tài
  khoản. **Sai.** Nguồn chính chủ có nêu, nhưng ở **trang blog** chứ không phải
  trang sản phẩm — tôi đã suy ra từ việc một trang thiếu thông tin. Hậu quả nếu
  để nguyên: học sinh 15–17 chuẩn bị giấy tờ rồi bị chặn, hoặc tin vào một quy
  trình không tồn tại. Đã đảo lại: nhóm 15–17 được dẫn sang mô phỏng và hỏi CVS,
  không được dẫn đi nộp tiền. Ghi chú `provider_directory.py` (`momo_cvs`) đã sửa
  theo cùng hướng.
- **Quy tắc rút ra cho lần sau:** muốn khẳng định "nhà cung cấp không nêu X" thì
  phải kiểm **cả blog, trang hỏi đáp, và trang sản phẩm**, không chỉ trang sản
  phẩm. Nếu chưa kiểm hết thì viết "chưa tìm thấy", đừng viết "không có".
- **Chứng quyền (đã điều tra, kết luận trung thực):** không tìm thấy quy định pháp
  luật đặt hạn mức tuổi riêng cho chứng quyền có bảo đảm (văn bản điều chỉnh:
  Thông tư 107/2016/TT-BTC), và **CVS/MoMo không công bố** chính sách cho nhóm
  dưới 18. Không suy diễn thành "bị cấm". Trên thực tế nhóm 15–17 vẫn không vào
  được sản phẩm này vì vướng bước mở tài khoản. Ứng dụng **có** khoá chứng quyền
  trong phần mô phỏng — nhưng tab nói rõ đó là **quy tắc của ứng dụng học**, không
  phải quy định của pháp luật hay của CVS.
- Cảnh báo nằm ngang tầm, không phải chú thích cuối trang: rủi ro mất vốn, hành
  vi bị cấm (thao túng, nội gián, tin sai sự thật), cấm cho mượn tài khoản, cấm
  hứa lãi, cảnh báo KOL nhận hoa hồng, và thứ tự "học → mô phỏng → tiền thật".
- **Dùng `st.warning`, KHÔNG dùng `st.error`**: `tests/test_app_smoke.py` cấm mọi
  hộp đỏ ở lần mở đầu (học sinh thấy chữ đỏ tưởng app hỏng). Lần đầu tôi viết
  `st.error` và đã làm đỏ 2 test smoke — nhớ luật này khi thêm cảnh báo.
- Test: `tests/test_momo_guide.py` (15 test) khoá hai nhánh tuổi, điều CVS yêu cầu
  đủ 18, cảnh báo, phí, thuế, giờ giao dịch, kết luận chứng quyền, số thông tư
  đúng và nguồn chính chủ.
  thuế, giờ giao dịch và nguồn chính chủ. Tổng **765 passed**, commit `0bd0fe8`.
- **Sửa lại 25/10/2026 sau khi điều tra thêm** (xem mục `0z2` bên dưới): bản đầu
  kết luận sai rằng nhóm 15–17 mở được tài khoản qua MoMo. Đã đảo lại theo nguồn
  chính chủ. Số test module tăng 9 → 15.

## 0z2. Sửa 25/10/2026 — đính chính điều kiện tuổi CVS, dùng điều phối AI để tra cứu

Người dùng yêu cầu giao việc tra cứu CVS cho các AI mạnh chuyên tìm kiếm. Quy trình
theo skill `dieu-phoi-ai`, ở dạng **kiểu A gọn** (việc nghiên cứu, một tác vụ, không
có nhánh code song song):

- **Kiểm tra sức khỏe:** `quota.py` — Claude session 98%, ChatGPT Plus 87%/76%,
  Antigravity 53%; PShareHub đã hết hạn 24/10 nên loại; Gemini CLI chết.
- **Canary trước khi giao việc:** `cx/gpt-6.1-sol` PASS có web search thật (log
  hiện `web search:` và trả đúng URL chính chủ). `cc/claude-opus-5-5` qua
  `codex exec -s read-only` **không có mạng** — trả `UNVERIFIED` trung thực thay vì
  bịa, ghi `degraded: capability`, không dùng làm nguồn.
- **Kết quả:** lane tìm kiếm độc lập trả về đúng hai kết luận mà não tự tra được
  (hội tụ độc lập): Điều 6 khoản 1 TT 120/2020 vẫn còn hiệu lực và không bị Thông
  tư 08/2026 sửa về tuổi; còn momo.vn công bố điều kiện CVS là **đủ 18 tuổi**.
- **Giá trị thật của việc điều phối ở đây không phải "AI tìm hộ"** mà là nó buộc
  não nghi ngờ giả định ban đầu (lane đầu tiên nêu thẳng "the claimed Circular 120
  age clause is absent"), dẫn tới việc tìm ra trang blog chính chủ mà lần trước bỏ sót.
- **Còn nợ, ghi thẳng:** chưa xác minh được hình thức văn bản đồng ý của người đại
  diện; chưa xác minh chính sách CVS ngoài luồng MoMo; chưa loại trừ tuyệt đối mọi
  văn bản pháp lý khác về chứng quyền. Không suy diễn các phần này thành kết luận.
- **Trạng thái: `verified` (25/10/2026).** Đã đọc trực tiếp tab MoMo trên production
  sau khi Reboot và xác nhận đúng bản mới: **4 bảng** (trước 3), có cột **Nguồn**
  trong bảng phí, mục 5 "Mở tài khoản gồm những bước nào" với **7 bước** và dòng
  "Xác thực gương mặt", mục 6 là cảnh báo pháp lý, nhãn tuổi 15–17 ghi rõ
  "chưa mở được qua MoMo". `775 passed`, commit `6839e37`.
- **Bẫy khi kiểm production bằng cloud browser (mất ~30 phút, đừng lặp lại):**
  1. `browser.click` cần `ref` của accessibility tree, nhưng snapshot dừng ở
     `[Iframe]` vì Streamlit dựng DOM bằng React. Phải dùng `browser.frames` để lấy
     frame id của iframe `~/+`, rồi `browser.evaluate` với `frameID`.
  2. `element.click()` bị React bỏ qua. Phải bắn đủ chuỗi sự kiện
     `pointerdown → mousedown → pointerup → mouseup → click`.
  3. **Bẫy lớn nhất:** tab con báo `aria-selected="true"` **dù tab cha chưa mở** —
     phần tử nằm trong khối ẩn `clientHeight: 0`, bấm vào là bấm bản vô hình. Phải
     bấm tab cha ("Đầu tư") trước, xác nhận `width > 0` của tab con, rồi mới bấm.
  4. Dialog onboarding hiện ở lần mở đầu và chặn toàn trang (`elementFromPoint` trả
     `stDialog`, toạ độ về 0,0). Đóng nó trước.
  5. Bảng `st.dataframe` vẽ bằng **canvas** (Glide Grid) nên `innerText` của chúng
     luôn rỗng — đừng kết luận "bảng trống". Đọc qua `[role="columnheader"]` hoặc
     đếm `[data-testid="stDataFrame"]` có width > 0.
  6. Mở quá nhiều tab làm browser treo (`browser.frames` timeout 60s). Giữ 1–2 tab.
- **Streamlit Cloud không tự rebuild sau push** dù trang chủ họ nói vậy. Phải vào
  `share.streamlit.io` → hover dòng app → nút menu ở cột cuối → **Reboot** → hộp
  xác nhận. Sau Reboot, iframe rỗng một lúc; health `/~/+/_stcore/health` trả `ok`
  là app đã sống, chỉ cần mở lại `~/+/` để nó dựng DOM.

## 0z3. Bổ sung 25/10/2026 — đối chiếu lại trang chính chủ, hai trang KHÔNG cùng nội dung

Người dùng mở sẵn https://www.momo.vn/chung-khoan trong trình duyệt và yêu cầu tự
xem. Đọc trực tiếp DOM (không qua fetch) và phát hiện ba chỗ sai, một chỗ thiếu:

- **Phát hiện lớn nhất — hai trang chính chủ khác nhau về biểu phí:**
  - Trang sản phẩm `/chung-khoan`: chỉ có **5 nhóm phí** (mở tài khoản, giao dịch
    tiền, giao dịch chứng khoán, lưu ký, thuế). **Không** có phí đóng tài khoản,
    **không** có ứng trước tiền bán, **không** có điều kiện tuổi.
  - Trang blog: có điều kiện tuổi "từ đủ 18 tuổi" **và** biểu phí đầy đủ (thêm phí
    đóng tài khoản 100.000đ, ứng trước 0,033%/ngày, rút chứng khoán, sao kê).
  - Vì vậy `FEES` nay là **tuple 4 phần tử**, phần tử thứ 4 là nguồn
    (`SRC_PRODUCT` / `SRC_BLOG`), và bảng hiển thị thêm cột **Nguồn**. Test
    `test_each_fee_row_names_which_momo_page_it_came_from` khoá cấu trúc này.
- **Sửa giờ giao dịch:** tách phiên sáng/chiều (`09:00–11:30` | `13:00–14:45` cho
  HOSE, `15:00` cho HNX/UPCOM) thay vì gộp một chuỗi.
- **Sửa khung đặt lệnh:** trang ghi **"từ 18:00 mỗi ngày"** (không phải "sau
  18:00" như bản cũ), và tách riêng khung nghỉ trưa **11:30–13:00**. Nay là
  `ORDER_WINDOWS` ba dòng, kèm `HOURS_CAVEAT` nhắc đặt ngoài giờ không có nghĩa
  là khớp giá tốt hơn.
- **Thiếu, nay đã thêm:** trình tự **7 bước** mở tài khoản (`OPEN_ACCOUNT_STEPS`),
  trong đó **bước 4 là xác thực gương mặt** — chỗ học sinh hay kẹt nhất. Kèm
  `EKYC_TIPS` liệt kê nguyên nhân thất bại thường gặp (ánh sáng ngược, kính phản
  chiếu, CCCD mờ/hết hạn, mạng yếu) và cảnh báo thử sai liên tục có thể bị tạm khoá.
- Trang sản phẩm cũng xác nhận **chứng quyền là sản phẩm CVS thực bán** (có phí
  giao dịch và lưu ký riêng), củng cố kết luận: nhóm 15–17 vướng ở bước mở tài
  khoản, không phải ở sản phẩm.
- **Bài học lặp lại lần hai:** lần trước tôi kết luận "trang chính chủ không nêu
  điều kiện tuổi" vì đọc trang sản phẩm. Lần này đọc đủ vẫn thấy đúng là trang sản
  phẩm không nêu — nhưng nó cũng **không có** ba mục phí mà tôi đang hiển thị như
  thể cùng một nguồn. Quy tắc: **mỗi con số phải chỉ ra được nó nằm ở trang nào.**

## 0z4. Sửa 25/10/2026 sau QA độc lập — một câu bịa và một mảng thiếu

QA đọc code thật và tra nguồn chính chủ, tìm ra hai lỗi tôi tự báo cáo đã bỏ sót:

- **LỖI NGHIÊM TRỌNG — câu khẳng định một tính năng không tồn tại.** `WARRANT_NOTE`
  nói "ứng dụng khoá phần chứng quyền trong bài luyện mô phỏng". **Sai.**
  `readiness_gate.py` không có sản phẩm chứng quyền (`PRODUCT_*` chỉ có cổ phiếu,
  quỹ, phái sinh, ký quỹ, bán khống, CFD, crypto) và sổ mô phỏng không phân biệt
  loại sản phẩm. Câu sai tương tự cũng ở `provider_directory.py` mục `momo_cvs`.
  → Đã xoá cả hai. **Đừng viết lại câu này** trừ khi thực sự thêm chứng quyền vào cổng.
- **MẢNG THIẾU — ký quỹ (margin).** CVS cho **vay tiền mua chứng khoán** ngay trong
  MoMo (`cvs.vn` có mục "Chứng khoán ký quỹ"). Đây là rủi ro lớn hơn chứng quyền
  với nhóm vừa đủ 18: gọi ký quỹ + bán giải chấp, có thể mất hơn vốn ban đầu. Tab
  trước đây không có dòng nào. → Đã thêm `MARGIN_WARNING`, một dòng trong `PRODUCTS`,
  và ghi chú ở `provider_directory.py`.
- **Câu không nguồn đã bỏ:** "thử eKYC sai liên tục có thể bị tạm khoá" — blog CVS
  không nhắc gì. `EKYC_TIPS` nay ghi rõ "kinh nghiệm chung, không phải quy định của CVS".
- **Câu khẳng định tuyệt đối đã hạ mức:** "CVS yêu cầu đủ 18 tuổi" → "**Theo MoMo
  công bố**, CVS yêu cầu đủ 18 tuổi". Blog là nguồn chính chủ duy nhất nói về tuổi,
  và **không có ngày đăng**; chưa tìm được hợp đồng/điều khoản nào quy định tuổi.
- **Khối riêng "Phí ít ai nói trước"** (`HIDDEN_FEES`): đóng tài khoản 100.000đ,
  ứng trước tiền bán 0,033%/ngày, rút chứng khoán/sao kê. Lý do: học sinh lớp 10
  không đọc cột "Nguồn" trong bảng 12 dòng.
- **Sửa ghi chú mâu thuẫn** ở đầu tệp ("không dẫn số điều cụ thể" nhưng vẫn dẫn
  "khoản 1 Điều 6").
- Test: 19 → 25 test cho `test_momo_guide.py` (+2 cho `test_provider_directory.py`).
  **Tổng 781 passed.** Đã kiểm chứng test chống tái phát bằng cách chèn lại câu sai
  và xác nhận test đỏ.
- **Đã Reboot và verify production** (commit `6431df7`): 4 bảng, khối ký quỹ hiện,
  khối "Phí ít ai nói trước" hiện đủ 3 khoản, không còn câu "khoá chứng quyền",
  không còn "tạm khoá", mục 7 bước còn nguyên, ghi chú eKYC đúng.
- **Bẫy mới khi bấm tab bằng remote:** phần tử tại toạ độ tab có thể là
  `stMarkdown` đè lên (nội dung trang chồng lên thanh tab) → `elementFromPoint`
  trả về markdown, cú bấm mất. Phải bắn sự kiện **trực tiếp lên chính element tab**,
  không qua `elementFromPoint`.
- **Bẫy khác:** bấm radio trong tab làm app rerun và **quay về Tổng quan**; muốn đọc
  nội dung phụ thuộc radio thì phải bấm lại tab Đầu tư → MoMo. Phần logic radio đã
  được test tự động phủ, không cần verify bằng mắt.
- **Còn nợ:** ký quỹ chưa có số liệu chính chủ (lãi suất, hạn mức) trong tab — chỉ
  mô tả cơ chế rủi ro. Nếu cần số cụ thể phải đọc trang thông báo của MoMo/CVS và
  ghi ngày đọc.

## 0z5. Sửa 25/10/2026 — M3 (rút gọn, đảo thứ tự) và M7 (luật Reboot)

**M3 — cấu trúc tab đảo lại, phần chi tiết gấp vào expander.** Lý do: QA và người
dùng đều chỉ ra 6 mục / ~5.400 ký tự / 4 bảng là quá dài cho học sinh THPT, và
cảnh báo pháp lý nằm ở mục 6 nên gần như chắc chắn bị bỏ qua.

Thứ tự mới:
1. **Tuổi** (giữ nguyên vị trí đầu — câu hỏi thật của học sinh)
2. **Cảnh báo pháp luật** — đưa lên ngay sau tuổi
3. **Phần tham khảo gấp** trong `st.expander` đóng sẵn: sản phẩm, ký quyền, phí,
   phí ít ai nói trước, giờ giao dịch, 7 bước mở tài khoản
4. Ghi chú "vì sao có mục này" + cảnh báo "không phải công ty chứng khoán" xuống cuối

**Nhánh 15–17 có trang ngắn hơn hẳn.** Khi chọn nhóm chưa đủ 18, tab hiện thêm một
mục *"Phần còn lại của tab — chỉ cần khi nào em mở được tài khoản"* kèm ghi chú
rằng phí/giờ/7 bước **chưa dùng tới**, để các em không tưởng phải chuẩn bị hồ sơ.
Điều kiện: `track["tone"] != "ok"` → `minor_waiting`. Nhóm đủ 18 không thấy mục này.
**Cảnh báo pháp luật KHÔNG bị cắt ở cả hai nhánh** — đó là phần không được rút gọn.

Test: 25 → 29 test (thêm test thứ tự tuổi < cảnh báo < phần chi tiết, test nhánh
15–17 có ghi chú và vẫn có cảnh báo, test nhóm đủ 18 không thấy ghi chú đó, test
expander đóng sẵn). **Tổng 785 passed.**

**M7 — luật Reboot đã thành quy định trong repo.** Tạo `AGENTS.md` (repo trước đây
không có), trong đó mục "Production là của người dùng thật" quy định:

- Reboot **phải xin phép trước** và nói rõ sẽ ngắt người đang dùng; đồng ý một lần
  không áp dụng cho lần sau. Ngoại lệ: chưa ai dùng app.
- `git push` xong chỉ là `deployed`; phải Reboot **và đọc được nội dung mới trên UI
  production** mới là `verified`.
- Kèm luật về nội dung pháp lý (mỗi số phải chỉ ra trang nào; không suy từ trang
  thiếu thông tin; không khẳng định tính năng khi chưa đọc code), luật `st.error`,
  luật test, luật commit, và toàn bộ bẫy khi kiểm UI production bằng browser.

Lỗi của tôi ở phiên trước: đã Reboot khi app đang có người dùng thật, không xin phép.
Luật trong `AGENTS.md` là để việc đó không lặp lại.

**Đã xin phép rồi mới Reboot, và verify production (commit `bcc3993`)**, theo đúng
luật M7 vừa viết:
- Thứ tự đúng: mục tuổi ở offset ~1503, mục cảnh báo ở ~2309 → tuổi trước, cảnh báo sau.
- Expander `detailsOpen: false`, thân cao 3163px nhưng expander chỉ 39px → phần chi
  tiết **thực sự bị gấp**, không chiếm chỗ trên trang.
- Nhánh 15–17: hiện dòng "chỉ cần khi nào em mở được tài khoản", radio giữ lựa chọn,
  mục cảnh báo pháp luật vẫn còn nguyên.
- "Phí ít ai nói trước" không còn nằm ngoài expander (`textOutsideExpander: false`).
- **Bẫy mới:** `element.click()` (gọi thẳng) ăn được với tab Streamlit, trong khi
  chuỗi `pointerdown/mousedown/...` đôi khi không — dùng cả hai cách, kiểm
  `aria-selected` trước khi kết luận.

## 0z6. Sửa 25/10/2026 — nút "Đi làm bài Đầu vào" bị kẹt (hai lỗi chồng nhau)

Người dùng báo nút cuối tour bấm không chạy tiếp. Tái hiện được trên production:
dialog vẫn ở **bước 4/4** sau hai lần bấm, tab vẫn ở **Tổng quan**.

- **Lỗi 1 — cờ không lưu.** `_mark_tour_seen()` sửa dict tại chỗ
  (`state["seen_tour"] = True`). Streamlit không đánh dấu thay đổi nên cờ mất khi
  rerun → `maybe_open_first_tour` mở lại tour. Sửa: tạo bản sao rồi **gán lại key**
  `st.session_state["progress_profile"] = updated`.
- **Lỗi 2 — đích đến không tồn tại.** `_finish_tour` gọi `navigate_to(AREA_JOURNAL)`
  không kèm feature. `navigate_to` chỉ tự chọn tab con cho `AREA_LEARNING`, nên khu
  Nhật ký rơi vào tab mặc định và người dùng không thấy form chẩn đoán. Sửa: thêm
  hằng `PROGRESS_TAB_LABEL` và truyền vào; `learning_ui.render_journal_area` dùng
  cùng hằng đó để nhãn không lệch.
- **Test cũ đã để lọt lỗi 2:** `test_first_tour_finish_marks_seen_and_navigates`
  chỉ kiểm khu (NAV_KEY), không kiểm tab con. Đã thêm assertion
  `tools_nhat_ky_tien_do == PROGRESS_TAB_LABEL`, cộng 2 test mới: một kiểm form
  "Đầu vào (pre-test)" thật sự hiện sau khi bấm, một kiểm nhãn khớp tiêu đề tab và
  không phải feature id.
- **Đã kiểm chứng test bắt được lỗi:** gỡ fix điều hướng → đúng 2 test đỏ
  (`test_first_tour_finish_marks_seen_and_navigates`,
  `test_tour_finish_lands_on_the_tab_that_has_the_diagnostic_form`); khôi phục → xanh.
- 787 passed. Commit `1480f6b`.
- **Bẫy đã gặp:** dòng `tools_<area>` trong `st.session_state` là **nhãn tab**, không
  phải feature id. `navigate_to` nhận label trực tiếp vì
  `lmode.FEATURES.get(feature, {}).get("label", feature)` giữ nguyên chuỗi lạ.

**Còn nợ (người dùng hoãn):** hệ thống nộp bài bằng Firebase. Cần chốt 4 điều trước
khi code: (1) project Firebase đã có chưa, (2) định danh học sinh bằng gì — hiện app
cố ý không hỏi họ tên/ngày sinh, (3) ai được đọc dữ liệu để viết Security Rules,
(4) đã có đồng ý của phụ huynh chưa (Nghị định 13/2023/NĐ-CP về dữ liệu cá nhân,
đặc biệt với người chưa thành niên). **Không tự dựng hạ tầng lưu dữ liệu học sinh
khi chưa có 4 câu trả lời này.**

## 0z. Bổ sung 24/10/2026 (khuya) — lớp dẫn đường onboarding, 4 commit, đã lên production

Bốn việc làm rời, mỗi việc một commit revert được độc lập:

| Commit | Nội dung | Test |
|---|---|---|
| `01b164f` | Microcopy thật thà: guide bỏ "Nhập điểm…", caption nói rõ pre/post giống nhau là cố ý, cổng vốn thật chỉ sang Danh mục mô phỏng | +3 (746) |
| `f4acb8c` | Checklist "Hành trình lần đầu · 0/5" trên Tổng quan, đọc tiến độ thật, tự ẩn khi đủ 5/5 | +3 (749) |
| `e86b4c4` | Tour 4 bước `@st.dialog`, tự mở khi hồ sơ còn trống, cờ `seen_tour` lưu trong hồ sơ | +3 +1 (753) |
| `cab3821` | Bảng "Tab nào — khi nào" cuối Tổng quan, đủ 5 khu vực, lấy nhãn từ `lmode.AREA_LABELS` | +1 (754) |

- **Backup về bản cũ**: tag `pre-onboarding` (= `7fe9717`, đã push lên origin) và zip
  `C:\Users\ADMIN\quant-app-backups\quant-app-pre-onboarding-20261024_1927.zip`.
  Về lại một nửa: `git revert e86b4c4` / `cab3821` tuỳ ý.
- **Bẫy đã dính — đọc trước khi thêm khoá vào hồ sơ**: `seen_tour` là bool và
  `_profile_has_content` (progress_store.py) coi `False is not None` là hoạt động, nên
  hồ sơ mới tinh bị tưởng là "đã có dữ liệu" và **ghi đè tiến độ đã lưu**. Đã sửa:
  `_means_activity` xử lý `bool` riêng (chỉ `True` mới tính). Thêm khoá kiểu bool
  khác vào schema phải theo đúng mẫu này.
- **Schema vẫn là 2**: `seen_tour` thêm vào `TOP_LEVEL_KEYS`, `empty_profile`,
  `export_json`, `import_json` (`.get("seen_tour") is True`) — file JSON cũ vẫn nạp
  được, file mới để lạc cũng vẫn đọc được.
- **Không có test hồi quy cho UI thật**: AppTest kiểm được sự tồn tại + điều hướng của
  nút trong tour, nhưng bấm nút cuối tour trên trình duyệt thật chưa kiểm được bằng
  cloud browser (synthetic event không tới Streamlit, CDP bị chiếm profile). Production
  đã xác minh phần mở tour, đủ 4 bước, đóng tour, và **không mở lại** sau reload.
- **Lỗi thật đã sửa ở `2cbe4e5` — đọc kỹ, rất dễ tái phát**: `st.dialog` chạy như
  **fragment**, bấm nút bên trong dialog chỉ rerun riêng dialog đó, thanh tab phía sau
  không dựng lại. Bản tour đầu gọi `navigate_to()` mà quên `st.rerun()`, nên bấm "Đi
  làm bài Đầu vào" thì `seen_tour` và `NAV_KEY` đổi đúng trong state mà màn hình vẫn
  đứng ở Tổng quan. **AppTest không bắt được lỗi này** vì nó luôn rerun cả app — test
  cũ vẫn xanh. Test mới khoá hợp đồng bằng cách monkeypatch `st.rerun` và đòi đúng 1
  lần gọi; đã kiểm chứng bằng cách bỏ `st.rerun()` thì test đỏ. Mọi nút trong
  `st.dialog` mà cần đổi thứ ngoài dialog (đổi tab, đổi trang) đều phải `st.rerun()`.
- **Deploy 24/10 khuya phải Reboot tay**: log báo "Updated app!" nhưng nội dung vẫn
  bản cũ; Reboot app trong menu ⋮ rồi mở tab mới thì đúng bản mới. Gặp lại thì làm
  đúng thế, đừng revert code.
- **Đóng bớt tab khi verify**: mở 6–7 tab app cùng lúc làm cloud browser treo
  (`browser.evaluate` timeout 60s). Giữ 1–2 tab là đủ.

## 0. Bổ sung 24/10/2026 — tự lưu tiến độ vào trình duyệt (Nấc 1) + QA điện thoại/máy tính bảng

- Tiến độ học giờ **tự lưu vào localStorage của trình duyệt** (key
  `quantapp.progress.v1`): đóng tab, mở lại là điểm bài quay về, kèm banner
  "🔄 Đã khôi phục tiến độ học trên máy này — N bài đạt". Không email, không
  đăng nhập, không gửi dữ liệu cá nhân lên máy chủ.
- File mới: `progress_store.py` (đọc/ghi/khôi phục; ngưỡng đạt PASS_SCORE=70;
  khôi phục đúng 1 lần/phiên, chỉ khi hồ sơ phiên còn trống, dữ liệu đi qua
  `progress_profile.import_json` — hỏng là bỏ cả hồ sơ, không cố sửa) và
  `components/qa_progress_store/index.html` (component ẩn 0px, giao tiếp bằng
  giao thức postMessage chuẩn của Streamlit Components, apiVersion 1, không
  thêm gói pip — CDN streamlit-component-lib chỉ có ESM nên không nạp nổi qua
  thẻ script). `app.py` gọi restore trước sidebar và persist ở cuối file;
  `learning_ui.py` thêm banner khôi phục + viết lại caption "Sao lưu hồ sơ".
- **Ba lần fix liên tiếp 24/10, đều do QA sống trên production bắt được**
  (bài học: xác nhận sau push phải chờ build thật sự lên rồi mới tính — lần
  xác nhận "thành công" đầu tiên chạy khi Cloud vẫn đang chạy build cũ):
  `c7da49d` — cờ phiên khôi phục bị áp ngay lần chạy đầu, khi component còn
  chưa kịp gửi giá trị (Streamlit cần thêm một rerun để nhận postMessage);
  giờ chỉ áp cờ khi đã nhận được dict. `c3730e7` — **nguyên nhân rễ**: host
  Streamlit (`ComponentRegistry.ts`) bỏ lặng lẽ mọi postMessage thiếu cờ
  `isStreamlitMessage: true`, nên component tự viết câm hai chiều
  (componentReady/render/setComponentValue/setFrameHeight đều không tới nơi);
  mọi message giờ đóng gói đúng như `component-lib/src/streamlit.ts`, và các
  lần gửi sau khôi phục được dedupe bằng so sánh chuỗi. `5037501` — lần chạy
  đầu mỗi phiên từng ghi đè hồ sơ rỗng lên dữ liệu đã lưu ngay khi kênh message
  sống lại; `persist_progress` giờ từ chối ghi khi `_profile_has_content` trả
  False (dict/list rỗng + null = chưa có hoạt động; điểm 0.0 thật vẫn tính).
- Lưu ý thật thà: message commit `c7da49d` mô tả sai mức hại — ghi "chỉ làm
  banner không hiện" trong khi thực tế khi đó khôi phục KHÔNG hề hoạt động
  (cả hai lỗi cờ lẫn giao thức) cho tới `c3730e7`. Không có dữ liệu học sinh
  nào mất: tính năng sống chưa đầy một giờ, chưa ai dùng, JSON xuất tay vẫn
  là sao lưu chính thức.
- Trạng thái verify trên production: khôi phục đầu-cuối xác nhận 2 lần độc
  lập trên 2 trình duyệt (banner DOM thật + "Đã đạt 2/4" + "Điểm gần nhất
  85/100" hiển thị lại đúng bài; banner chỉ hiện 1 lần render nên dễ thoát
  khỏi khung ảnh chụp — bằng chứng DOM là đủ). Save-path ghi theo render
  event: chỉ re-fire khi args đổi hoặc component được mount lại (đọc trong
  `ComponentInstance.tsx`: deps gồm `jsonArgs` dưới dạng chuỗi) — rerun với
  payload giống hệt sẽ KHÔNG ghi lại, nên đụng vào localStorage giữa chừng
  không tự hồi phục; đó là hành vi Streamlit chuẩn, luồng HS thật (điểm bài
  đổi → args đổi) vẫn ghi bình thường.
- **Quy tắc QA storage**: phải mở ĐÚNG 1 tab production. Multi-tab cùng
  origin dùng chung localStorage, và session cũ reconnect (khi Cloud deploy
  lại) sẽ rerun rồi ghi đè chéo — đã từng có 5 tab lạc làm hỏng cả chuỗi
  nghiệm.
- **Giải mã chuỗi zeros-299 trong storage** (bản ghi cũ ở đây sai — nó KHÔNG
  phải dấu hiệu "build cũ"): chuỗi `~299` ký tự = payload rỗng canonical
  (~258) + khối `"self_reflection_scores":{"lap_luan":0,"rui_ro_nguon":0,
  "nhat_ky":0}`. Nguồn: `learning_ui.py` gán `reflection[key] = value` của
  number_input (mặc định 0.0) **ngay lúc render**, mà `st.tabs` chạy mã của
  mọi tab kể cả tab ẩn → mỗi rerun hồ sơ trống đầy zeros → `_profile_has_content`
  coi `0 is not None` là "có hoạt động" → guard `5037501` bị vô hiệu → persist
  ghi zeros-299 đè storage ở run-1 mỗi phiên. Chuỗi này sinh được trên chính
  HEAD, nên hành vi storage không phân biệt được build `c3730e7` và HEAD.
  Component file là **3098 bytes** byte-identical local/live, nhưng file đó
  không đổi từ `c3730e7` nên đối chiếu byte cũng không phân biệt được build.
- **Fix bug #4 (24/10, sau chuỗi 3 fix trên)**: bỏ side effect zero-fill —
  `learning_ui.py` chuyển gán `reflection[key] = value` sang callback
  `on_change` (`_record_reflection`) nên hồ sơ chỉ nhận giá trị khi người học
  thật sự đổi số; hồ sơ trống giữ nguyên là trống, guard chống ghi đè rỗng
  hoạt động đúng lại. Ngữ nghĩa "điểm 0 hợp lệ" được giữ: điểm 0 do người học
  thao tác thật thì vẫn ghi; chỉ dừng việc render tự điền 0. Regression:
  2 test AppTest mới trong `tests/test_learning_flow.py` (render không tự-fill;
  đổi input thì ghi và persist).
- **Kỹ thuật QA phiên mới trên production (chuẩn hoá)**: (1) Navigate tab
  thẳng `https://quant-app-…streamlit.app/~/+/` — app nhúng trong iframe của
  Cloud, outer shell không thấy stApp; (2) click tab ứng dụng bằng
  `DIV[role="tab"]` (click phần tử con như STRONG không ăn); (3) **canary** —
  ghi vào storage một hồ sơ có top-key lạ `"canary"` (bị `import_json` từ chối
  vì key lạ) rồi reload: canary bị đè = bug ghi-đè còn sống, sống sót = guard
  hiệu lực; tái hiện 100% mỗi phiên mới trước fix. Lưu ý race còn tồn tại:
  component khôi phục đọc storage lúc mount và gửi postMessage, restore dùng
  giá trị widget (không re-read storage) — dữ liệu "tự hồi phục" nhờ read-early
  thắng race persist; sau khi fix #4 deploy, writer tự động không còn: race chỉ
  còn nếu học sinh nộp bài trước rerun đầu tiên kịp nhận giá trị component.
- ✅ **Đã verify sau deploy (tối 24/10)**: auto-deploy từng kẹt 3 lần canary
  (gen 10–12) — vào share.streamlit.io → menu app → **Reboot** (nút trong
  dialog xác nhận) kích lại container; sau reboot: canary `qa_postreboot_r1`
  SỐNG SÓT qua reload (286 bytes, không zeros), e2e restore đạt ("Đã đạt 2/4"
  + "Điểm gần nhất 85/100"), storage giữ scores và `self_reflection_scores`
  rỗng sạch. Lưu ý UI Cloud: menu row app (Reboot/Delete/Analytics/Settings)
  ẩn trong nút kebab cuối bảng app; click link tên app thì mở app URL bản
  mới, không phải trang quản lý.
- **Tệp JSON xuất tay vẫn là sao lưu chính thức** (tab "Nhật ký và tiến độ")
  vì iOS Safari có thể xoá localStorage sau ~7 ngày không truy cập; đổi máy,
  đổi trình duyệt hoặc xoá dữ liệu trình duyệt là mất.
- Nấc 2 (kế hoạch, chưa làm): mã lớp 6 ký tự để ghép lớp + cân nhắc lưu đám
  mây (Supabase/Neon) khi cần ghép tiến độ giữa các máy.
- QA hiển thị (giả lập Chrome DevTools trên production): điện thoại
  390×844×3 (tab Tổng quan + Lộ trình học) và máy tính bảng 768×1024×2 —
  sidebar tự thu hamburger, tab wrap 2 cột, không tràn ngang
  (scrollWidth = innerWidth), nút/selectbox/progress bar hiển thị đủ.
  **Không cần sửa CSS**: `@media 768px` và flex-wrap sẵn có đã đạt.
- Quirks kiểm thử chrome-devtools (nhớ để lần sau đỡ lost time): `emulate`
  đổi viewport lần đầu thường ném "Navigation timeout" nhưng áp dụng vẫn
  thành công — verify bằng `window.innerWidth` rồi làm tiếp; `take_screenshot`
  có thể timeout ngay sau rerun — evaluate nhẹ 1 nhịp rồi chụp lại; script
  evaluate trả CHUỖI thì khối json bị bọc ngoặc kép (JSON.parse 2 lần), trả
  OBJECT literal thì parse 1 lần — nhầm là `Number()` ra NaN lặng lẽ. Mở
  expander bằng CDP click: lấy uid mới từ `take_snapshot` ngay trước mỗi click
  (uid đổi sau rerun); check đã mở bằng icon `keyboard_arrow_down` + chiều
  cao khối, đừng check thuộc tính `open`.
- Quirks browser tích hợp (`browser.*`): `evaluate` nhận tham số `script`
  (không phải `code`) và trả sẵn object `{tab, value}`; `screenshot` bắt buộc
  cửa sổ desktop visible — khi cửa sổ ẩn thì chụp pixel bằng chrome-devtools
  thay thế; MCP chrome-devtools có thể chết giữa phiên (timeout — phải
  reconnect từ /mcps), mọi việc DOM/localStorage làm trọn với browser tích
  hợp, chỉ riêng chụp ảnh mới cần CDP.
- Test: **742 passed** (734 + 8 khi thêm bài m7_AI dự báo — chi tiết ở mục
  0a; full suite ~93s).

## 0a. Bổ sung 24/10/2026 (đêm) — bài học m7 "AI dự báo thị trường" (Kronos)

- Thêm `m7_ai_du_bao` (order 11, bài cuối LESSONS, không gắn SGK nên là
  "current" cho mọi lớp 10/11/12 và cả sinh viên): mức học liệu thuần,
  KHÔNG chạy model trong app. Mạch nội dung: máy đọc nến như ngôn ngữ
  (12 tỷ nến/45 sàn), dải xác suất ≠ chắc chắn (66,7% → hai phiên độc lập
  0,667² ≈ 44,5%), giới hạn model học từ quá khứ, trách nhiệm người dùng.
  Disclaimer ghi rõ trong bài: +93% RankIC là con số tác giả tự báo cáo
  (chưa kiểm chứng độc lập), demo chạy BTC/USDT chỉ minh họa.
- Nhánh tương tác mới `INTERACTIVE_AI_LINK` = `"link_ai_ngoai"` + constant
  `KRONOS_DEMO_URL` trong curriculum.py; render bằng `st.link_button` tới
  demo GitHub Pages + caption disclaimer trong `_render_thpt_practice`
  (learning_ui.py). Quirks đã verify: `st.link_button` KHÔNG có tham số
  `key`; AppTest không có getter riêng — đọc qua `at.get("link_button")`
  (trả `[UnknownElement()]`, đếm len được).
- Test đổi theo 11 bài: EXPECTED_IDS + m7, orders `range(1, 12)`, test đếm
  bài đổi tên `test_eleven_modules_in_declared_order` (+assert m7 `sgk_grade
  is None` nằm cuối), tổng câu chặn 18–44 (38+4) đổi tên test tương ứng,
  split lớp: lop_10 9/2, lop_11 10/1, lop_12 11/0 (thêm 1 bài chính mọi lớp);
  test practice-action có nhánh riêng AI_LINK; thêm `test_render_ai_
  forecasting_lesson_with_demo_link`. Copy expander đại học "mười bài" →
  "mười một bài". **742 passed (~93s)**.
- ✅ Verify production auto-deploy (`03b1dd7`, KHÔNG cần Reboot lần này):
  caption lộ trình "Bài 1/11" xác nhận 11 bài; bấm "Bài tiếp theo" 10 nhịp
  tới "Bài 11/11": title "AI dự báo thị trường" render, link button
  `Mở demo Kronos (mở tab mới)` đúng href demo GitHub Pages + `target="_blank"`,
  caption disclaimer BTC/USDT + "+93% RankIC" + "khuyến nghị giao dịch" hiện
  đủ; storage sau chuỗi 10 rerun vẫn 299 bytes (scores m1 85 / s1 90,
  `self_reflection_scores` `[]`) — fix #4 vẫn giữ. Quirk QA: dropdown
  Streamlit selectbox trên production mở qua evaluate chỉ thấy 1 option
  (portal ảo hóa) và tắt giữa hai nhịp evaluate — điều hướng dùng nút
  "Bài tiếp theo" ổn định hơn.
- ✅ Verify responsive m7 bằng **iframe rig** (kỹ thuật mới, dùng lại được
  khi không có tool viewport và chrome-devtools MCP chết): tiêm vào 1 tab
  popup `<iframe style="width:390px;height:844px;border:0" src="<app-url>/
  ~/+/">`; media query trong iframe phản ứng theo width thật của iframe
  (same-origin nên `contentDocument` đọc được trực tiếp). Nhắc: popup
  `window.open(..., 'width=390')` BỊ OS bỏ width (thành 1000px) — đừng dùng
  để emulate. Kết quả cả hai bề ngang, KHÔNG sửa CSS:
  - **390×844** (điện thoại): `matchMedia('(max-width: 768px)')` và
    `(max-width: 480px)` cùng matches, `scrollWidth - clientWidth == 0`
    qua mọi nhịp điều hướng Bài 1→11; Bài 11/11 render đủ title +
    disclaimer; link button 202×40px tại x=16, right=218 (tap target chuẩn
    40px, nằm gọn trong 390).
  - **768×844** (máy tính bảng, giá trị biên): `media768` vẫn matches đúng
    (max-width: 768px gồm đúng 768), `media480` tắt đúng, `overflowX == 0`
    tại Bài 11/11, link button 202×40px visible. Lưu ý: đây là render
    Chromium chuẩn media query, không phải chạm thật trên iOS/Android.
  - Sau QA: storage tab production chính vẫn 299 bytes (không zeros); tab
    rig đã đóng, khôi phục quy tắc 1 tab production.
- Bổ sung 24/10 (khuya): `st.info` hướng dẫn nguồn file backup ngay trên ô
  upload Danh mục mô phỏng (nhánh `ledger is None` trong
  `render_paper_portfolio`): người mới thấy "Chưa từng tạo danh mục? Bỏ qua
  ô tải file..." + giải thích file JSON do nút 💾 xuất, tên
  `quant_app_paper_YYYYMMDD_HHMMSS.json`. Có AppTest
  `test_paper_portfolio_without_ledger_explains_backup_source` (assert info
  + uploader + nút init) — **743 passed (~5m25s)**, commit `55297b7`.
  **ĐÃ verify production (24/10 tối)**: container cũ treo ~35 phút; sau đó
  user đăng nhập dashboard thành công → bấm ⋮ (data-testid=app-menu) →
  Reboot → xác nhận dialog → app sống lại ~2–5 phút sau. Đo tab production:
  vào Đầu tư → Danh mục mô phỏng thấy đúng nội dung info (so khớp nguyên
  văn "Chưa từng tạo danh mục? Bỏ qua ô tải file bên dưới..."). Nợ này
  ĐÃ XONG. Lưu ý thao tác: kebab menu share.streamlit.io chỉ bấm được bằng
  driver click (browser.click với ref từ browser.snapshot), JS click giả
  không mở menu.

## 0b. Bổ sung 23/10/2026 (tối) — nhịp lộ trình theo lớp + đọc trước đại học

- Người học chọn **lớp 10/11/12** giờ thấy lộ trình chia đúng ba nhóm:
  **lộ trình chính** giữ nguyên nhịp dự án (6 bài tài chính + bài SGK năm nay
  📚 + bài nền năm trước 🧱), nút "Tiếp tục bài chưa đạt" và thanh tiến độ
  chạy trên nhóm này; bài SGK **lớp trên** gập vào expander "📖 Học trước
  chương trình" — mở ra vẫn làm và chấm, điểm vẫn tính vào cổng nâng cao.
  Lớp 12 là lớp cao nhất nên KHÔNG có mục học trước: s4 là bài năm nay nằm
  trong nhóm chính (📚 10). Sinh viên, "Khác" và track đại học không chia.
- Cách làm: field `sgk_grade` trong `curriculum.Lesson` (cố ý không đặt tên
  `grade` vì trùng method chấm điểm `Lesson.grade`); hàm
  `curriculum.lesson_phase(sgk_grade, my_grade)` phân loại
  current/foundation/ahead; `learning_ui` tách `_render_lesson_track` thành
  wrapper chia nhóm + thân chung `_render_track_body`, helper
  `_split_track_lessons`. Phương án A buổi chiều (đềo bài SGK đúng lớp lên
  đầu) đã bị phương án C thay thế hành vi; tên hàm promote đã xóa.
- **Đọc trước kiến thức đại học cho học sinh cấp 3**: module mới
  `university_teen.py` "dịch" cả 6 bài đại học thành bốn phần — nói dễ
  hiểu, ví dụ tính tay được, ứng dụng gần gũi, câu phản tư. Hiển thị ở
  expander "🎓 Kiến thức đại học — đọc trước nếu em tò mò" cuối trang Lộ
  trình học (chế độ THPT). Chỉ đọc: không chấm, không nút trỏ tới công cụ
  nâng cao — công cụ chuyên sâu vẫn phải qua cổng 4 bài; nơi nhắc tới công
  cụ nâng cao đều ghi rõ điều kiện. Lộ trình đại học giữ nguyên văn phong
  giáo trình, sinh viên không thấy mục này.
- Cổng mở công cụ nâng cao "bất kỳ 4 bài nào ≥70/100" giữ nguyên ý nghĩa;
  chấm điểm ghi theo lesson_id nên mọi tiến độ cũ được bảo toàn.
- Dọn nốt chuẩn Streamlit 1.60: 4 chỗ `use_container_width` còn lại (app.py:
  2 biểu đồ giá trong phiên + bảng lệnh khớp; muse_brief.py: link_button AI)
  chuyển sang `width="stretch"`. Từ giờ không còn chỗ nào dùng cờ cũ.
- Secrets đã chốt: chủ dự án dán `[shared_ai]` vào Secrets dashboard của app
  production (tối 23/10). App xác nhận đang chạy qua ảnh chụp browser thật của
  chủ dự án. Key dùng chung nằm duy nhất trong Secrets Cloud — KHÔNG ghi vào
  bất kỳ file nào trong repo; tham chiếu cấu hình xem `.streamlit/secrets.example.toml`.
- Test: **717 passed** (thêm test của C: chia nhóm đúng cho 3 lớp — 8+2,
  9+1, 10+0 —, ba nhãn 📚🧱📖, bài lớp trên vẫn tính cổng mở; thêm test của
  tính năng đại-học-cho-THPT: phủ sáu bài × bốn phần, mục có mặt ở track
  THPT và vắng ở track đại học; chạy `.venv` 3.12).
- Quirk kiểm thử nhớ nhá: AppTest của Streamlit — sau mỗi `.run()` phải
  lấy lại node widget (`at.selectbox(key=...)`) trước khi `set_value` tiếp;
  dùng node cũ qua hai lần run gây KeyError lạ trên key widget của bài khác.
- Việc còn mở (không gấp): nhờ học sinh thật xác nhận trên production —
  (a) đổi lớp thấy đúng ba nhóm với dấu 📚🧱📖; (b) mục 📖 gập mặc định,
  mở ra vẫn chấm được; (c) mục 🎓 đủ sáu bài × bốn phần dễ đọc; (d) thanh
  bên mặc định "AI dùng chung (cấp sẵn của trang)"; (e) bảng tần suất hiển
  thị đủ chữ "Không đổi"/"Số phiên".

## 0c. Bổ sung 23/10/2026 (chiều) — trọn bộ thống kê phổ thông (Toán 10–12)

- Gói "Trọn bộ ngay": 4 bài học thống kê bám SGK Kết nối tri thức theo
  Chương trình 2018 — s1 Số gần đúng và sai số (Toán 10, Bài 12), s2 Số đặc
  trưng đo trung tâm và độ phân tán (Toán 10, Bài 13–14), s3 Mẫu ghép nhóm và
  số đặc trưng trung tâm (Toán 11, Bài 8–9), s4 Độ phân tán của mẫu ghép nhóm
  (Toán 12, Bài 9–10). Tổng 10 bài / 38 câu chấm cục bộ, nguồn dẫn SachMem +
  Thông tư 32/2018.
- 3 công cụ tương tác trong tab Khám phá dữ liệu (luôn mở ở chế độ THPT):
  Máy tính số đặc trưng (`stats_calc`), Phòng thí nghiệm ghép nhóm
  (`grouping_lab`), Bảng tần suất hai chiều và biểu đồ (`freq_table`).
  `freq_table` chưa nạp dữ liệu thì tự dùng bộ mô phỏng 260 phiên, có ghi rõ.
- Tính toán gom hết vào `stats_tools.py` mới (hàm thuần dữ liệu được unit test
  riêng; hàm render chỉ dựng giao diện). Quy ước thống kê: tứ phân vị theo
  trung vị nửa trái/phải, phương sai chia n, mẫu ghép nhóm dùng giá trị đại
  diện là trung điểm (một số bộ SGK gọi "tổ trọng tâm" — đã ghi chú caution vì
  các bộ sách có thể lệch nhẹ).
- Mối nối chéo cho học sinh: ghép nhóm ↔ sai số (s3 nối s1), "Biến động năm
  hóa = s·√252" ở tab Đầu tư ↔ độ lệch chuẩn (s2/s4), mỗi bài có 4 nhánh thực
  hành tương tác ngay trong trang bài học.
- Sau review chủ dự án, mọi chỗ **dùng** kiến thức thống kê chạy đủ mạch học
  4 bước trong `stats_tools.py`: `theory_lead` (dẫn dắt lý thuyết 1 phút) →
  "Bước 1 — tự tính trên giấy" (ô dự đoán x̄/s/x̄g so máy, đoán mã tăng nhiều
  nhất trước khi vẽ) → `meaning_block` (HS viết ý nghĩa trước, đáp án mẫu theo
  khung câu, model answer động theo số vừa tính) → `reflection_block` (phản tư
  đào sâu, mỗi câu hỏi ẩn lời giải riêng). Áp ở 3 tab Khám phá dữ liệu, 4 nhánh
  thực hành s1–s4 trong trang bài học, và expander "Toán đằng sau Biến động
  năm hóa" ở tab Đầu tư.
- Sau duyệt của chủ dự án, 10 bài **xen kẽ theo nhịp làm dự án** (không còn
  block thống kê ở cuối): m1, m2, m3, s1, s2, m4, s3, m5, m6, s4 — bài thống
  kê đặt đúng lúc dự án cần (sai số sau dự báo, phân tán trước rủi ro, ghép
  nhóm trước biểu đồ, so giai đoạn sau mô phỏng). Cổng mở công cụ nâng cao
  "bất kỳ 4 bài nào ≥70/100" không đổi, không phụ thuộc thứ tự.
- Test: **707 passed** (thêm `tests/test_stats_tools.py` 22 test tính tay khớp
  SGK: s²=2.96; An/Bình 1.045/0.045; mẫu 0..9 ghép k=5 mean 4.5, s²=6.48).
  AppTest chạy thật app hai chế độ + từng công cụ, không exception.
- (Dòng "còn chờ dán secrets" đã gỡ: xem mục 0a ở trên — đã dán xong tối 23/10.)

## 0d. Bổ sung 23/10/2026 (sáng) — luồng AI dùng chung (cấp sẵn của trang)

- Học sinh **không cần API key riêng**: thanh bên mặc định chọn "AI dùng chung
  (cấp sẵn của trang)". Cấu hình đọc từ `[shared_ai]` trong **Secrets của
  Streamlit Cloud** (chỉ chủ app nhập; tuyệt đối không dán key vào repo công
  khai). Mẫu cấu hình: `.streamlit/secrets.example.toml`.
- Luồng dùng giao thức **OpenAI tương thích** (`POST {base_url}/chat/completions`)
  qua `urllib` chuẩn trong `analytics._openai_compatible_chat` — không thêm
  dependency mới. Mọi lỗi gọi AI vẫn đi qua `_friendly_llm_error`, key luôn
  được che thành `[REDACTED]`.
- Học sinh có key riêng vẫn chọn luồng của em: Anthropic / Gemini / Agents AI
  như cũ, hoặc mục mới "Router riêng của em (key riêng)" — máy chủ tương thích
  OpenAI, nhập full key + base URL + model.
- ⚠️ Máy chủ AI chạy CLI trên máy local (9router loopback 127.0.0.1) **không
  truy cập được từ Streamlit Cloud**; Secrets phải dùng endpoint HTTPS công khai.
- Test: **642 passed** (bổ sung `tests/test_shared_ai.py` và 4 test cho luồng
  OpenAI tương thích trong `test_analytics.py`). Chạy bằng `.venv` (3.12).
- Đã thử sống endpoint dùng chung (GLM 5.3 Flash): HTTP 200, trả lời đúng.
  Model suy luận cần ngân sách token đủ (~300 token cho phần suy nghĩ chỉ với
  một câu chào), nên code đặt `max_tokens=2048` và có lỗi thân thiện khi máy
  chủ tiêu hết ngân sách trước khi trả lời.
- Đã push `92050e5` (feature AI dùng chung). Sau push, app production văng
  **ImportError** nhưng code không lỗi: tái hiện bằng venv sạch Windows
  (`requirements.txt` + `python -c "import app"`) lẫn Docker Linux
  (`python:3.12-slim` và `3.13-slim`) — mọi module gốc import RC 0. Chẩn đoán
  cuối: **môi trường build trên Cloud bị corrupt**, không phải code.
- Xử trí: push `7a11825` (commit rỗng) chưa hết vì build tái dùng cache cũ;
  push `df8a6c4` bật tạm `showErrorDetails="stacktrace"` đã ép build sạch và
  app **chạy lại bình thường** (đã soi lần đầu, khối AI ở sidebar hiện đủ 6
  lựa chọn). Đã revert `showErrorDetails` trong commit sau — đừng bật nếu
  không có sự cố.
- ✅ Đã dán xong (tối 23/10, xem mục 0a): `[shared_ai]` nằm trong Secrets
  dashboard app production. Sidebar giờ tự mặc định "AI dùng chung (cấp sẵn
  của trang)" khi học sinh chưa có key riêng.

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
# 1. Bộ test (732 test, ~5 phút trên máy này)
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
- `tests/` — 742 test, không cần mạng.

## 6. Lịch sử

- 2026-07-24: commit đầu.
- 2026-08-03: `854387d` — né NumPy thiếu wheel cp314 bằng cách hạ `vnstock` xuống 4.0.2.
- 2026-10-16: `59ad66b`, `e9eac4e` — PyPI gỡ vnstock, chuyển sang kho chính thức; đổi sang
  4.0.9 + ezchart 1.0.2 và **vô tình đưa ràng buộc `numpy<2.3` trở lại** → app chết.
- 2026-10-23: thêm `--only-binary=numpy`, ghi lại chẩn đoán này.
- 2026-10-23: luồng AI dùng chung (`92050e5`); trọn bộ thống kê phổ thông
  (4 bài s1–s4 + 3 công cụ, `stats_tools.py` mới).
- 2026-10-23: `f5d89c7` — xen kẽ 10 bài theo nhịp dự án (sau review chủ dự án);
  `8fa45e6` — mạch học 4 bước (dẫn dắt → tự tính → ý nghĩa → phản tư) cho 3 tab
  công cụ, 4 nhánh thực hành s1–s4 và "Toán đằng sau Biến động năm hóa". Đã
  verify trên production (app chạy trong iframe `/~/+/` của Cloud): thứ tự bài
  1→6 đọc trực tiếp đúng (m1, m2, m3, s1, s2, m4), 3 tab + trang bài s1 hiển thị
  đủ mạch mới; 708 test pass.
- 2026-10-23: `84daceb` — tab "Soạn học liệu với Muse" đổi thành "Soạn học liệu
  với AI": Muse chỉ là một lựa chọn, có thể bị chặn tại VN; thêm st.info chú
  thích + 5 nút link AI (Muse/ChatGPT/Gemini/Copilot/Zalo AI), file tải về
  `hoc_lieu_…md`, 2 dòng "Nhờ Muse…" tổng quát thành "Nhờ AI bên ngoài…".
  Key widget `muse_*` giữ nguyên. 709 test pass.
- 2026-10-23: `c62bbca` — sidebar "Kết nối AI": mỗi provider có key riêng
  (Claude, Gemini) được thêm nút link lấy API key + hướng dẫn từng bước +
  caption gợi ý chọn model; cập nhật model dòng 10/2026 (Claude 5.5:
  sonnet-5-5 mặc định, haiku-5-5, opus-5-5, fable-5-1; Gemini: gemini-3.8-flash
  mặc định, gemini-4-argon, 3.6-flash, 3.5-flash-lite, 3.1-pro-preview; bỏ ID
  không tồn tại "gemini-3.5-flash"); note quota mở rộng cho gemini-4-argon.
  `DEFAULT_GEMINI_MODEL` giữ nguyên. Nguồn ID: docs chính thức Google
  (ai.google.dev, 22/10/2026) và platform.claude.com (23/10/2026).
  Verify: 709 test pass + AppTest độc lập (options/default/link/guide/caption
  quota bật đúng cho pro & argon, tắt cho flash). **Lưu ý verify:** khi mở app
  production trong iframe `/~/+/` của harness browser, sidebar không được
  mount (chỉ có main content, kể cả sau reload cứng) — dùng app chạy local
  (`streamlit run app.py`) hoặc trình duyệt người dùng để soi sidebar; đây là
  quirk của embed, không phải lỗi code.
- 2026-10-23: chất lượng câu hỏi học tập + fix mất chữ: (1) `meaning_block`
  thêm tham số `frame` — giàn giáo câu điền khuyết ("Mã ___ có ___ phiên tăng
  trên tổng ___ phiên (khoảng ___%)…") hiển thị st.info riêng dưới dòng gợi
  ý, HS yếu điền số vào là xong; (2) viết lại câu hỏi/gợi ý/phản tư của 3
  công cụ thống kê (stats_calc, grouping_lab, freq_table trong stats_tools),
  4 nhánh thực hành s1–s4 (learning_ui) và expander Biến động năm hóa
  (investment_ui): câu ngắn, kèm ví dụ cụ thể, thuật ngữ giải thích tại chỗ
  (số thô, chọn cổ phiếu, dữ liệu phân loại, nội suy, trung vị, áp đảo…);
  câu hỏi "Nêu ý nghĩa" của bảng tần suất đổi từ "phần chọn mã của báo cáo
  dự án" sang yêu cầu 2 câu kèm ví dụ + giàn giáo điền khuyết; (3) fix mất
  chữ bảng: bảng tần suất hai chiều trải full chiều rộng + `column_config`
  đặt cứng px ("Không đổi" 115px, "Số phiên" 100px — hết bị cắt "Khô…"),
  bảng ghép nhóm và bảng so sánh cũng đặt cứng độ rộng + định dạng số
  (%.4g/%.2f), hai biểu đồ chuyển xuống hàng dưới đặt cạnh nhau; (4) dọn
  deprecation Streamlit 1.60 trong stats_tools: 6 chỗ `use_container_width`
  đổi sang `width="stretch"` (dataframe) hoặc bỏ (plotly mặc định stretch);
  còn 4 chỗ cũ app.py (3) + muse_brief.py (1) — follow-up. Verify: 709 test
  pass; render local qua DOM xác nhận câu hỏi/giàn giáo/gợi ý mới; KHÔNG soi
  được pixel trong harness (thiếu WebGL nên canvas không vẽ, screenshot cần
  cửa sổ desktop visible) — cần ai đó xem bảng hiển thị đủ chữ "Không đổi",
  "Số phiên" trên production bằng browser thật.
- 2026-10-24: `83af12e` — Nấc 1 tự lưu tiến độ học vào localStorage trình
  duyệt (`progress_store.py` + `components/qa_progress_store/index.html`);
  QA điện thoại 390px và máy tính bảng 768px đạt, không đổi CSS.
- 2026-10-24: `c7da49d`, `c3730e7`, `5037501` — chuỗi fix Nấc 1 (cờ khôi phục
  chờ giá trị; cờ `isStreamlitMessage` cho mọi message component; chặn ghi đè
  hồ sơ rỗng), chi tiết ở mục 0; `1534cd4` — HANDOFF lần 1; `3444f3b`,
  `ab0a4d1` — kích deploy + HANDOFF lần 2/3; `3f4e834` — fix bug #4
  zero-fill (bỏ side effect render, chuyển sang callback on_change; 734 test);
  verify production sau Reboot: canary `qa_postreboot_r1` sống sót, e2e
  restore 2/4 mô-đun + 85/100 đạt; `5e7051c` — HANDOFF ghi kết quả verify.
- 2026-10-24: `03b1dd7` — bài học m7 "AI dự báo thị trường: dùng máy, giữ
  trách nhiệm" (Kronos, mức học liệu, order 11, link demo ngoài); 742 test
  pass; chi tiết ở mục 0a.
