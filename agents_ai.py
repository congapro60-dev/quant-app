"""Small, opt-in client for the public Agents AI HungLeAI consult route.

The credential is supplied at runtime and never logged or persisted.  The
client accepts a Firebase bearer token or a future scoped API key; the server
decides which credential type is valid.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://agents.ai.vn/api"
AGENT_SLUG = "hungle-stock-dashboard"
CONSULT_URL = f"{BASE_URL}/agents/{AGENT_SLUG}/consult"
DASHBOARD_SESSION_URL = f"{BASE_URL}/agents/{AGENT_SLUG}/dashboard-session"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class AgentsAIError(RuntimeError):
    """Redacted, user-actionable error from Agents AI."""


@dataclass(frozen=True)
class AgentsAIResponse:
    text: str
    cost_credits: float | None = None
    model: str = ""


def _credential(value: str) -> str:
    token = str(value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token or any(ord(char) < 32 for char in token):
        raise AgentsAIError("Bearer credential (token/API key) trống hoặc không hợp lệ.")
    return token


def _error_detail(exc: Exception, credential: str = "") -> str:
    raw = " ".join(str(exc).split())
    if credential:
        raw = raw.replace(credential, "[REDACTED]")
    raw = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,]+", r"\1[REDACTED]", raw)
    return raw[:240] or type(exc).__name__


def _headers(credential: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {credential}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
        "User-Agent": "Quant-App/agents-ai-consult",
    }


def _read_response(response) -> bytes:
    data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise AgentsAIError("Phản hồi Agents AI vượt giới hạn 2 MB.")
    return data


def _parse_sse(raw: str) -> AgentsAIResponse:
    text_parts: list[str] = []
    cost: float | None = None
    model = ""
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            item = json.loads(payload)
        except json.JSONDecodeError:
            text_parts.append(payload)
            continue
        if isinstance(item, dict):
            delta = item.get("text") or item.get("content") or item.get("answer")
            if isinstance(delta, str):
                text_parts.append(delta)
            if item.get("cost_credits") is not None:
                try:
                    cost = float(item["cost_credits"])
                except (TypeError, ValueError):
                    pass
            if isinstance(item.get("model"), str):
                model = item["model"]
    return AgentsAIResponse("".join(text_parts).strip(), cost, model)


def _parse_json(raw: bytes) -> AgentsAIResponse:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentsAIError("Agents AI trả về dữ liệu không đọc được.") from exc
    if isinstance(payload, dict):
        text = payload.get("text") or payload.get("answer") or payload.get("content")
        if not text and isinstance(payload.get("messages"), list):
            text = "\n".join(
                str(item.get("text", item.get("content", "")))
                for item in payload["messages"] if isinstance(item, dict)
            )
        if isinstance(text, str):
            cost = payload.get("cost_credits")
            try:
                cost = float(cost) if cost is not None else None
            except (TypeError, ValueError):
                cost = None
            return AgentsAIResponse(text.strip(), cost, str(payload.get("model", "")))
    raise AgentsAIError("Agents AI không trả về nội dung phân tích văn bản.")


def consult(
    question: str,
    credential: str,
    *,
    symbol: str = "",
    timeout: float = 45.0,
) -> AgentsAIResponse:
    """Ask HungLeAI about one symbol; opt-in network call only."""

    token = _credential(credential)
    question = str(question or "").strip()
    if not question:
        raise AgentsAIError("Câu hỏi Agents AI trống.")
    payload = {"symbol": str(symbol or "").strip().upper(), "question": question}
    request = Request(
        CONSULT_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(token),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = _read_response(response)
            content_type = str(response.headers.get("Content-Type", "")).lower()
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(512).decode("utf-8", errors="replace")
        except Exception:
            pass
        raise AgentsAIError(f"Agents AI HTTP {exc.code}: {_error_detail(Exception(body), token)}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AgentsAIError(f"Không kết nối được Agents AI: {_error_detail(exc, token)}") from exc
    if "event-stream" in content_type or b"data:" in raw[:2000]:
        result = _parse_sse(raw.decode("utf-8", errors="replace"))
    else:
        result = _parse_json(raw)
    if not result.text:
        raise AgentsAIError("Agents AI trả về phản hồi rỗng.")
    return result


def dashboard_url() -> str:
    """Public dashboard entry; an authenticated session is created by the site."""

    return "https://agents.ai.vn/agents/stock-ai"
