"""Kiểm thử: tab giới thiệu Chứng khoán trên MoMo — đúng pháp lý và có cảnh báo."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

import momo_guide as mg


def _run():
    at = AppTest.from_string(
        "from momo_guide import render_momo_guide\nrender_momo_guide()",
        default_timeout=60,
    ).run()
    assert not at.exception
    return at


def test_two_age_tracks_cover_15_to_17_and_18_plus():
    """Hai nhánh tách rõ: đủ 18 (CVS nhận hồ sơ) và 15–17 (chưa mở được qua MoMo)."""

    assert len(mg.AGE_TRACKS) == 2
    adult, minor = mg.AGE_TRACKS
    assert "18 tuổi trở lên" in adult["who"]
    assert "nhóm duy nhất CVS nhận hồ sơ" in adult["can"]
    assert "năng lực hành vi dân sự" in " ".join(adult["requires"])
    assert "15" in minor["who"] and "18" in minor["who"]
    assert "chưa mở được" in minor["who"]


def test_cvs_actually_requires_18_which_overrides_the_law_permission():
    """Điểm dễ sai nhất: luật cho phép 15–17, nhưng CVS yêu cầu đủ 18.

    Nguồn chính chủ momo.vn ghi rõ điều kiện mở tài khoản tại CVS là từ đủ 18
    tuổi. Test này khoá lại để sau này không có ai 'sửa' thành 15–17 mở được.
    """

    minor = mg.AGE_TRACKS[1]
    joined = minor["can"] + " " + " ".join(minor["requires"])
    assert "pháp luật cho phép" in joined
    assert "CVS yêu cầu đủ 18 tuổi" in joined
    assert "chưa mở được" in joined

    # Nguồn phải là trang chính chủ momo.vn, và con số tuổi nằm trong hằng số.
    assert mg.MOMO_AGE_SOURCE.startswith("https://www.momo.vn/")
    assert "18" in mg.CVS_MIN_AGE_NOTE


def test_age_caveat_separates_law_from_broker_policy():
    """Được luật cho phép KHÁC với được CVS nhận hồ sơ — phải nói rõ."""

    text = mg.AGE_CAVEAT
    lowered = text.lower()
    assert "pháp luật cho phép" in lowered
    assert "CVS" in text
    assert "nhận hồ sơ" in text
    # Không được lặp lại câu sai cũ rằng trang chính chủ thiếu thông tin tuổi.
    assert "không nêu điều kiện" not in lowered


def test_minor_checklist_never_tells_them_to_prepare_an_application():
    """Nhóm 15–17 không được dẫn đi chuẩn bị hồ sơ hay nộp tiền."""

    joined = " ".join(mg.age_checklist(1)).lower()

    assert "không" in joined and "đứng tên hộ" in joined
    assert "mô phỏng" in joined
    assert "1900 5454 41" in " ".join(mg.age_checklist(1))
    # Không được có câu mời đi nộp tiền hay eKYC như thể mở được.
    assert "trước khi nộp tiền" not in joined
    assert "ekyc" not in joined


def test_momo_render_shows_risk_warning_and_not_a_broker():
    at = _run()

    warnings = " ".join(str(w.value) for w in at.warning)
    assert "mất một phần hoặc toàn bộ" in warnings
    assert "không" in warnings and "lời khuyên đầu tư" in warnings
    # Không dùng hộp đỏ: học sinh thấy chữ đỏ sẽ tưởng ứng dụng hỏng.
    assert "không phải công ty chứng khoán" in warnings
    assert "không đặt lệnh" in warnings
    assert [e.value for e in at.error] == []


def test_momo_render_lists_fees_tax_and_trading_hours():
    at = _run()

    tables = [t.value for t in at.dataframe]
    joined = " ".join(str(t.to_dict()) for t in tables)

    assert "0,1%" in joined  # phí giao dịch và thuế bán
    assert "0,27" in joined  # phí lưu ký
    assert "HOSE" in joined and "UPCOM" in joined
    assert "Chứng quyền có bảo đảm" in joined


def test_hidden_fees_that_surprise_students_are_listed():
    """Phí đóng tài khoản và ứng trước tiền bán — loại học sinh hay bị bất ngờ."""

    joined = " ".join(f"{k} {v} {n}" for k, v, n, _ in mg.FEES)

    assert "Đóng tài khoản" in joined
    assert "100.000" in joined
    assert "Ứng trước tiền bán" in joined
    assert "0,033%" in joined
    assert "đóng tài khoản mất 100.000" in mg.FEE_WARNING.lower()


def test_each_fee_row_names_which_momo_page_it_came_from():
    """Trang sản phẩm và trang blog KHÔNG cùng biểu phí — phải ghi rõ nguồn từng dòng.

    Phí đóng tài khoản và ứng trước tiền bán chỉ có ở trang blog. Nếu để chung một
    bảng không ghi nguồn, người đọc sẽ tưởng tất cả nằm trên trang sản phẩm.
    """

    for row in mg.FEES:
        assert len(row) == 4, f"thiếu cột nguồn: {row}"
        assert row[3] in (mg.SRC_PRODUCT, mg.SRC_BLOG)

    by_name = {row[0]: row[3] for row in mg.FEES}
    assert by_name["**Đóng tài khoản giao dịch**"] == mg.SRC_BLOG
    assert by_name["Ứng trước tiền bán tự động"] == mg.SRC_BLOG
    assert by_name["Phí lưu ký cổ phiếu, chứng quyền, chứng chỉ quỹ"] == mg.SRC_PRODUCT


def test_trading_hours_split_morning_and_afternoon_sessions():
    """HOSE chiều đóng 14:45, HNX/UPCOM 15:00 — không gộp một chuỗi."""

    hours = {s: (m, a) for s, m, a in mg.TRADING_HOURS}

    assert hours["HOSE"] == ("09:00–11:30", "13:00–14:45")
    assert hours["HNX"] == ("09:00–11:30", "13:00–15:00")
    assert hours["UPCOM"] == ("09:00–11:30", "13:00–15:00")


def test_three_order_windows_match_the_official_page():
    """Ba khung: trong giờ, nghỉ trưa 11:30–13:00, và từ 18:00 mỗi ngày."""

    names = " ".join(k for k, _, _ in mg.ORDER_WINDOWS)
    bodies = " ".join(w + " " + r for _, w, r in mg.ORDER_WINDOWS)

    assert len(mg.ORDER_WINDOWS) == 3
    assert "11:30–13:00" in names
    assert "từ 18:00 mỗi ngày" in names
    assert "13:00" in bodies
    assert "09:00" in bodies


def test_account_opening_lists_face_verification_step():
    """Bài học thực tế: bước xác thực gương mặt là chỗ hay thất bại nhất."""

    steps = " ".join(mg.OPEN_ACCOUNT_STEPS)

    assert len(mg.OPEN_ACCOUNT_STEPS) == 7
    assert "Xác thực gương mặt" in steps
    assert "1900 5454 41" in mg.EKYC_TIPS


def test_legal_warnings_name_forbidden_acts_and_sources():
    titles = [w["title"] for w in mg.LEGAL_WARNINGS]
    joined = " ".join(titles) + " " + " ".join(w["body"] for w in mg.LEGAL_WARNINGS)

    for keyword in ("thao túng", "nội gián", "thông tin sai", "mượn tài khoản"):
        assert keyword in joined.lower()

    docs = " ".join(mg.LEGAL_DOCS)
    assert "Luật Chứng khoán 2019" in docs
    assert "Thông tư 120/2020/TT-BTC" in docs


def test_every_claim_carries_an_official_source():
    """Không có số liệu nào từ nguồn thứ ba — chỉ trang chính chủ MoMo."""

    assert mg.MOMO_URL == "https://www.momo.vn/chung-khoan"
    assert mg.MOMO_FEE_URL.startswith("https://www.momo.vn/")
    assert mg.SOURCE_DATE  # ngày đọc, để biết số liệu cũ hay mới


@pytest.mark.parametrize("index", [0, 1])
def test_age_track_selection_renders_checklist(index):
    at = _run()
    at.radio(key="momo_age_track").set_value(index).run()

    assert not at.exception
    body = " ".join(str(m.value) for m in at.markdown)
    assert "Việc cần làm ở nhóm này" in body


def test_minor_track_warns_they_cannot_open_yet_on_screen():
    """Trên màn hình, nhóm 15–17 phải thấy cảnh báo chưa mở được, không phải mời gọi."""

    at = _run()
    at.radio(key="momo_age_track").set_value(1).run()

    body = " ".join(str(m.value) for m in at.markdown) + " ".join(
        str(w.value) for w in at.warning)

    assert "chưa mở được" in body
    assert "đứng tên hộ" in body


def test_warrant_note_does_not_claim_a_lock_that_does_not_exist():
    """QA 25/10/2026: câu "ứng dụng khoá chứng quyền trong mô phỏng" là bịa.

    readiness_gate.py không có sản phẩm chứng quyền. Test này chặn câu đó quay lại.
    """

    text = mg.WARRANT_NOTE

    assert "khoá phần chứng quyền" not in text
    assert "khoá chứng quyền" not in text
    # Vẫn phải nói rõ điều tra được gì.
    assert "không công bố" in text
    assert "hạn mức tuổi riêng" in text


def test_margin_warning_matches_what_readiness_gate_actually_blocks():
    """Ký quỹ là rủi ro thật với nhóm đủ 18, và ứng dụng CÓ khoá với dưới 18.

    Đối chiếu với code thật: MINOR_HARD_BLOCKED phải chứa PRODUCT_MARGIN.
    """

    import readiness_gate as rg

    assert rg.PRODUCT_MARGIN in rg.MINOR_HARD_BLOCKED

    text = mg.MARGIN_WARNING
    assert "gọi ký quỹ" in text
    assert "bán giải chấp" in text
    assert "vay" in text
    # Không được khẳng định khoá chứng quyền khi code không làm vậy.
    assert "chứng quyền" not in text or "khoá" not in text.split("chứng quyền")[0][-20:]


def test_margin_appears_in_the_product_table():
    joined = " ".join(f"{p} {n}" for p, _, n in mg.PRODUCTS)

    assert "Ký quỹ" in joined
    assert "margin" in joined.lower()


def test_ekyc_tips_do_not_invent_a_lockout_policy():
    """QA: blog không nói gì về việc tạm khoá khi eKYC sai nhiều lần."""

    text = mg.EKYC_TIPS

    assert "tạm khoá" not in text and "tạm khóa" not in text
    assert "không phải quy định của CVS" in text


def test_hidden_fees_block_lists_the_three_surprise_costs():
    joined = " ".join(f"{n} {a}" for n, a, _ in mg.HIDDEN_FEES)

    assert len(mg.HIDDEN_FEES) == 3
    assert "Đóng tài khoản" in joined
    assert "Ứng trước tiền bán" in joined
    assert "100.000" in joined


def test_legal_docs_name_the_actual_age_and_warrant_documents():
    """Số thông tư phải đúng: 120/2020 là tuổi, 107/2016 là chứng quyền."""

    docs = " ".join(mg.LEGAL_DOCS)

    assert "Thông tư 120/2020/TT-BTC" in docs
    assert "Điều 6" in docs
    assert "Thông tư 107/2016/TT-BTC" in docs
    # Không được ghi sai 68/2024 là bản sửa đổi về tuổi.
    assert "68/2024" not in docs


def test_source_links_are_official_momo_domains_only():
    """Mọi liên kết nguồn phải thuộc tên miền chính chủ momo.vn."""

    for url in (mg.MOMO_URL, mg.MOMO_FEE_URL, mg.MOMO_AGE_SOURCE):
        assert url.startswith("https://www.momo.vn/")
