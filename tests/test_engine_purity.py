import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.conftest import PAGES, StubLLM, good_reply


def test_importing_engine_pulls_in_no_llm_or_network_code():
    code = (
        "import sys, engine\n"
        "bad = [m for m in ('httpx', 'app.llm', 'app.extract', 'openai') if m in sys.modules]\n"
        "sys.exit(1 if bad else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


@pytest.fixture
def stored_policy(client: TestClient, monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    return client.post("/policies", data={"text": "\n--- Page 2 ---\n".join(PAGES)}).json()["id"]


SCENARIO = {
    "procedure": "cataract",
    "days_admitted": 1,
    "room_rent_per_day": "3000",
    "charges": {"doctor": "60000"},
    "policy_age_days": 400,
}


def test_estimate_endpoint_returns_decimal_strings_and_trail(client, stored_policy):
    r = client.post("/estimate", json={"policy_id": stored_policy, "scenario": SCENARIO})
    assert r.status_code == 200
    body = r.json()
    # sub-limit 40000 then 10% co-pay from the stubbed policy
    assert body["payable"] == "36000.00" and body["patient_pays"] == "24000.00"
    assert body["trail"][0]["name"] == "Bill as submitted"


def test_estimate_unknown_policy_404_and_bad_input_422(client, stored_policy):
    assert (
        client.post("/estimate", json={"policy_id": "x", "scenario": SCENARIO}).status_code == 404
    )
    bad = {**SCENARIO, "days_admitted": -1}
    assert (
        client.post("/estimate", json={"policy_id": stored_policy, "scenario": bad}).status_code
        == 422
    )
