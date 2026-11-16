import httpx
import pytest

from app import llm
from app.llm import LLMClient, LLMError


def make(responses, monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return calls


def resp(status, json=None, headers=None):
    return httpx.Response(
        status, json=json, headers=headers, request=httpx.Request("POST", "http://x")
    )


OK = {"choices": [{"message": {"content": "{}"}}]}


def test_retries_429_then_succeeds(monkeypatch):
    calls = make([resp(429, headers={"retry-after": "1"}), resp(200, OK)], monkeypatch)
    assert LLMClient("http://x", "k", "m").chat_json([]) == "{}"
    assert len(calls) == 2


def test_gives_up_after_max_attempts(monkeypatch):
    calls = make([resp(429)], monkeypatch)
    with pytest.raises(LLMError):
        LLMClient("http://x", "k", "m").chat_json([])
    assert len(calls) == llm.MAX_ATTEMPTS


def test_client_error_is_not_retried(monkeypatch):
    calls = make([resp(401)], monkeypatch)
    with pytest.raises(LLMError):
        LLMClient("http://x", "k", "m").chat_json([])
    assert len(calls) == 1
