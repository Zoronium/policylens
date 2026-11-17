import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth, main
from tests.conftest import PAGES, StubLLM, good_reply

TEXT = "--- Page 1 ---\n" + PAGES[0] + "\n--- Page 2 ---\n" + PAGES[1]
DOMAIN = "test-app.clerk.accounts.dev"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(sub="user_a", key=KEY, iss=f"https://{DOMAIN}", exp_in=300):
    return jwt.encode({"sub": sub, "iss": iss, "exp": int(time.time()) + exp_in}, key, "RS256")


def bearer(**kw):
    return {"Authorization": f"Bearer {token(**kw)}"}


@pytest.fixture(autouse=True)
def clerk(monkeypatch, client):
    pk = "pk_test_" + base64.b64encode(f"{DOMAIN}$".encode()).decode()
    monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", pk)
    monkeypatch.setattr(auth, "signing_key", lambda tok, domain: KEY.public_key())
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))


def make(client, **kw):
    r = client.post("/policies", data={"text": TEXT}, **kw)
    assert r.status_code == 201
    return r.json()["id"]


def test_domain_comes_from_the_publishable_key():
    pk = "pk_test_" + base64.b64encode(b"example-app.clerk.accounts.dev$").decode().rstrip("=")
    assert auth.clerk_domain(pk) == "example-app.clerk.accounts.dev"


def test_signed_out_policy_stays_open_by_id(client):
    pid = make(client)
    assert client.get(f"/policies/{pid}").status_code == 200


def test_signed_in_policy_is_private_to_its_owner(client):
    pid = make(client, headers=bearer(sub="user_a"))
    assert client.get(f"/policies/{pid}", headers=bearer(sub="user_a")).status_code == 200
    assert client.get(f"/policies/{pid}", headers=bearer(sub="user_b")).status_code == 404
    assert client.get(f"/policies/{pid}").status_code == 404


def test_estimate_respects_ownership(client):
    pid = make(client, headers=bearer(sub="user_a"))
    body = {
        "policy_id": pid,
        "scenario": {
            "procedure": "x",
            "days_admitted": 1,
            "room_rent_per_day": "1000",
            "charges": {"room": "1000"},
            "policy_age_days": 400,
        },
    }
    assert client.post("/estimate", json=body, headers=bearer(sub="user_a")).status_code == 200
    assert client.post("/estimate", json=body, headers=bearer(sub="user_b")).status_code == 404


def test_my_policies_lists_only_mine_newest_first(client):
    a1 = make(client, headers=bearer(sub="user_a"))
    a2 = make(client, headers=bearer(sub="user_a"))
    make(client, headers=bearer(sub="user_b"))
    make(client)  # signed out: belongs to nobody
    got = client.get("/me/policies", headers=bearer(sub="user_a")).json()
    assert [p["id"] for p in got] == [a2, a1]


def test_my_policies_needs_sign_in(client):
    assert client.get("/me/policies").status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": f"Bearer {token(key=OTHER_KEY)}"},  # signed with the wrong key
        {"Authorization": f"Bearer {token(exp_in=-60)}"},  # expired
        {"Authorization": f"Bearer {token(iss='https://evil.example')}"},  # wrong issuer
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic abc"},
    ],
)
def test_bad_tokens_are_401_not_anonymous(client, headers):
    assert client.get("/me/policies", headers=headers).status_code == 401
    assert client.post("/policies", data={"text": TEXT}, headers=headers).status_code == 401


def test_token_without_server_config_is_401(client, monkeypatch):
    monkeypatch.delenv("CLERK_PUBLISHABLE_KEY")
    assert client.get("/me/policies", headers=bearer()).status_code == 401
