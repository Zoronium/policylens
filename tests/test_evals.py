import json
from pathlib import Path

import pytest

from app.extract import annotate_review, extract_policy
from app.pdf import split_pages
from evals import run as evals_run
from evals.score import score_policy, summarise
from tests.conftest import StubLLM

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden"
EXPECTED = json.loads((GOLDEN / "expected.json").read_text(encoding="utf-8"))
EXPECTED.pop("_comment")


def c(value, conf=0.95):
    return {"value": value, "source_page": 1, "source_quote": "zzqq", "confidence": conf}


def oracle_reply(e: dict) -> dict:
    """The perfect extractor for a labelled policy (its quotes will not verify)."""
    return {
        "sum_insured": c(e["sum_insured"]),
        "room_rent_cap": c(e["room_rent_cap"]),
        "icu_cap": c(e["icu_cap"]),
        "co_pay_pct": c(e["co_pay_pct"]),
        "deductible": c(e["deductible"]),
        "sub_limits": [c(s) for s in e["sub_limits"]],
        "waiting_periods": {
            "initial_days": c(e["initial_days"]),
            "pre_existing_months": c(e["pre_existing_months"]),
            "specific_illness": [c(s) for s in e["specific_illness"]],
        },
        "exclusions": [c(x) for x in e["exclusions"]],
        "network_only": c(e["network_only"]),
    }


def run_one(name, reply):
    pages = split_pages((GOLDEN / f"{name}.txt").read_text(encoding="utf-8"))
    cov = annotate_review(extract_policy(pages, StubLLM(reply)), 0.7)
    return cov, pages


def test_golden_set_has_ten_policies_with_text_and_labels():
    assert len(EXPECTED) == 10
    for name in EXPECTED:
        text = (GOLDEN / f"{name}.txt").read_text(encoding="utf-8")
        assert "SYNTHETIC" in text


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_oracle_extraction_scores_perfectly(name):
    cov, pages = run_one(name, oracle_reply(EXPECTED[name]))
    res = score_policy(cov, EXPECTED[name], pages)
    assert all(f["score"] == 1.0 for f in res["fields"].values()), res["fields"]


def test_wrong_number_and_missing_list_item_lower_the_score():
    name = "01_harbor_shield_basic"
    reply = oracle_reply(EXPECTED[name])
    reply["sum_insured"] = c(400000)
    reply["exclusions"] = reply["exclusions"][:2]
    cov, pages = run_one(name, reply)
    f = score_policy(cov, EXPECTED[name], pages)["fields"]
    assert f["sum_insured"]["score"] == 0
    assert 0 < f["exclusions"]["score"] < 1  # precision 1, recall 2/5


def test_null_equals_zero_for_copay_but_not_for_caps():
    name = "05_orchid_super_topup"
    reply = oracle_reply(EXPECTED[name])
    reply["co_pay_pct"] = c(0)
    reply["room_rent_cap"] = c({"kind": "flat", "amount": 0})
    cov, pages = run_one(name, reply)
    f = score_policy(cov, EXPECTED[name], pages)["fields"]
    assert f["co_pay_pct"]["score"] == 1 and f["room_rent_cap"]["score"] == 0


def test_citation_validity_is_recomputed_from_the_page_text():
    name = "10_aspen_compact"
    reply = oracle_reply(EXPECTED[name])
    reply["sum_insured"] = {
        "value": 200000,
        "source_page": 1,
        "source_quote": "Cover (sum insured): Rs. 2,00,000",
        "confidence": 0.9,
    }
    cov, pages = run_one(name, reply)
    res = score_policy(cov, EXPECTED[name], pages)
    assert res["citations_valid"] == 1  # only the real quote counts; the "zzqq" quotes do not
    assert res["citations_total"] > 1


def test_summary_counts_flagged_and_wrong_fields():
    name = "10_aspen_compact"
    reply = oracle_reply(EXPECTED[name])
    reply["deductible"] = c(9999, conf=0.2)  # wrong and the model knew
    cov, pages = run_one(name, reply)
    s = summarise({name: score_policy(cov, EXPECTED[name], pages)})
    assert s["wrong_fields"] == 1 and s["wrong_fields_flagged"] == 1
    assert s["low_confidence_share"] > 0


def test_cli_refuses_to_run_without_an_llm_key(monkeypatch, capsys):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert evals_run.main([]) == 2
    assert "LLM_API_KEY" in capsys.readouterr().err
