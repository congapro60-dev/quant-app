"""Kiểm thử nhật ký thay đổi chính sách."""

from __future__ import annotations

import json

import pytest

import policy_audit as pa
import readiness_gate as rg


def test_records_a_change_with_old_and_new_value():
    session: dict = {}
    event = pa.record_change(session, "age_band", rg.AGE_UNDER_15, rg.AGE_15_17)

    assert event is not None
    assert event.field == "age_band"
    assert event.old_value == rg.AGE_UNDER_15
    assert event.new_value == rg.AGE_15_17
    assert event.at
    assert len(pa.events(session)) == 1


def test_unchanged_value_is_not_recorded():
    """Streamlit dựng lại trang liên tục; ghi vô điều kiện sẽ làm nhật ký vô dụng."""

    session: dict = {}
    pa.record_change(session, "guardian_confirmed", False, True)
    for _ in range(50):
        pa.record_change(session, "guardian_confirmed", True, True)

    assert len(pa.events(session)) == 1


def test_booleans_are_rendered_in_vietnamese():
    session: dict = {}
    event = pa.record_change(session, "risk_check_passed", False, True)
    assert event.old_value == "Không"
    assert event.new_value == "Có"


def test_none_is_rendered_as_unset():
    session: dict = {}
    event = pa.record_change(session, "capital_cap_vnd", None, 5_000_000)
    assert event.old_value == "(chưa đặt)"


def test_field_label_is_vietnamese():
    session: dict = {}
    event = pa.record_change(session, "max_sector_fraction", 0.3, 0.4)
    assert event.field_label == "Tỷ trọng tối đa mỗi ngành"


def test_unknown_field_falls_back_to_raw_name():
    session: dict = {}
    event = pa.record_change(session, "truong_moi", 1, 2)
    assert event.field_label == "truong_moi"


# ---------------------------------------------------------------------------
# Không lưu dữ liệu định danh
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["cccd", "so_cmnd", "ngay_sinh", "kyc_status",
                                 "bank_account", "passport"])
def test_identity_fields_are_refused(bad):
    session: dict = {}
    with pytest.raises(pa.PolicyAuditError):
        pa.record_change(session, bad, "x", "y")
    assert pa.events(session) == []


def test_sync_refuses_identity_fields():
    session: dict = {}
    with pytest.raises(pa.PolicyAuditError):
        pa.sync_and_record(session, {"cccd": "123"}, snapshot_key="snap")


def test_empty_field_name_is_refused():
    with pytest.raises(pa.PolicyAuditError):
        pa.record_change({}, "", 1, 2)


# ---------------------------------------------------------------------------
# So sánh hàng loạt
# ---------------------------------------------------------------------------

def test_sync_records_only_fields_that_changed():
    session: dict = {}
    first = {"age_band": rg.AGE_15_17, "guardian_confirmed": False}
    pa.sync_and_record(session, first, snapshot_key="snap")
    assert len(pa.events(session)) == 2          # lần đầu đặt cũng là thay đổi

    # Chạy lại y hệt: không thêm mục nào
    pa.sync_and_record(session, first, snapshot_key="snap")
    assert len(pa.events(session)) == 2

    # Đổi một trường
    second = dict(first, guardian_confirmed=True)
    recorded = pa.sync_and_record(session, second, snapshot_key="snap")
    assert len(recorded) == 1
    assert recorded[0].field == "guardian_confirmed"


def test_sync_rejects_non_mapping():
    with pytest.raises(pa.PolicyAuditError):
        pa.sync_and_record({}, ["khong phai mapping"], snapshot_key="snap")


def test_gate_and_limit_changes_share_one_log():
    session: dict = {}
    pa.sync_and_record(session, {"age_band": rg.AGE_18_PLUS}, snapshot_key="s1")
    pa.sync_and_record(session, {"capital_cap_vnd": 10_000_000}, snapshot_key="s2")
    fields = {e.field for e in pa.events(session)}
    assert fields == {"age_band", "capital_cap_vnd"}


# ---------------------------------------------------------------------------
# Giới hạn và xuất
# ---------------------------------------------------------------------------

def test_log_is_capped_and_keeps_the_newest():
    session: dict = {}
    for i in range(pa.MAX_EVENTS + 40):
        pa.record_change(session, "capital_cap_vnd", i, i + 1)

    log = pa.events(session)
    assert len(log) == pa.MAX_EVENTS
    assert log[-1].new_value == str(pa.MAX_EVENTS + 40)


def test_long_values_are_truncated():
    session: dict = {}
    event = pa.record_change(session, "note_field", "a", "b" * 5000)
    assert len(event.new_value) <= pa.MAX_VALUE_LEN


def test_export_json_is_parseable_and_utf8():
    session: dict = {}
    pa.record_change(session, "age_band", None, rg.AGE_15_17,
                     note="Người học tự khai")
    parsed = json.loads(pa.export_json(session))
    assert parsed[0]["field"] == "age_band"
    assert parsed[0]["note"] == "Người học tự khai"


def test_audit_rows_are_newest_first_and_vietnamese_headed():
    session: dict = {}
    pa.record_change(session, "age_band", None, rg.AGE_15_17)
    pa.record_change(session, "risk_check_passed", False, True)

    rows = pa.audit_rows(session)
    assert rows[0]["Mục chính sách"] == "Đạt bài kiểm tra rủi ro"
    assert set(rows[0]) == {"Thời điểm", "Mục chính sách", "Giá trị cũ",
                            "Giá trị mới", "Ghi chú"}


def test_events_on_empty_or_corrupt_session():
    assert pa.events(None) == []
    assert pa.events({}) == []
    assert pa.events({pa.AUDIT_KEY: "khong phai danh sach"}) == []
