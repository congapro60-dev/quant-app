"""Kiểm thử tầng AI dùng chung đọc cấu hình từ Secrets."""

from __future__ import annotations

import analytics
from shared_ai import SECTION, shared_ai_config


def test_shared_config_resolves_full_section():
    config, note = shared_ai_config({
        SECTION: {
            "api_key": "k-shared",
            "base_url": "https://router.example/v1",
            "model": "model-a",
        },
    })

    assert config is not None
    assert note == ""
    assert config["provider"] == analytics.OPENAI_COMPATIBLE_PROVIDER
    assert config["api_key"] == "k-shared"
    assert config["base_url"] == "https://router.example/v1"
    assert config["model"] == "model-a"
    assert config["display_name"] == "AI dùng chung của trang"


def test_shared_config_defaults_to_missing_notice():
    config, note = shared_ai_config({})

    assert config is None
    assert "Secrets" in note


def test_shared_config_lists_missing_fields():
    config, note = shared_ai_config({SECTION: {"api_key": "k-shared"}})

    assert config is None
    assert "base_url" in note
    assert "model" in note


def test_shared_config_rejects_non_mapping_section():
    config, note = shared_ai_config({SECTION: "oops"})

    assert config is None
    assert note


def test_shared_config_uses_display_name():
    config, _note = shared_ai_config({
        SECTION: {
            "api_key": "k-shared",
            "base_url": "https://r.example/v1",
            "model": "m",
            "display_name": "GLM của trường",
        },
    })

    assert config["display_name"] == "GLM của trường"
