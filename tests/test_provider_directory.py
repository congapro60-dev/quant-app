"""Kiểm thử danh bạ nhà cung cấp: đủ trường, trung lập, không suy diễn."""

from __future__ import annotations

import pytest

import provider_directory as pd_


REQUIRED_FIELDS = (
    "legal_name",
    "official_url",
    "products",
    "membership_source",
    "age_policy",
    "age_policy_source",
    "verified_at",
    "verification_status",
)

REQUIRED_KEYS = {
    "ssi", "mbs", "tcbs", "vndirect", "vietcap", "hsc", "vnsc", "dragonx",
}


def test_directory_contains_the_eight_required_providers():
    assert REQUIRED_KEYS <= {p.key for p in pd_.all_providers()}


def test_momo_channel_is_listed_with_its_operating_broker():
    """MoMo là kênh phân phối; pháp nhân chịu trách nhiệm là CVS."""

    momo = pd_.get_provider("momo_cvs")
    assert momo is not None
    assert "CVS" in momo.legal_name
    assert pd_.P_WARRANT in momo.products
    assert pd_.P_DERIVATIVE not in momo.products


def test_covered_warrant_is_flagged_as_leveraged_in_notes():
    momo = pd_.get_provider("momo_cvs")
    joined = " ".join(momo.notes).lower()
    assert "đòn bẩy" in joined


def test_hotline_shows_when_it_has_its_own_source():
    """Tổng đài và chính sách tuổi là hai dữ kiện độc lập."""

    ssi = pd_.get_provider("ssi")
    assert ssi.verification_status != pd_.STATUS_VERIFIED
    assert ssi.hotline_display() != pd_.UNVERIFIED_NOTICE
    # nhưng chính sách tuổi vẫn phải là chưa xác minh
    assert ssi.age_policy_display() == pd_.UNVERIFIED_NOTICE


def test_hotline_without_source_stays_unverified():
    p = pd_.Provider(
        key="x", legal_name="X", official_url="https://x.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        hotline="1900 1234", hotline_source=None,
    )
    assert p.hotline_display() == pd_.UNVERIFIED_NOTICE


def test_legal_baseline_is_documented_with_a_source():
    assert pd_.LEGAL_BASELINE_NOTE.strip()
    assert pd_.LEGAL_BASELINE_SOURCE.startswith("https://")
    assert "15" in pd_.LEGAL_BASELINE_NOTE


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_every_record_has_all_required_fields(provider):
    for field_name in REQUIRED_FIELDS:
        assert hasattr(provider, field_name), field_name


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_legal_name_and_products_are_filled(provider):
    assert provider.legal_name.strip()
    assert provider.products
    assert provider.membership_source.strip()


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_official_url_is_https_and_affiliate_free(provider):
    assert pd_.is_official_https_url(provider.official_url), provider.official_url
    assert not pd_.has_affiliate_marker(provider.official_url)


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_no_affiliate_marker_anywhere_in_record(provider):
    blob = " ".join(
        str(x) for x in (
            provider.official_url,
            provider.membership_source,
            provider.age_policy_source or "",
            " ".join(provider.notes),
        )
    )
    assert not pd_.has_affiliate_marker(blob)


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_unverified_records_show_the_required_notice(provider):
    """Chưa xác minh thì phải nói rõ, không được hiện chính sách đoán."""

    if not provider.is_verified:
        assert provider.age_policy_display() == pd_.UNVERIFIED_NOTICE
        assert provider.age_policy_source_display() == pd_.UNVERIFIED_NOTICE


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_fee_and_hotline_fields_exist(provider):
    for field_name in ("published_fees", "published_fees_source", "hotline"):
        assert hasattr(provider, field_name), field_name


@pytest.mark.parametrize("provider", list(pd_.PROVIDERS), ids=lambda p: p.key)
def test_fact_without_its_own_source_shows_the_notice(provider):
    """Mỗi dữ kiện tự mang nguồn; thiếu nguồn thì không hiện số."""

    if not provider.published_fees_source:
        assert provider.published_fees_display() == pd_.UNVERIFIED_NOTICE
    if not provider.hotline_source:
        assert provider.hotline_display() == pd_.UNVERIFIED_NOTICE


def test_fee_and_hotline_need_their_own_source_not_the_age_status():
    with_sources = pd_.Provider(
        key="v", legal_name="V", official_url="https://v.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        published_fees="0,15% giá trị giao dịch",
        published_fees_source="https://v.vn/bieu-phi",
        hotline="1900 0000", hotline_source="https://v.vn/lien-he",
    )
    # Chính sách tuổi vẫn chưa xác minh, nhưng hai dữ kiện kia có nguồn riêng.
    assert with_sources.age_policy_display() == pd_.UNVERIFIED_NOTICE
    assert with_sources.published_fees_display() == "0,15% giá trị giao dịch"
    assert with_sources.hotline_display() == "1900 0000"

    no_sources = pd_.Provider(
        key="s", legal_name="S", official_url="https://s.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        verification_status=pd_.STATUS_VERIFIED,
        age_policy="Từ đủ 18 tuổi", age_policy_source="https://s.vn/tos",
        published_fees="0,15%", hotline="1900 1111",
    )
    # Dù bản ghi đã xác minh tuổi, phí và tổng đài thiếu nguồn thì vẫn không hiện.
    assert no_sources.published_fees_display() == pd_.UNVERIFIED_NOTICE
    assert no_sources.hotline_display() == pd_.UNVERIFIED_NOTICE


def test_directory_row_carries_fee_and_hotline_columns():
    row = pd_.directory_rows()[0]
    assert "Phí công bố" in row
    assert "Tổng đài" in row


def test_verification_status_values_are_valid():
    for provider in pd_.PROVIDERS:
        assert provider.verification_status in pd_.VALID_STATUSES


def test_record_marked_verified_must_carry_policy_and_source():
    """Không thể vừa 'đã xác minh' vừa thiếu nội dung hoặc nguồn."""

    good = pd_.Provider(
        key="x", legal_name="X", official_url="https://x.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        age_policy="Từ đủ 18 tuổi", age_policy_source="https://x.vn/dieu-khoan",
        verified_at="2026-08-11", verification_status=pd_.STATUS_VERIFIED,
    )
    assert good.is_verified is True
    assert good.age_policy_display() == "Từ đủ 18 tuổi"

    missing_source = pd_.Provider(
        key="y", legal_name="Y", official_url="https://y.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        age_policy="Từ đủ 18 tuổi", age_policy_source=None,
        verification_status=pd_.STATUS_VERIFIED,
    )
    assert missing_source.is_verified is False
    assert missing_source.age_policy_display() == pd_.UNVERIFIED_NOTICE


def test_expired_status_falls_back_to_notice():
    expired = pd_.Provider(
        key="z", legal_name="Z", official_url="https://z.vn/",
        products=(pd_.P_STOCK,), membership_source=pd_.VSDC_MEMBER_LIST,
        age_policy="Từ đủ 18 tuổi", age_policy_source="https://z.vn/tos",
        verified_at="2020-01-01", verification_status=pd_.STATUS_EXPIRED,
    )
    assert expired.age_policy_display() == pd_.UNVERIFIED_NOTICE


def test_directory_rows_never_leak_none_into_display():
    for row in pd_.directory_rows():
        for key, value in row.items():
            assert value is not None, key
            assert str(value).strip() != "", key


def test_products_are_separated_not_lumped_together():
    """Phái sinh phải tách khỏi cổ phiếu/chứng chỉ quỹ."""

    dragonx = pd_.get_provider("dragonx")
    assert dragonx is not None
    assert pd_.P_DERIVATIVE not in dragonx.products
    assert pd_.P_STOCK not in dragonx.products
    assert pd_.P_FUND in dragonx.products


def test_providers_for_product_filters():
    fund_providers = pd_.providers_for_product(pd_.P_FUND)
    assert any(p.key == "dragonx" for p in fund_providers)
    deriv = pd_.providers_for_product(pd_.P_DERIVATIVE)
    assert all(pd_.P_DERIVATIVE in p.products for p in deriv)


def test_directory_is_alphabetical_not_ranked():
    keys = [p.key for p in pd_.all_providers()]
    assert keys == sorted(keys)


def test_get_provider_is_case_insensitive_and_safe():
    assert pd_.get_provider("SSI") is not None
    assert pd_.get_provider("  ssi ") is not None
    assert pd_.get_provider("khong-ton-tai") is None
    assert pd_.get_provider("") is None


def test_affiliate_detector_catches_common_markers():
    assert pd_.has_affiliate_marker("https://x.vn/?ref=abc") is True
    assert pd_.has_affiliate_marker("https://x.vn/?utm_source=y") is True
    assert pd_.has_affiliate_marker("https://x.vn/mo-tai-khoan") is False
