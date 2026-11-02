"""Trang Hướng dẫn: đủ chức năng, chỉ nói về thứ có thật, dựng không lỗi."""
from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

import account_help
import feature_guides as fg
import learning_modes as lmode
import user_guide as ug

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")


def _source_without_guide() -> str:
    skip = {"user_guide.py"}
    return "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("*.py") if p.name not in skip)


def _guide_text() -> str:
    parts = [b for _, b in ug.STUDENT_STEPS] + [b for _, b in ug.TEACHER_STEPS]
    parts += [a for _, a in ug.FAQ]
    return "\n".join(parts)


def test_every_bold_label_in_the_guide_exists_in_the_app():
    """Luật repo: không khẳng định tính năng chưa có. Nút đổi tên thì test này đỏ."""
    source = _source_without_guide()
    labels = set()
    for chunk in re.findall(r"\*\*(.+?)\*\*", _guide_text()):
        labels.update(part.strip() for part in chunk.split("→"))
    missing = [label for label in labels if label not in source]
    assert missing == [], f"Hướng dẫn nhắc tới nhãn không có trong app: {missing}"


def test_guard_above_catches_a_made_up_button(monkeypatch):
    fake = ((("Nút giả"), "Bấm **Nút không tồn tại**."),)
    monkeypatch.setattr(ug, "STUDENT_STEPS", fake)
    source = _source_without_guide()
    chunks = re.findall(r"\*\*(.+?)\*\*", _guide_text())
    assert "Nút không tồn tại" in chunks and "Nút không tồn tại" not in source


def test_feature_map_covers_every_area():
    for area in lmode.AREA_ORDER:
        has_features = bool(lmode.features_in_area(area, list(lmode.FEATURES)))
        assert has_features or ug.EXTRA_ITEMS.get(area), area


def test_every_feature_has_a_description_for_the_map():
    for key in lmode.FEATURES:
        assert fg.get_guide(key) is not None, key


def test_tab_is_visible_to_guests_and_renders_all_sections():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert ug.GUIDE_LABEL in labels
    for section in ("Học sinh", "Giáo viên", "Tất cả chức năng", "Câu hỏi thường gặp"):
        assert section in labels, section
    expanders = [e.label for e in at.expander]
    assert "Em quên mật khẩu thì sao?" in expanders
    assert lmode.AREA_LABELS[lmode.AREA_MODEL_LAB] in expanders


def test_teacher_steps_mention_the_invite_requirement():
    assert "mã mời" in " ".join(b for _, b in ug.TEACHER_STEPS).lower()


def test_forgot_password_is_honest_and_shown_at_login():
    joined = " ".join(account_help.FORGOT_PASSWORD_STEPS)
    assert "Không ai lấy lại được" in joined
    assert "tài khoản mới" in joined
    at = AppTest.from_string(
        "import classroom_self_ui as ui\n"
        "from firebase_classroom import FirebaseClassroom, PROJECT_ID\n"
        "ui.entry(FirebaseClassroom({'project_id': PROJECT_ID, 'api_key': 'x'}))\n",
        default_timeout=30,
    ).run()
    assert not at.exception
    assert "Quên mật khẩu?" in [e.label for e in at.expander]
