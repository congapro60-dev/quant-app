"""Kiểm tra dấu "nhớ đăng nhập" trong trình duyệt (thuần, không cần mạng)."""
import time

import account_store as store


def _valid(**over):
    payload = {
        "version": 1,
        "username": "hoc-sinh-01",
        "uid": "uid-1",
        "kind": "student",
        "display_name": "Nguyễn An",
        "refresh_token": "r" * 40,
        "saved_at": time.time(),
    }
    payload.update(over)
    return payload


def test_sanitize_accepts_valid_marker():
    clean = store.sanitize(_valid())
    assert clean and clean["username"] == "hoc-sinh-01" and clean["kind"] == "student"


def test_sanitize_rejects_tampered_or_partial_markers():
    assert store.sanitize(None) is None
    assert store.sanitize("not-a-dict") is None
    assert store.sanitize(_valid(extra="x")) is None          # lạ trường
    assert store.sanitize(_valid(kind="admin")) is None        # sai vai trò
    assert store.sanitize(_valid(refresh_token="short")) is None
    assert store.sanitize(_valid(refresh_token=None)) is None
    assert store.sanitize(_valid(display_name="  ")) is None
    assert store.sanitize(_valid(uid="")) is None
    assert store.sanitize(_valid(saved_at=True)) is None        # bool không phải mốc thời gian
    assert store.sanitize(_valid(saved_at="2026")) is None
    assert store.sanitize(_valid(username="x" * 200)) is None


def test_payload_from_session_requires_full_identity():
    class Session:
        uid = "uid-9"
        refresh_token = "t" * 40

    profile = {"kind": "teacher", "display_name": "Cô Hồng"}
    payload = store.payload_from_session(Session(), profile, "co-hong")
    assert payload and payload["kind"] == "teacher" and payload["uid"] == "uid-9"
    assert store.payload_from_session(Session(), {"kind": "none"}, "co-hong") is None
    assert store.payload_from_session(Session(), profile, "") is None
    assert store.payload_from_session(Session(), {"kind": "teacher"}, "co-hong") is None


def test_marker_expires_after_max_age():
    assert store.MAX_AGE_DAYS == 30
    now = time.time()
    assert store.is_fresh(_valid(saved_at=now), now=now)
    assert store.is_fresh(_valid(saved_at=now - 29 * 24 * 3600), now=now)
    assert not store.is_fresh(_valid(saved_at=now - 31 * 24 * 3600), now=now)
    assert not store.is_fresh(_valid(saved_at=now + 600), now=now)   # mốc ở tương lai
    assert not store.is_fresh({"saved_at": None}, now=now)
