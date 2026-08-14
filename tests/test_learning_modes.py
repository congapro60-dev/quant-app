"""Kiểm thử hai chế độ học và cam kết giữ nguyên dữ liệu phiên."""

from __future__ import annotations

import pandas as pd
import pytest

import learning_modes as lm


def _session_with_work() -> dict:
    """Phiên đã có dữ liệu phân tích, sổ mô phỏng và kết quả kiểm thử."""

    return {
        lm.MODE_KEY: lm.MODE_HIGHSCHOOL,
        "prices_df": pd.DataFrame({"CTG": [31.0, 31.5], "VNINDEX": [1200.0, 1210.0]}),
        "returns_df": pd.DataFrame({"CTG": [0.016]}),
        "valid_assets": ["CTG", "FPT"],
        "market_ticker": "VNINDEX",
        "sim_results_list": [{"Mã CP": "CTG", "Beta (Độ nhạy)": 1.1}],
        "opt_res": {"assets": ["CTG", "FPT"]},
        "paper_ledger": {"cash_vnd": 10_000_000},
        "paper_trades": [{"symbol": "CTG", "side": "BUY"}],
        "trade_plans": {"CTG": {"stop": 29.0}},
        "backtest_result": {"cagr": 0.07},
        "eviews_data": pd.DataFrame({"Y": [1.0, 2.0]}),
    }


def test_default_mode_is_highschool():
    assert lm.get_mode({}) == lm.MODE_HIGHSCHOOL
    assert lm.normalise_mode("khong-ton-tai") == lm.MODE_HIGHSCHOOL
    assert lm.normalise_mode(None) == lm.MODE_HIGHSCHOOL


def test_normalise_mode_accepts_valid_values():
    assert lm.normalise_mode("dai_hoc") == lm.MODE_UNIVERSITY
    assert lm.normalise_mode("  DAI_HOC ") == lm.MODE_UNIVERSITY
    assert lm.normalise_mode("thpt") == lm.MODE_HIGHSCHOOL


def test_switch_mode_preserves_analysis_and_portfolio_state():
    """Yêu cầu cốt lõi: đổi chế độ không được xóa dữ liệu đang làm dở."""

    session = _session_with_work()
    before_prices = session["prices_df"].copy()

    lm.switch_mode(session, lm.MODE_UNIVERSITY)

    assert session[lm.MODE_KEY] == lm.MODE_UNIVERSITY
    pd.testing.assert_frame_equal(session["prices_df"], before_prices)
    assert session["valid_assets"] == ["CTG", "FPT"]
    assert session["paper_ledger"] == {"cash_vnd": 10_000_000}
    assert session["trade_plans"] == {"CTG": {"stop": 29.0}}
    assert session["backtest_result"] == {"cagr": 0.07}


def test_switch_mode_round_trip_keeps_every_preserved_key():
    session = _session_with_work()
    expected_keys = {k for k in lm.PRESERVED_SESSION_KEYS if k in session}

    lm.switch_mode(session, lm.MODE_UNIVERSITY)
    lm.switch_mode(session, lm.MODE_HIGHSCHOOL)

    assert expected_keys <= set(session)
    assert session[lm.MODE_KEY] == lm.MODE_HIGHSCHOOL
    assert not session["prices_df"].empty
    assert session["paper_trades"] == [{"symbol": "CTG", "side": "BUY"}]


def test_switch_mode_rejects_unknown_value_without_losing_data():
    session = _session_with_work()
    lm.switch_mode(session, "che_do_la")
    assert session[lm.MODE_KEY] == lm.MODE_HIGHSCHOOL
    assert session["valid_assets"] == ["CTG", "FPT"]


def test_preserved_keys_cover_the_contract_named_in_the_spec():
    for key in (
        "prices_df",
        "valid_assets",
        "paper_ledger",
        "trade_plans",
        "backtest_result",
    ):
        assert key in lm.PRESERVED_SESSION_KEYS


def test_university_mode_sees_all_nine_features():
    session = {lm.MODE_KEY: lm.MODE_UNIVERSITY}
    assert len(lm.visible_features(session)) == 9
    assert set(lm.visible_features(session)) == set(lm.FEATURES)


def test_highschool_hides_advanced_features_until_unlocked():
    session = {lm.MODE_KEY: lm.MODE_HIGHSCHOOL}
    basic = lm.visible_features(session)

    assert lm.FEATURE_SIM not in basic
    assert lm.FEATURE_MARKOWITZ not in basic
    assert lm.FEATURE_EVIEWS not in basic
    assert lm.FEATURE_BACKTEST not in basic
    # Nhóm cơ bản vẫn dùng được ngay
    assert lm.FEATURE_PAPER in basic
    assert lm.FEATURE_INVEST_DESK in basic


def test_highschool_sees_advanced_after_unlock():
    session = {lm.MODE_KEY: lm.MODE_HIGHSCHOOL, lm.UNLOCK_KEY: True}
    unlocked = lm.visible_features(session)
    assert lm.FEATURE_SIM in unlocked
    assert len(unlocked) == 9


def test_advanced_unlocked_always_true_for_university():
    assert lm.is_advanced_unlocked({lm.MODE_KEY: lm.MODE_UNIVERSITY}) is True
    assert lm.is_advanced_unlocked({lm.MODE_KEY: lm.MODE_HIGHSCHOOL}) is False


def test_every_feature_belongs_to_one_of_the_five_areas():
    for name, meta in lm.FEATURES.items():
        assert meta["area"] in lm.AREA_ORDER, name


def test_area_labels_cover_every_area():
    assert set(lm.AREA_LABELS) == set(lm.AREA_ORDER)
    assert len(lm.AREA_ORDER) == 5


def test_features_in_area_filters_correctly():
    names = lm.visible_features(mode=lm.MODE_UNIVERSITY)
    lab = lm.features_in_area(lm.AREA_MODEL_LAB, names)
    assert lm.FEATURE_SIM in lab
    assert lm.FEATURE_PAPER not in lab


def test_learner_profile_defaults_are_valid():
    profile = lm.default_learner_profile()
    assert profile["grade_level"] in lm.GRADE_LEVELS
    assert profile["knowledge_level"] in lm.KNOWLEDGE_LEVELS
    assert profile["goals"] == []


def test_learner_profile_normalises_unknown_values():
    messy = lm.normalise_learner_profile({
        "grade_level": "lop_99", "knowledge_level": "sieu_cap",
        "goals": ["khong_ton_tai", "on_thi"],
    })
    assert messy["grade_level"] == "khac"
    assert messy["knowledge_level"] == "moi_bat_dau"
    assert messy["goals"] == ["on_thi"]


def test_learner_profile_drops_identity_and_unknown_keys():
    stored = lm.store_learner_profile({}, {
        "grade_level": "lop_11", "knowledge_level": "kha", "goals": ["on_thi"],
        "ho_ten": "Nguyen Van A", "ngay_sinh": "2010-01-01", "cccd": "0123",
    })
    assert set(stored) == {"grade_level", "knowledge_level", "goals"}


def test_learner_profile_handles_garbage_input():
    for bad in (None, "chuoi", 123, []):
        profile = lm.normalise_learner_profile(bad)
        assert profile == lm.default_learner_profile()


def test_learner_profile_deduplicates_goals():
    profile = lm.normalise_learner_profile({"goals": ["on_thi", "on_thi"]})
    assert profile["goals"] == ["on_thi"]


def test_learner_profile_accepts_single_goal_as_string():
    profile = lm.normalise_learner_profile({"goals": "on_thi"})
    assert profile["goals"] == ["on_thi"]


def test_suggested_mode_follows_grade_but_does_not_force():
    assert lm.suggested_mode({"grade_level": "lop_10"}) == lm.MODE_HIGHSCHOOL
    assert lm.suggested_mode({"grade_level": "sinh_vien"}) == lm.MODE_UNIVERSITY
    assert lm.suggested_mode({"grade_level": "khac"}) == lm.DEFAULT_MODE


def test_learner_profile_survives_mode_switch():
    session = _session_with_work()
    lm.store_learner_profile(session, {"grade_level": "lop_12", "goals": ["on_thi"]})
    lm.switch_mode(session, lm.MODE_UNIVERSITY)
    assert lm.get_learner_profile(session)["grade_level"] == "lop_12"


def test_risk_limits_and_audit_survive_mode_switch():
    session = _session_with_work()
    session["risk_limits"] = {"capital_cap_vnd": 5_000_000}
    session["policy_audit"] = ["su_kien"]
    lm.switch_mode(session, lm.MODE_UNIVERSITY)
    assert session["risk_limits"] == {"capital_cap_vnd": 5_000_000}
    assert session["policy_audit"] == ["su_kien"]


@pytest.mark.parametrize("label_map", [lm.GRADE_LABELS, lm.KNOWLEDGE_LABELS,
                                       lm.GOAL_LABELS])
def test_learner_profile_labels_are_filled(label_map):
    for key, label in label_map.items():
        assert label.strip(), key


@pytest.mark.parametrize("mode", list(lm.VALID_MODES))
def test_mode_labels_are_bilingual(mode):
    """Nhãn chế độ phải có tiếng Việt kèm tiếng Anh trong ngoặc."""

    label = lm.MODE_LABELS[mode]
    assert "(" in label and ")" in label
