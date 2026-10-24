# HANDOFF — Quant App

**Cập nhật**: 2026-10-24 · **Repo**: https://github.com/congapro60-dev/quant-app · **Branch chuẩn**: `master` · **Production**: https://quant-app-nnqcr8uwb6mjyonxod8nzu.streamlit.app

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
  thắng race persist; đến khi fix #4 deploy, race window vẫn là rủi ro nền.
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
- Test: **734 passed** (thêm `tests/test_progress_store.py` — 15 test với
  monkeypatch `_component`, gồm 3 test cho chuỗi fix: chờ giá trị trình duyệt,
  bỏ qua persist hồ sơ rỗng, persist khi có nhật ký; thêm 2 test AppTest
  zero-fill bug #4 trong `tests/test_learning_flow.py`; full suite ~137s).

## 0a. Bổ sung 23/10/2026 (tối) — nhịp lộ trình theo lớp + đọc trước đại học

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

## 0b. Bổ sung 23/10/2026 (chiều) — trọn bộ thống kê phổ thông (Toán 10–12)

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

## 0c. Bổ sung 23/10/2026 (sáng) — luồng AI dùng chung (cấp sẵn của trang)

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
- `tests/` — 732 test, không cần mạng.

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
  hồ sơ rỗng), chi tiết ở mục 0; `1534cd4` — HANDOFF lần 1.
