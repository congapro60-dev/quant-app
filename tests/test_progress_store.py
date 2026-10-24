"""Kiểm tra lưu/khôi phục tiến độ vào localStorage của trình duyệt (Nấc 1).

Component thật cần trình duyệt; ở đây thay bằng giả lập để kiểm tra logic
Python: khôi phục đúng một lần, không đè dữ liệu phiên, dữ liệu hỏng thì bỏ
qua, và phần ghi luôn gửi payload sạch đúng schema hồ sơ.
"""

from __future__ import annotations

import json
from pathlib import Path

import progress_profile as pp
import progress_store


def _component_dir() -> Path:
    return Path(progress_store.__file__).parent / "components" / "qa_progress_store"


def _state_with_scores(scores: dict[str, float]) -> dict:
    profile = pp.empty_profile()
    profile["lesson_scores"] = dict(scores)
    return {"progress_profile": profile}


# ---------------------------------------------------------------------------
# Tệp component
# ---------------------------------------------------------------------------

def test_component_index_html_exists_and_uses_expected_key():
    path = _component_dir() / "index.html"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert progress_store.STORAGE_KEY in text
    assert "streamlit:setComponentValue" in text
    assert "streamlit:componentReady" in text
    assert "streamlit:setFrameHeight" in text


# ---------------------------------------------------------------------------
# Chuẩn bị payload ghi xuống
# ---------------------------------------------------------------------------

def test_payload_from_state_roundtrips_through_checkpoint_rules():
    state = _state_with_scores({"b1": 80.0, "b2": 55.5})
    payload = progress_store.payload_from_state(state)
    assert payload is not None
    restored = pp.import_json(json.dumps(payload, ensure_ascii=False))
    assert restored["lesson_scores"] == {"b1": 80.0, "b2": 55.5}


def test_payload_from_state_without_profile_is_none():
    assert progress_store.payload_from_state({}) is None
    assert progress_store.payload_from_state({"progress_profile": "x"}) is None


# ---------------------------------------------------------------------------
# Khôi phục
# ---------------------------------------------------------------------------

def test_restore_hydrates_empty_profile_and_counts_passed(monkeypatch):
    stored = pp.empty_profile()
    pp.record_lesson(stored, "b1", 80)
    pp.record_lesson(stored, "b2", 60)
    monkeypatch.setattr(
        progress_store, "_component",
        lambda **kw: json.loads(pp.export_json(stored)),
    )

    state = _state_with_scores({})
    passed = progress_store.restore_progress(state)

    assert passed == 1
    assert state["progress_profile"]["lesson_scores"]["b1"] == 80
    assert state[progress_store.RESTORE_BANNER] == 1


def test_restore_runs_once_per_session_and_never_overwrites_new_work(monkeypatch):
    stored = pp.empty_profile()
    pp.record_lesson(stored, "b1", 80)
    monkeypatch.setattr(
        progress_store, "_component",
        lambda **kw: json.loads(pp.export_json(stored)),
    )

    state = _state_with_scores({})
    assert progress_store.restore_progress(state) == 1
    # Học sinh làm tiếp trong phiên: điểm mới phải thắng dữ liệu cũ.
    state["progress_profile"]["lesson_scores"]["b1"] = 90
    pp.record_lesson(state["progress_profile"], "b3", 100)
    assert progress_store.restore_progress(state) == 0
    assert state["progress_profile"]["lesson_scores"]["b1"] == 90
    assert state["progress_profile"]["lesson_scores"]["b3"] == 100


def test_restore_skips_storage_when_session_already_has_progress(monkeypatch):
    stored = pp.empty_profile()
    pp.record_lesson(stored, "cu", 80)
    monkeypatch.setattr(
        progress_store, "_component",
        lambda **kw: json.loads(pp.export_json(stored)),
    )

    state = _state_with_scores({"moi": 75.0})
    assert progress_store.restore_progress(state) == 0
    assert state["progress_profile"]["lesson_scores"] == {"moi": 75.0}
    assert progress_store.RESTORE_BANNER not in state


def test_restore_ignores_unsafe_or_corrupt_storage(monkeypatch):
    monkeypatch.setattr(
        progress_store, "_component",
        lambda **kw: {"lesson_scores": {"x": "not-a-number"}, "khoa_la": 1},
    )
    state = _state_with_scores({})
    assert progress_store.restore_progress(state) == 0
    assert state["progress_profile"] == pp.empty_profile()
    assert progress_store.RESTORE_BANNER not in state


def test_restore_tolerates_component_returning_none(monkeypatch):
    monkeypatch.setattr(progress_store, "_component", lambda **kw: None)
    state = _state_with_scores({})
    assert progress_store.restore_progress(state) == 0
    assert progress_store.RESTORE_BANNER not in state


def test_restore_tolerates_component_error(monkeypatch):
    def boom(**kw):
        raise RuntimeError("không có trình duyệt")

    monkeypatch.setattr(progress_store, "_component", boom)
    state = _state_with_scores({})
    assert progress_store.restore_progress(state) == 0


# ---------------------------------------------------------------------------
# Ghi xuống
# ---------------------------------------------------------------------------

def test_persist_sends_clean_payload_in_save_mode(monkeypatch):
    seen: dict = {}

    def fake_component(**kw):
        seen.update(kw)
        return None

    monkeypatch.setattr(progress_store, "_component", fake_component)
    state = _state_with_scores({"b1": 80.0})

    assert progress_store.persist_progress(state) is True
    assert seen["mode"] == "save"
    assert set(seen["payload"]) == pp.TOP_LEVEL_KEYS
    assert seen["payload"]["lesson_scores"] == {"b1": 80.0}


def test_persist_without_profile_is_silent_noop(monkeypatch):
    called: list = []
    monkeypatch.setattr(progress_store, "_component", lambda **kw: called.append(kw))
    assert progress_store.persist_progress({}) is False
    assert called == []


# ---------------------------------------------------------------------------
# Ngưỡng đạt
# ---------------------------------------------------------------------------

def test_passed_lesson_count_uses_pass_score():
    scores = {"dat": 70, "truot": 69.9, "tot": 100.0}
    assert progress_store.passed_lesson_count({"lesson_scores": scores}) == 2
    assert progress_store.passed_lesson_count(None) == 0
    assert progress_store.passed_lesson_count({"lesson_scores": {"x": "abc"}}) == 0
