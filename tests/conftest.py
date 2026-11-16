import json

import pytest
from fastapi.testclient import TestClient

from app import main


class StubLLM:
    """Returns canned replies in order (the last one repeats) and records every call."""

    model = "stub"

    def __init__(self, *replies):
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls: list[list[dict]] = []

    def chat_json(self, messages):
        self.calls.append(list(messages))
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]


def cited(value, page=1, quote="q", conf=0.95):
    return {"value": value, "source_page": page, "source_quote": quote, "confidence": conf}


PAGES = [
    "Sum insured: Rs. 5,00,000 per year. Co-payment: You pay 10% of every admissible claim.",
    "Cataract surgery is limited to Rs. 40,000 per eye. Cosmetic surgery is not covered.",
]


def good_reply():
    return {
        "sum_insured": cited(500000, 1, "Sum insured: Rs. 5,00,000 per year"),
        "co_pay_pct": cited(10, 1, "You pay 10% of every admissible claim"),
        "sub_limits": [
            cited(
                {"procedure": "cataract", "limit": 40000},
                2,
                "Cataract surgery is limited to Rs. 40,000 per eye",
            )
        ],
        "exclusions": [cited("cosmetic surgery", 2, "Cosmetic surgery is not covered")],
    }


@pytest.fixture(autouse=True)
def _fresh_limits(monkeypatch):
    from app.ratelimit import limiter

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)  # a developer's .env must not leak into tests
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setenv("REVIEW_THRESHOLD", "0.7")
    with TestClient(main.app) as c:
        yield c
