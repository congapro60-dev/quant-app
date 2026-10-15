import json

import pytest

import agents_ai


class _Response:
    def __init__(self, body: bytes, content_type: str):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self, _limit):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_consult_posts_symbol_and_parses_sse_without_exposing_credential(monkeypatch):
    calls = {}

    def fake_open(request, timeout):
        calls["url"] = request.full_url
        calls["auth"] = request.headers["Authorization"]
        calls["body"] = json.loads(request.data.decode("utf-8"))
        calls["timeout"] = timeout
        return _Response(
            b'data: {"text":"PVT "}\n\ndata: {"text":"tham khao","cost_credits":5,"model":"hung"}\n\n',
            "text/event-stream",
        )

    monkeypatch.setattr(agents_ai, "urlopen", fake_open)
    result = agents_ai.consult("Phân tích dòng tiền", "secret-token", symbol="pvt")
    assert result.text == "PVT tham khao"
    assert result.cost_credits == 5
    assert calls["url"] == agents_ai.CONSULT_URL
    assert calls["auth"] == "Bearer secret-token"
    assert calls["body"] == {"symbol": "PVT", "question": "Phân tích dòng tiền"}
    assert calls["timeout"] == 45.0


def test_consult_accepts_json_response(monkeypatch):
    monkeypatch.setattr(
        agents_ai,
        "urlopen",
        lambda *_args, **_kwargs: _Response(
            json.dumps({"answer": "Không đủ dữ liệu.", "cost_credits": 2}).encode(),
            "application/json",
        ),
    )
    result = agents_ai.consult("Có nên mua?", "Bearer key", symbol="CTG")
    assert result.text == "Không đủ dữ liệu."
    assert result.cost_credits == 2


def test_credential_and_question_are_required():
    with pytest.raises(agents_ai.AgentsAIError):
        agents_ai.consult("x", "")
    with pytest.raises(agents_ai.AgentsAIError):
        agents_ai.consult("", "token")


def test_dashboard_public_entry_is_not_a_secret_or_session_url():
    assert agents_ai.dashboard_url() == "https://agents.ai.vn/agents/stock-ai"
