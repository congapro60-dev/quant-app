"""Kiểm thử phân loại lỗi dữ liệu và câu chữ theo từng người đọc."""

from __future__ import annotations

import pytest

import data_status_ui as ds


# ---------------------------------------------------------------------------
# Phân loại
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Market-data validation failed after trying sources KBS, VCI, MSN "
    "(KBS:VNINDEX:PROVIDER_ERROR; request:INCOMPLETE_PORTFOLIO)",
    "Không tải được dữ liệu: timeout",
    "HTTP 403 Forbidden",
    "429 too many requests",
    "circuit breaker open",
])
def test_provider_failures_are_classified_as_infrastructure(text):
    assert ds.classify(text) == ds.KIND_PROVIDER


@pytest.mark.parametrize("text", [
    "Ngày bắt đầu phải trước ngày kết thúc.",
    "Cần ít nhất một mã cổ phiếu và một chỉ số thị trường.",
    "Giới hạn 12 mã mỗi lần để bảo vệ quota và độ ổn định.",
])
def test_user_input_errors_are_classified_separately(text):
    assert ds.classify(text) == ds.KIND_INPUT


def test_empty_error_means_no_error():
    assert ds.classify("") == ds.KIND_NONE
    assert ds.classify(None) == ds.KIND_NONE
    assert ds.classify("   ") == ds.KIND_NONE


def test_unknown_error_defaults_to_infrastructure():
    """Nghiêng về phía người dùng không sửa được, để họ khỏi loay hoay."""

    assert ds.classify("một lỗi lạ chưa từng gặp") == ds.KIND_PROVIDER


def test_input_marker_wins_over_provider_marker():
    mixed = "Ngày bắt đầu phải trước ngày kết thúc (PROVIDER_ERROR)"
    assert ds.classify(mixed) == ds.KIND_INPUT


# ---------------------------------------------------------------------------
# Câu chữ theo người đọc
# ---------------------------------------------------------------------------

def test_learner_is_told_lessons_still_work():
    """Đây là lý do tồn tại của tệp này: học sinh không được tưởng app hỏng."""

    msg = ds.message_for(ds.KIND_PROVIDER, is_learner=True)
    assert "Lộ trình học" in msg
    assert "vẫn dùng được" in msg


def test_learner_message_has_no_technical_jargon():
    msg = ds.message_for(ds.KIND_PROVIDER, is_learner=True).lower()
    for jargon in ("provider_error", "http", "403", "timeout", "circuit"):
        assert jargon not in msg


def test_researcher_gets_the_actual_cause_and_a_way_out():
    msg = ds.message_for(ds.KIND_PROVIDER, is_learner=False)
    assert "ngoài Việt Nam" in msg
    assert "Việt Nam" in msg


def test_input_error_message_is_same_for_both_readers():
    """Lỗi nhập liệu thì ai cũng sửa được, nên nói giống nhau."""

    a = ds.message_for(ds.KIND_INPUT, is_learner=True)
    b = ds.message_for(ds.KIND_INPUT, is_learner=False)
    assert a == b
    assert "mã cổ phiếu" in a


def test_no_error_produces_no_message():
    assert ds.message_for(ds.KIND_NONE, is_learner=True) == ""
    assert ds.message_for(ds.KIND_NONE, is_learner=False) == ""


# ---------------------------------------------------------------------------
# Chi tiết kỹ thuật
# ---------------------------------------------------------------------------

def test_technical_detail_hidden_from_learners():
    assert ds.should_show_technical_detail(ds.KIND_PROVIDER, is_learner=True) is False
    assert ds.should_show_technical_detail(ds.KIND_INPUT, is_learner=True) is False


def test_technical_detail_available_to_researchers():
    assert ds.should_show_technical_detail(ds.KIND_PROVIDER, is_learner=False) is True


def test_no_technical_detail_when_there_is_no_error():
    assert ds.should_show_technical_detail(ds.KIND_NONE, is_learner=False) is False
