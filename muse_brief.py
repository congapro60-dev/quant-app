"""Prepare grounded briefs locally; no Muse API or private session data."""

import streamlit as st

import curriculum as cur
import curriculum_university as uni
import learning_modes as lmode

PURPOSE_LABELS = {
    "prepare": "Chuẩn bị trước bài mới",
    "review": "Ôn tập, bù phần chưa hiểu",
    "new_lesson": "Tự học trọn một bài",
}
AUDIENCE_LABELS = {"thpt": "Học sinh THPT", "dai_hoc": "Sinh viên đại học"}
_STRUCTURES = {
    "prepare": "10 phút: tình huống mở đầu, 3 câu dự đoán, giải nghĩa từ khóa, 2 câu hỏi mang tới lớp. Chưa đưa lời giải trước dự đoán.",
    "review": "15 phút: 3 câu chẩn đoán, giải thích theo từng lỗi hiểu sai, ví dụ tương tự và 3 câu kiểm tra lại có đáp án riêng.",
    "new_lesson": "25 phút: mục tiêu, kiểm tra kiến thức nền, giải thích từng bước, ví dụ có lời giải, thực hành có gợi ý và kiểm tra cuối bài.",
}


def build_learning_brief(lesson, purpose: str, audience: str) -> str:
    if purpose not in PURPOSE_LABELS or audience not in AUDIENCE_LABELS:
        raise ValueError("Mục tiêu hoặc nhóm người học không hợp lệ.")
    sources = "\n".join(f"- {name}" + (f": {url}" if url else " (tài liệu tham chiếu, chưa cung cấp toàn văn)")
                        for name, url in lesson.resources)
    misconceptions = "\n".join(f"- Nhầm: {wrong}\n  Giải thích: {right}" for wrong, right in lesson.misconceptions)
    return f"""# Yêu cầu học liệu: {lesson.title}

Người học: {AUDIENCE_LABELS[audience]}.
Mục đích: {PURPOSE_LABELS[purpose]}.
Đầu ra: bài tự học tiếng Việt, thuật ngữ tiếng Anh kèm nghĩa tiếng Việt.
Trình tự: {_STRUCTURES[purpose]}

## Nội dung nền từ Quant App
Mục tiêu: {lesson.objective}

Giải thích:
{lesson.explanation}

Ví dụ:
{lesson.example}

Thực hành:
{lesson.interactive}

Lỗi hiểu sai:
{misconceptions}

Nguồn được nêu trong bài:
{sources}

## Cách trình bày và kiểm chứng
- Tách hoạt động học sinh, gợi ý và đáp án để người học tự trả lời trước.
- Mỗi câu kiểm tra có đáp án, phép tính, đơn vị và giải thích lỗi sai.
- Kiểm tra số học; phân biệt dữ kiện, giả định và nhận xét. Gắn nhãn số liệu giả định.
- Chỉ dẫn nguồn thực sự đọc được, kèm URL và ngày truy cập. Không bịa trích dẫn từ tài liệu chưa được cung cấp.
- Nội dung dùng để học; không dự đoán chắc chắn giá, không khuyên mua/bán mã cụ thể, không đặt lệnh.
- Trả bản nháp Markdown để giáo viên duyệt; không tự đăng, gửi cho học sinh hoặc truy cập tài khoản giao dịch.

## Minh họa tùy chọn
Đề xuất một hình minh họa hoặc kịch bản video 10–20 giây giúp hiểu khái niệm.
Giữ chữ, số liệu và công thức thành phần riêng để kiểm tra; không nhúng chúng vào ảnh sinh tự động.
Trước khi tạo ảnh, video hoặc âm thanh, nêu công cụ khả dụng, quyền sử dụng và chi phí; chờ xác nhận.
Nếu không có công cụ, chỉ trả kịch bản, không nói đã tạo tệp.

## Bàn giao
Ghi riêng: đã soạn, đã kiểm tra, chưa kiểm chứng. Kèm nguồn và danh sách tệp thực sự có.
"""


ALTERNATIVE_AI_LINKS = (
    ("Mở Muse", "https://muse.ai/"),
    ("Mở ChatGPT", "https://chatgpt.com/"),
    ("Mở Gemini", "https://gemini.google.com/"),
    ("Mở Copilot", "https://copilot.microsoft.com/"),
    ("Mở Zalo AI", "https://zalo.ai/"),
)


def render_muse_workshop() -> None:
    st.header("Soạn học liệu với AI")
    st.write("Tạo bản yêu cầu từ bài học đang có, rồi tự dán sang AI tùy chọn (Muse, ChatGPT, Gemini, Copilot, Zalo AI…) để làm bài tự học, hình minh họa hoặc kịch bản video.")
    st.info(
        "Không có Muse vẫn làm được: bản yêu cầu chỉ là văn bản thường, chạy được với "
        "bất kỳ AI nào nhận văn bản. Muse có thể không truy cập được từ Việt Nam "
        "(một số nhà mạng chặn), nên với AI nào lớp bạn vào được thì dùng AI đó — "
        "đổi AI không làm thay đổi nội dung bản yêu cầu."
    )
    st.caption("Bước này chạy tại máy. Không gửi hồ sơ, điểm, danh mục hoặc khóa API sang AI bên ngoài nào.")
    audience = st.selectbox("Nhóm người học", list(AUDIENCE_LABELS),
                            index=1 if lmode.get_mode(st.session_state) == lmode.MODE_UNIVERSITY else 0,
                            format_func=AUDIENCE_LABELS.get, key="muse_audience")
    lessons = uni.all_lessons() if audience == "dai_hoc" else cur.all_lessons()
    lesson_index = st.selectbox("Bài cần soạn học liệu", range(len(lessons)),
                                format_func=lambda i: lessons[i].title, key="muse_lesson")
    purpose = st.radio("Mục tiêu tự học", list(PURPOSE_LABELS),
                       format_func=PURPOSE_LABELS.get, key="muse_purpose")
    brief = build_learning_brief(lessons[lesson_index], purpose, audience)
    with st.expander("Xem bản yêu cầu trước khi gửi", expanded=True):
        st.code(brief, language=None, height=300)
    st.download_button("Tải bản yêu cầu (.md)", brief.encode("utf-8"),
                       file_name=f"hoc_lieu_{lessons[lesson_index].lesson_id}_{purpose}.md",
                       mime="text/markdown", key="muse_download")
    links = st.columns(len(ALTERNATIVE_AI_LINKS))
    for column, (label, url) in zip(links, ALTERNATIVE_AI_LINKS):
        with column:
            st.link_button(label, url, width="stretch",
                           help="Mở website trong tab mới; Quant App không tự gửi nội dung đi. "
                                "Quyền sử dụng thuộc tài khoản của bạn.")
    st.caption(
        "Cách dùng chung cho mọi AI: tải bản yêu cầu (.md) ở trên hoặc copy khung văn bản, "
        "dán vào ô chat của AI bạn chọn, yêu cầu trả Markdown rồi giáo viên duyệt lại. "
        "Muse là một lựa chọn, không phải bắt buộc; một số AI miễn phí nhưng cần đăng ký tài khoản."
    )
    st.link_button(
        "Mở AI phân tích chứng khoán Việt Nam",
        "https://agents.ai.vn/agents/stock-ai",
        help="Mở tác nhân bên ngoài để tham khảo; Quant App không tự gửi dữ liệu sang đó.",
    )
    st.caption(
        "Tác nhân bên ngoài thuộc agents.ai.vn được mô tả là trả ảnh dashboard qua A2A. "
        "Chưa có tài liệu API công khai được xác minh; xem như nguồn tham khảo độc lập, "
        "không thay thế dữ liệu kiểm định của Quant App và không phải cam kết lợi nhuận."
    )
    with st.expander("Ứng dụng thêm cho nghiên cứu tài chính"):
        st.write("Nhờ AI bên ngoài tổng hợp báo cáo doanh nghiệp công khai, ghi rõ nguồn và ngày công bố; đối chiếu thông tin giữa nhiều nguồn trước khi dùng.")
        st.write("Nhờ AI bên ngoài tạo tình huống học về lãi kép, đa dạng hóa hoặc rủi ro. Chỉ dùng số liệu giả định có nhãn, kiểm tra đáp án bằng công cụ tính của Quant App.")
        st.caption("Quant App chưa tích hợp API tự động với AI nào. Nội dung AI tạo cần được kiểm tra trước khi đưa vào lớp học hoặc nghiên cứu.")
