import pytest

from app import access, main
from tests.conftest import PAGES, StubLLM, good_reply

TEXT = "--- Page 1 ---\n" + PAGES[0] + "\n--- Page 2 ---\n" + PAGES[1]
SECRET = "test-admin-token-0123456789"


@pytest.fixture
def secured(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", SECRET)
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    return client


def _login(client):
    code = access.code_for(access.current_window())
    r = client.post("/auth/login", json={"code": code})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_code_is_stable_within_the_hour_and_changes_after(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", SECRET)
    assert access.code_for(5) == access.code_for(5)
    assert access.code_for(5) != access.code_for(6)
    t = 10 * 3600
    code = access.code_for(access.current_window(t))
    assert access.verify_code(code, now=t + 3599)
    assert not access.verify_code(code, now=t + 3600)  # the hour rolled over


def test_code_depends_on_the_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", SECRET)
    a = access.code_for(7)
    monkeypatch.setenv("ADMIN_TOKEN", SECRET + "x")
    assert access.code_for(7) != a


def test_code_input_is_forgiving_about_case_dash_and_spaces(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", SECRET)
    code = access.code_for(access.current_window())
    assert access.verify_code(" " + code.lower().replace("-", " ") + " ")
    assert not access.verify_code("")


def test_session_tokens_expire_and_cannot_be_forged(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", SECRET)
    token, exp = access.issue_session(now=1000)
    assert access.verify_session(token, now=1000 + 3599)
    assert not access.verify_session(token, now=exp)
    assert not access.verify_session(f"{exp + 10_000}.{token.split('.')[1]}", now=1000)
    assert not access.verify_session("garbage") and not access.verify_session("")


def test_short_admin_token_is_refused(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "short")
    with pytest.raises(RuntimeError):
        access.check_config()


def test_auth_is_off_without_admin_token(client, monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    assert client.get("/health").json()["auth_required"] is False
    assert client.post("/policies", data={"text": TEXT}).status_code == 201
    assert client.post("/auth/login", json={"code": "x"}).status_code == 404


def test_extraction_needs_a_session_when_auth_is_on(secured):
    assert secured.get("/health").json()["auth_required"] is True
    assert secured.post("/policies", data={"text": TEXT}).status_code == 401
    bad = {"Authorization": "Bearer 1.deadbeef"}
    assert secured.post("/policies", data={"text": TEXT}, headers=bad).status_code == 401
    stale = {"Authorization": f"Bearer {access.issue_session(now=0)[0]}"}
    assert secured.post("/policies", data={"text": TEXT}, headers=stale).status_code == 401
    ok = secured.post("/policies", data={"text": TEXT}, headers=_login(secured))
    assert ok.status_code == 201


def test_wrong_code_is_rejected_and_logins_are_rate_limited(secured):
    for _ in range(10):
        assert secured.post("/auth/login", json={"code": "AAAA-AAAA"}).status_code == 401
    r = secured.post("/auth/login", json={"code": "AAAA-AAAA"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_estimate_and_reads_stay_open_without_a_code(secured):
    pid = secured.post("/policies", data={"text": TEXT}, headers=_login(secured)).json()["id"]
    assert secured.get(f"/policies/{pid}").status_code == 200
    body = {"policy_id": pid, "scenario": {"procedure": "x", "days_admitted": 1}}
    assert secured.post("/estimate", json=body).status_code != 401


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
