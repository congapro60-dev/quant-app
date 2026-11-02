"""Giao diện sáng/tối: đủ màu, đọc được, không gắn cứng màu trong CSS."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import theme_ui as tu

ROOT = Path(__file__).resolve().parents[1]


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_both_palettes_define_the_same_variables():
    assert set(tu.PALETTES[tu.LIGHT]) == set(tu.PALETTES[tu.DARK])


@pytest.mark.parametrize("theme", [tu.LIGHT, tu.DARK])
@pytest.mark.parametrize("fg,bg", [("text", "app-bg"), ("text", "surface"), ("muted", "app-bg"),
                                   ("eyebrow", "app-bg"), ("tab-active-text", "tab-active-bg"),
                                   ("danger", "surface"), ("success", "surface")])
def test_text_is_readable(theme, fg, bg):
    palette = tu.PALETTES[theme]
    assert _contrast(palette[fg], palette[bg]) >= 4.5, (theme, fg, bg)


def test_css_has_no_hard_coded_colours():
    assert re.findall(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", tu._CSS) == []


def test_every_variable_used_in_css_is_defined():
    used = set(re.findall(r"var\(--qa-([a-z0-9-]+)\)", tu._CSS))
    assert used <= set(tu.PALETTES[tu.LIGHT])


def test_build_css_switches_palette_and_falls_back_to_dark():
    assert tu.PALETTES[tu.LIGHT]["app-bg"] in tu.build_css(tu.LIGHT)
    assert tu.PALETTES[tu.DARK]["app-bg"] in tu.build_css(tu.DARK)
    assert tu.PALETTES[tu.DARK]["app-bg"] in tu.build_css("la")


def test_config_declares_both_themes_without_forcing_one():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    theme = config["theme"]
    assert "backgroundColor" not in theme and "base" not in theme
    assert _luminance(theme["light"]["backgroundColor"]) > 0.8
    assert _luminance(theme["dark"]["backgroundColor"]) < 0.1


def test_app_still_boots():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception
