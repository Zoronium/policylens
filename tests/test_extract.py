from app.extract import annotate_review, extract_policy, quote_on_page
from app.pdf import split_pages
from app.schema import Cited, iter_cited
from tests.conftest import PAGES, StubLLM, cited, good_reply


def test_happy_path_one_call_and_citations_verified():
    llm = StubLLM(good_reply())
    cov = extract_policy(PAGES, llm)
    assert len(llm.calls) == 1
    assert cov.sum_insured.value == 500000
    assert cov.sum_insured.quote_verified is True
    assert cov.sub_limits[0].value.procedure == "cataract"
    assert cov.warnings == []


def test_retry_once_after_invalid_json_includes_error_message():
    llm = StubLLM("not json at all", good_reply())
    cov = extract_policy(PAGES, llm)
    assert len(llm.calls) == 2
    assert "failed validation" in llm.calls[1][-1]["content"]
    assert cov.sum_insured.value == 500000
    assert cov.warnings == ["first answer failed validation; retried once"]


def test_two_failures_salvage_valid_fields_and_zero_confidence_on_bad_ones():
    bad = good_reply()
    bad["co_pay_pct"] = cited(250)  # >100 is invalid
    llm = StubLLM(bad, bad)
    cov = extract_policy(PAGES, llm)
    assert len(llm.calls) == 2  # exactly one retry, never more
    assert cov.sum_insured.value == 500000  # valid fields survive
    assert cov.co_pay_pct.value is None and cov.co_pay_pct.confidence == 0
    assert any("co_pay_pct" in w for w in cov.warnings)
    annotate_review(cov, 0.7)
    assert cov.co_pay_pct.needs_review


def test_quote_not_on_cited_page_caps_confidence_and_flags_review():
    reply = good_reply()
    reply["sum_insured"] = cited(500000, 2, "Sum insured: Rs. 5,00,000 per year")  # wrong page
    cov = extract_policy(PAGES, StubLLM(reply))
    assert cov.sum_insured.quote_verified is False
    assert cov.sum_insured.confidence <= 0.3
    annotate_review(cov, 0.7)
    assert cov.sum_insured.needs_review


def test_null_value_with_high_confidence_is_not_flagged():
    reply = good_reply()
    reply["deductible"] = {"value": None, "confidence": 0.9}
    cov = annotate_review(extract_policy(PAGES, StubLLM(reply)), 0.7)
    assert cov.deductible.needs_review is False


def test_quote_longer_than_25_words_is_clipped_not_rejected():
    c = Cited[int](value=1, source_quote=" ".join(f"w{i}" for i in range(40)))
    assert len(c.source_quote.split()) == 25


def test_quote_matching_ignores_case_and_punctuation():
    assert quote_on_page("co-payment: you pay 10%", 1, PAGES)
    assert not quote_on_page("you pay 20%", 1, PAGES)
    assert not quote_on_page("you pay 10%", 9, PAGES)


def test_split_pages_on_markers_and_form_feed():
    assert split_pages("intro\n--- Page 1 ---\nA\n--- Page 2 ---\nB") == [
        "intro\n\nA",
        "B",
    ]  # title block joins page 1
    assert split_pages("A\fB") == ["A", "B"]
    assert split_pages("just one page") == ["just one page"]


def test_iter_cited_walks_lists_and_nested_models():
    cov = extract_policy(PAGES, StubLLM(good_reply()))
    paths = {p for p, _ in iter_cited(cov)}
    assert "sub_limits[0]" in paths and "waiting_periods.initial_days" in paths


def test_prompt_shape_system_first_then_numbered_pages():
    llm = StubLLM(good_reply())
    extract_policy(PAGES, llm)
    assert llm.calls[0][0]["role"] == "system"
    assert "=== PAGE 1 ===" in llm.calls[0][1]["content"]
