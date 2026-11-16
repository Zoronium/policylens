import pymupdf

from app import main
from app.llm import LLMNotConfigured
from tests.conftest import PAGES, StubLLM, good_reply

TEXT = "--- Page 1 ---\n" + PAGES[0] + "\n--- Page 2 ---\n" + PAGES[1]


def test_post_then_get_round_trip(client, monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    r = client.post("/policies", data={"text": TEXT})
    assert r.status_code == 201
    body = r.json()
    assert body["coverage"]["sum_insured"]["value"] == "500000"  # money travels as a string
    assert body["pages"] == PAGES
    got = client.get(f"/policies/{body['id']}").json()
    assert got["coverage"] == body["coverage"]


def test_low_confidence_fields_are_listed_for_review(client, monkeypatch):
    reply = good_reply()
    reply["co_pay_pct"]["confidence"] = 0.4
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(reply))
    body = client.post("/policies", data={"text": TEXT}).json()
    assert body["needs_human_review"] is True
    assert "co_pay_pct" in body["review_fields"]
    assert body["coverage"]["co_pay_pct"]["needs_review"] is True
    assert body["coverage"]["sum_insured"]["needs_review"] is False


def test_upload_plain_text_file(client, monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    r = client.post("/policies", files={"file": ("p.txt", TEXT.encode(), "text/plain")})
    assert r.status_code == 201 and r.json()["source_name"] == "p.txt"


def test_upload_pdf_keeps_page_numbers(client, monkeypatch):
    doc = pymupdf.open()
    for t in PAGES:
        doc.new_page().insert_text((72, 72), t[:60])
    monkeypatch.setattr(main, "get_llm", lambda: StubLLM(good_reply()))
    r = client.post("/policies", files={"file": ("p.pdf", doc.tobytes(), "application/pdf")})
    assert r.status_code == 201 and len(r.json()["pages"]) == 2


def test_missing_llm_key_is_a_clear_503(client, monkeypatch):
    def boom():
        raise LLMNotConfigured("LLM_API_KEY is not set.")

    monkeypatch.setattr(main, "get_llm", boom)
    r = client.post("/policies", data={"text": TEXT})
    assert r.status_code == 503 and "LLM_API_KEY" in r.json()["detail"]


def test_neither_or_both_inputs_rejected(client):
    assert client.post("/policies").status_code == 422
    r = client.post("/policies", data={"text": "x"}, files={"file": ("a.txt", b"y")})
    assert r.status_code == 422


def test_unknown_policy_404(client):
    assert client.get("/policies/nope").status_code == 404


def test_samples_listed_and_marked_synthetic(client):
    samples = client.get("/samples").json()
    assert len(samples) == 3 and all("SYNTHETIC" in s["text"] for s in samples)
