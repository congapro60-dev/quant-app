"""Kiểm thử: mọi chức năng đều phải có phần giới thiệu và hướng dẫn."""

from __future__ import annotations

import pytest

import feature_guides as fg
import learning_modes as lmode


PANELS = (
    fg.PANEL_READINESS, fg.PANEL_PROVIDERS, fg.PANEL_PROGRESS,
    fg.PANEL_JOURNAL, fg.PANEL_POLICY,
)


def test_every_feature_has_a_guide():
    """Không chức năng nào được để người dùng tự đoán nó làm gì."""

    missing = [name for name in lmode.FEATURES if name not in fg.GUIDES]
    assert missing == [], f"Thiếu hướng dẫn cho: {missing}"


def test_every_extra_panel_has_a_guide():
    missing = [p for p in PANELS if p not in fg.GUIDES]
    assert missing == [], f"Thiếu hướng dẫn cho bảng: {missing}"


def test_guides_cover_all_nine_features_plus_panels():
    assert len(fg.GUIDES) >= len(lmode.FEATURES) + len(PANELS)


@pytest.mark.parametrize("key", sorted(fg.GUIDES), ids=str)
def test_guide_fields_are_filled(key):
    guide = fg.GUIDES[key]
    assert guide.what.strip()
    assert guide.why.strip()
    assert guide.read_result.strip()
    assert guide.caution.strip()


@pytest.mark.parametrize("key", sorted(fg.GUIDES), ids=str)
def test_guide_has_at_least_two_steps(key):
    steps = fg.GUIDES[key].steps
    assert len(steps) >= 2
    for step in steps:
        assert step.strip()


@pytest.mark.parametrize("key", sorted(fg.GUIDES), ids=str)
def test_guide_text_is_vietnamese(key):
    """Hướng dẫn là văn cho người đọc Việt, không được để nguyên tiếng Anh."""

    viet = "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
    guide = fg.GUIDES[key]
    for field_name in ("what", "why", "read_result", "caution"):
        text = getattr(guide, field_name).lower()
        assert any(ch in viet for ch in text), (key, field_name)


def test_guide_rejects_too_few_steps():
    with pytest.raises(ValueError):
        fg.FeatureGuide(
            what="x", why="y", steps=("chỉ một bước",),
            read_result="z", caution="t",
        )


def test_get_guide_returns_none_for_unknown_key():
    assert fg.get_guide("khong_ton_tai") is None
    assert fg.get_guide("") is None


def test_caution_actually_warns_not_just_repeats_what():
    """Phần cảnh báo phải nói điều khác với phần mô tả."""

    for key, guide in fg.GUIDES.items():
        assert guide.caution.strip() != guide.what.strip(), key
        assert guide.caution.strip() != guide.why.strip(), key


def test_intraday_guide_states_the_delay_limitation():
    guide = fg.GUIDES[lmode.FEATURE_INTRADAY]
    joined = (guide.what + guide.caution).lower()
    assert "trễ" in joined


def test_backtest_guide_warns_about_lookahead():
    guide = fg.GUIDES[lmode.FEATURE_BACKTEST]
    assert "t+1" in guide.caution.lower() or "tương lai" in guide.caution.lower()


def test_paper_guide_warns_data_is_session_only():
    guide = fg.GUIDES[lmode.FEATURE_PAPER]
    assert "phiên" in guide.caution.lower() or "tải" in guide.caution.lower()


def test_readiness_guide_states_app_does_not_verify():
    guide = fg.GUIDES[fg.PANEL_READINESS]
    assert "không" in guide.caution.lower()


def test_two_journals_are_distinguished_in_their_guides():
    """Hai mục tên gần giống nhau nên hướng dẫn phải phân biệt rõ."""

    decision = fg.GUIDES[fg.PANEL_JOURNAL]
    policy = fg.GUIDES[fg.PANEL_POLICY]
    assert "Lịch sử thiết lập" in decision.caution
    assert "tự ghi" in policy.what.lower() or "tự ghi" in policy.why.lower()
