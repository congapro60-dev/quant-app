"""Kiểm thử cổng vốn thật: phân tầng tuổi, chống bỏ qua và chống lưu định danh."""

from __future__ import annotations

import pytest

import readiness_gate as rg


def _full_pass(age_band: str) -> dict:
    """Đầu vào thỏa mọi điều kiện, dùng để kiểm tra riêng ảnh hưởng của tuổi."""

    return {
        "age_band": age_band,
        "guardian_confirmed": True,
        "broker_policy_confirmed": True,
        "paper_first_completed": True,
        "risk_check_passed": True,
    }


# ---------------------------------------------------------------------------
# Phân tầng theo tuổi: 14 / 15 / 17 / 18
# ---------------------------------------------------------------------------

def test_age_14_is_paper_only_even_with_every_confirmation():
    """Dưới 15 tuổi: không có tổ hợp xác nhận nào mở được vốn thật."""

    decision = rg.evaluate(_full_pass(rg.AGE_UNDER_15))
    assert decision.real_capital_allowed is False
    assert decision.paper_only is True
    assert decision.allowed_products == ()


def test_age_15_blocked_until_all_conditions_met():
    partial = _full_pass(rg.AGE_15_17)
    partial["guardian_confirmed"] = False
    decision = rg.evaluate(partial)
    assert decision.real_capital_allowed is False
    assert any("người đại diện" in item for item in decision.outstanding)


def test_age_17_allows_cash_only_stock_and_fund_when_fully_verified():
    decision = rg.evaluate(_full_pass(rg.AGE_15_17))
    assert decision.real_capital_allowed is True
    assert decision.allowed_products == (rg.PRODUCT_STOCK, rg.PRODUCT_FUND)
    assert any("cash-only" in note or "tiền có sẵn" in note for note in decision.notes)


def test_age_18_normal_mode_after_risk_check():
    decision = rg.evaluate(_full_pass(rg.AGE_18_PLUS))
    assert decision.real_capital_allowed is True
    assert rg.PRODUCT_STOCK in decision.allowed_products
    assert rg.PRODUCT_DERIVATIVE in decision.allowed_products


def test_age_18_without_risk_check_is_blocked():
    data = _full_pass(rg.AGE_18_PLUS)
    data["risk_check_passed"] = False
    decision = rg.evaluate(data)
    assert decision.real_capital_allowed is False
    assert decision.outstanding


# ---------------------------------------------------------------------------
# Khóa cứng sản phẩm với người dưới 18
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("band", [rg.AGE_UNDER_15, rg.AGE_15_17])
@pytest.mark.parametrize("product", list(rg.MINOR_HARD_BLOCKED))
def test_minors_hard_block_leveraged_and_derivative_products(band, product):
    decision = rg.evaluate(_full_pass(band))
    assert product in decision.blocked_products
    assert not decision.is_product_allowed(product)


def test_derivatives_hard_blocked_for_every_minor_band():
    for band in (rg.AGE_UNDER_15, rg.AGE_15_17):
        decision = rg.evaluate(_full_pass(band))
        assert rg.PRODUCT_DERIVATIVE in decision.blocked_products


def test_cfd_and_crypto_never_offered_at_any_age():
    for band in rg.AGE_BANDS:
        decision = rg.evaluate(_full_pass(band))
        assert rg.PRODUCT_CFD in decision.blocked_products
        assert rg.PRODUCT_CRYPTO in decision.blocked_products


# ---------------------------------------------------------------------------
# Không bỏ qua được cổng
# ---------------------------------------------------------------------------

def test_cannot_bypass_gate_by_forging_session_flags():
    """Cờ giả trong phiên không tạo ra quyền: quyết định luôn được tính lại."""

    session = {
        "readiness_state": {"age_band": rg.AGE_UNDER_15},
        # các cờ dưới đây là giả, mô phỏng người dùng sửa session_state
        "real_capital_allowed": True,
        "gate_passed": True,
        "readiness_ok": True,
    }
    decision = rg.evaluate_session(session)
    assert decision.real_capital_allowed is False
    assert decision.paper_only is True


def test_cannot_bypass_gate_by_injecting_extra_keys():
    """Khóa lạ (kể cả trông giống tham số URL) bị loại khi làm sạch."""

    decision = rg.evaluate({
        "age_band": rg.AGE_UNDER_15,
        "override": True,
        "force_allow": True,
        "admin": True,
        "real_capital_allowed": True,
    })
    assert decision.real_capital_allowed is False


def test_unknown_age_band_falls_back_to_most_restrictive():
    for bad in ["", None, "18", "abc", 18, {"a": 1}]:
        decision = rg.evaluate({"age_band": bad})
        assert decision.real_capital_allowed is False
        assert decision.age_band == rg.AGE_UNKNOWN


def test_missing_inputs_are_blocked_not_permissive():
    assert rg.evaluate(None).real_capital_allowed is False
    assert rg.evaluate({}).real_capital_allowed is False


# ---------------------------------------------------------------------------
# Không lưu dữ liệu định danh
# ---------------------------------------------------------------------------

def test_identity_documents_are_stripped_before_storage():
    session: dict = {}
    rg.store_gate_inputs(session, {
        "age_band": rg.AGE_18_PLUS,
        "risk_check_passed": True,
        "cccd": "0123456789",
        "ngay_sinh": "2001-01-01",
        "giay_khai_sinh": "scan.pdf",
        "kyc_status": "verified",
        "passport": "C1234567",
        "bank_account": "9704...",
    })
    stored = session["readiness_state"]
    for banned in ("cccd", "ngay_sinh", "giay_khai_sinh", "kyc_status",
                   "passport", "bank_account"):
        assert banned not in stored
    assert stored["age_band"] == rg.AGE_18_PLUS


def test_stored_state_only_contains_declared_gate_keys():
    session: dict = {}
    rg.store_gate_inputs(session, _full_pass(rg.AGE_18_PLUS) | {"junk": 1})
    assert set(session["readiness_state"]) <= set(rg.GATE_INPUT_KEYS)


def test_contains_identity_data_detects_pii():
    assert rg.contains_identity_data({"cccd": "x"}) is True
    assert rg.contains_identity_data({"so_cmnd": "x"}) is True
    assert rg.contains_identity_data({"age_band": rg.AGE_18_PLUS}) is False


# ---------------------------------------------------------------------------
# Nhãn song ngữ
# ---------------------------------------------------------------------------

def test_leveraged_product_labels_carry_english_terms():
    for product in (rg.PRODUCT_DERIVATIVE, rg.PRODUCT_MARGIN, rg.PRODUCT_SHORT):
        assert "(" in rg.PRODUCT_LABELS[product]


def test_every_age_band_has_a_vietnamese_label():
    for band in rg.AGE_BANDS + (rg.AGE_UNKNOWN,):
        assert rg.AGE_LABELS[band].strip()
