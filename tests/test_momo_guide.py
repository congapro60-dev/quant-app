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
    """Luật chia hai nhánh: đủ 15–chưa đủ 18 (cần người giám hộ) và đủ 18+."""

    assert len(mg.AGE_TRACKS) == 2
    adult, minor = mg.AGE_TRACKS
    assert "18 tuổi trở lên" in adult["who"]
    assert "năng lực hành vi dân sự" in " ".join(adult["requires"])
    assert "15" in minor["who"] and "18" in minor["who"]
    assert "người đại diện theo pháp luật" in minor["can"]


def test_age_caveat_separates_law_from_broker_policy():
    """Được luật cho phép KHÁC với được CVS nhận hồ sơ — phải nói rõ."""

    text = mg.AGE_CAVEAT
    assert "pháp luật cho phép" in text
    assert "CVS" in text
    assert "không nêu điều kiện" in text.lower() or "không nêu" in text


def test_minor_checklist_requires_guardian_consent_before_money():
    steps = mg.age_checklist(1)
    joined = " ".join(steps).lower()
    assert "giám hộ" in joined or "cha/mẹ" in joined
    assert "trước khi nộp tiền" in joined


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
    assert "Chuẩn bị trước khi mở" in body
