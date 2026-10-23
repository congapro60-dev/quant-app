import pytest
from streamlit.testing.v1 import AppTest

import curriculum as cur
import curriculum_university as uni
from muse_brief import build_learning_brief, PURPOSE_LABELS


@pytest.mark.parametrize("lessons,audience", [(cur.all_lessons(), "thpt"), (uni.all_lessons(), "dai_hoc")])
def test_briefs_use_actual_lessons_and_distinct_learning_goals(lessons, audience):
    for lesson in lessons:
        variants = [build_learning_brief(lesson, purpose, audience) for purpose in PURPOSE_LABELS]
        assert len(set(variants)) == 3
        for brief in variants:
            assert lesson.title in brief and lesson.objective in brief
            assert lesson.example in brief and lesson.interactive in brief
            assert "không đặt lệnh" in brief and "chi phí; chờ xác nhận" in brief
            for name, _ in lesson.resources:
                assert name in brief


@pytest.mark.parametrize("purpose,audience", [("buy", "thpt"), ("review", "unknown")])
def test_invalid_brief_options_rejected(purpose, audience):
    with pytest.raises(ValueError):
        build_learning_brief(cur.all_lessons()[0], purpose, audience)


def test_workshop_does_not_export_private_session_fields():
    at = AppTest.from_string("from muse_brief import render_muse_workshop\nrender_muse_workshop()", default_timeout=30)
    for key in ("api_key_val", "paper_ledger", "progress_profile"):
        at.session_state[key] = "PRIVATE_SENTINEL_53812"
    at.run()
    assert not at.exception
    assert "PRIVATE_SENTINEL_53812" not in " ".join(c.value for c in at.code)
    at.radio(key="muse_purpose").set_value("review").run()
    assert "3 câu chẩn đoán" in at.code[0].value
    assert not at.exception


def test_workshop_offers_muse_and_alternative_ai_links():
    """Muse có thể bị chặn tại Việt Nam nên tab phải chỉ sẵn AI thay thế."""

    at = AppTest.from_string("from muse_brief import render_muse_workshop\nrender_muse_workshop()", default_timeout=30)
    at.run()
    assert not at.exception
    labels = [link.label for link in at.get("link_button")]
    for expected in ("Mở Muse", "Mở ChatGPT", "Mở Gemini", "Mở Copilot", "Mở Zalo AI"):
        assert expected in labels
    infos = " ".join(info.value for info in at.info)
    assert "không truy cập được từ Việt Nam" in infos
