from app import main
from tests.conftest import PAGES, StubLLM, good_reply

TEXT = "--- Page 1 ---\n" + PAGES[0] + "\n--- Page 2 ---\n" + PAGES[1]


def test_per_ip_extraction_limit(client, monkeypatch):
    monkeypatch.setenv("EXTRACTIONS_PER_HOUR", "2")
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    assert [client.post("/policies", data={"text": TEXT}).status_code for _ in range(3)] == [
        201,
        201,
        429,
    ]


def test_global_daily_cap_applies_across_clients(client, monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setenv("LLM_DAILY_LIMIT", "2")
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    codes = [
        client.post(
            "/policies", data={"text": TEXT}, headers={"X-Forwarded-For": f"10.0.0.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_forged_forwarded_for_does_not_dodge_the_limit(client, monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setenv("EXTRACTIONS_PER_HOUR", "1")
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    # the proxy appends the real peer last; the client controls only what comes before it
    first = {"X-Forwarded-For": "1.1.1.1, 9.9.9.9"}
    second = {"X-Forwarded-For": "2.2.2.2, 9.9.9.9"}
    assert client.post("/policies", data={"text": TEXT}, headers=first).status_code == 201
    assert client.post("/policies", data={"text": TEXT}, headers=second).status_code == 429


def test_forwarded_for_is_ignored_unless_proxy_is_trusted(client, monkeypatch):
    monkeypatch.setenv("EXTRACTIONS_PER_HOUR", "1")
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    codes = [
        client.post(
            "/policies", data={"text": TEXT}, headers={"X-Forwarded-For": f"10.0.0.{i}"}
        ).status_code
        for i in range(2)
    ]
    assert codes == [201, 429]


def test_llm_failure_does_not_echo_provider_detail(client, monkeypatch):
    from app.llm import LLMError

    def boom():
        raise LLMError("401 from https://secret-host.example/v1?key=abc123")

    monkeypatch.setattr(main, "get_llm", boom)
    r = client.post("/policies", data={"text": TEXT})
    assert r.status_code == 502 and "secret-host" not in r.text and "abc123" not in r.text
