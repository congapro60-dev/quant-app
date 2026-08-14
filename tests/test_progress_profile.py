"""Kiểm thử hồ sơ tiến độ: rubric, xuất/nhập và từ chối JSON độc hại."""

from __future__ import annotations

import json

import pytest

import progress_profile as pp


# ---------------------------------------------------------------------------
# Ghi tiến độ
# ---------------------------------------------------------------------------

def test_empty_profile_has_expected_shape():
    profile = pp.empty_profile()
    assert set(profile) == pp.TOP_LEVEL_KEYS
    assert profile["lesson_scores"] == {}
    assert profile["journal"] == []


def test_record_test_and_lesson_scores():
    profile = pp.empty_profile()
    pp.record_test(profile, "pre_test", 40)
    pp.record_lesson(profile, "bai_1", 80)
    assert profile["pre_test"]["score"] == 40.0
    assert profile["pre_test"]["taken_at"]
    assert profile["lesson_scores"]["bai_1"] == 80.0


def test_scores_are_clamped_to_zero_hundred():
    profile = pp.empty_profile()
    pp.record_lesson(profile, "a", 250)
    pp.record_lesson(profile, "b", -30)
    assert profile["lesson_scores"]["a"] == 100.0
    assert profile["lesson_scores"]["b"] == 0.0


def test_journal_entry_is_recorded_with_timestamp():
    profile = pp.empty_profile()
    pp.add_journal_entry(
        profile, title="Mua CTG", decision="Chưa mua",
        rationale="Chờ kiểm định", risk="Giới hạn lỗ 2%", sources="Báo cáo quý",
    )
    assert len(profile["journal"]) == 1
    assert profile["journal"][0]["at"]
    assert profile["journal"][0]["title"] == "Mua CTG"


def test_record_test_rejects_bad_target():
    with pytest.raises(ValueError):
        pp.record_test(pp.empty_profile(), "giua_ky", 50)


# ---------------------------------------------------------------------------
# Rubric 30/30/25/15
# ---------------------------------------------------------------------------

def test_rubric_weights_match_the_required_split():
    assert pp.RUBRIC_WEIGHTS["kien_thuc"] == 0.30
    assert pp.RUBRIC_WEIGHTS["lap_luan"] == 0.30
    assert pp.RUBRIC_WEIGHTS["rui_ro_nguon"] == 0.25
    assert pp.RUBRIC_WEIGHTS["nhat_ky"] == 0.15
    assert abs(sum(pp.RUBRIC_WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_profile_scores_one_hundred():
    profile = pp.empty_profile()
    pp.record_lesson(profile, "b1", 100)
    pp.record_test(profile, "post_test", 100)
    profile["rubric_scores"] = {
        "kien_thuc": 100, "lap_luan": 100, "rui_ro_nguon": 100, "nhat_ky": 100,
    }
    assert pp.compute_rubric(profile).total == pytest.approx(100.0)


def test_empty_profile_scores_zero():
    assert pp.compute_rubric(pp.empty_profile()).total == 0.0


def test_rubric_rows_cover_all_four_criteria():
    rows = pp.compute_rubric(pp.empty_profile()).as_rows()
    assert len(rows) == 4
    assert {r["Tiêu chí"] for r in rows} == set(pp.RUBRIC_LABELS.values())


# ---------------------------------------------------------------------------
# Xuất / nhập hợp lệ
# ---------------------------------------------------------------------------

def test_export_import_round_trip():
    profile = pp.empty_profile()
    pp.record_lesson(profile, "bai_1", 75)
    pp.record_test(profile, "post_test", 88)
    pp.add_journal_entry(profile, title="T1", decision="Giữ")

    restored = pp.import_json(pp.export_json(profile))

    assert restored["lesson_scores"]["bai_1"] == 75.0
    assert restored["post_test"]["score"] == 88.0
    assert len(restored["journal"]) == 1


def test_export_is_valid_utf8_json_with_vietnamese():
    profile = pp.empty_profile()
    pp.add_journal_entry(profile, title="Rủi ro thị trường", decision="Chờ")
    parsed = json.loads(pp.export_json(profile))
    assert parsed["journal"][0]["title"] == "Rủi ro thị trường"


# ---------------------------------------------------------------------------
# Từ chối JSON độc hại / hỏng
# ---------------------------------------------------------------------------

def test_reject_non_json():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json("khong phai json")


def test_reject_empty_file():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json("")


def test_reject_non_object_root():
    for payload in ("[]", '"chuoi"', "123", "null"):
        with pytest.raises(pp.ProfileImportError):
            pp.import_json(payload)


def test_reject_oversized_payload():
    big = json.dumps({"lesson_scores": {str(i): 1 for i in range(60000)}})
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(big)


def test_reject_deeply_nested_payload():
    nested: dict = {"journal": []}
    node: dict = nested
    for _ in range(40):
        node["pre_test"] = {}
        node = node["pre_test"]
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps(nested))


def test_reject_unknown_top_level_keys():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"__class__": "os.system", "lesson_scores": {}}))


def test_reject_identity_fields_in_import():
    for bad in ({"cccd": "123"}, {"ngay_sinh": "2010-01-01"}, {"kyc": "ok"}):
        with pytest.raises(pp.ProfileImportError):
            pp.import_json(json.dumps(bad))


def test_reject_pii_nested_in_lesson_scores():
    payload = json.dumps({"lesson_scores": {"cccd_hoc_sinh": 10}})
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(payload)


def test_reject_bad_types():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"lesson_scores": []}))
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"journal": {"a": 1}}))
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"pre_test": "100"}))


def test_reject_non_numeric_scores():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"lesson_scores": {"a": "rat gioi"}}))


def test_reject_infinity_and_nan_scores():
    for literal in ("Infinity", "-Infinity", "NaN"):
        payload = '{"lesson_scores": {"a": %s}}' % literal
        with pytest.raises(pp.ProfileImportError):
            pp.import_json(payload)


def test_reject_unsupported_schema_version():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"schema_version": 999}))
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(json.dumps({"schema_version": "1"}))


def test_reject_too_many_journal_entries():
    payload = json.dumps({
        "journal": [{"title": "x"} for _ in range(pp.MAX_JOURNAL_ENTRIES + 1)]
    })
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(payload)


def test_reject_journal_entry_with_unknown_key():
    payload = json.dumps({"journal": [{"title": "x", "exec": "rm -rf"}]})
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(payload)


def test_reject_unknown_rubric_criteria():
    payload = json.dumps({"rubric_scores": {"diem_thuong": 100}})
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(payload)


def test_long_text_is_truncated_not_rejected():
    payload = json.dumps({"journal": [{"title": "a" * 50_000}]})
    restored = pp.import_json(payload)
    assert len(restored["journal"][0]["title"]) <= pp.MAX_TEXT_LEN


def test_import_accepts_bytes_input():
    restored = pp.import_json(pp.export_json(pp.empty_profile()).encode("utf-8"))
    assert restored["schema_version"] == pp.SCHEMA_VERSION


def test_import_rejects_invalid_utf8_bytes():
    with pytest.raises(pp.ProfileImportError):
        pp.import_json(b"\xff\xfe\x00bad")
