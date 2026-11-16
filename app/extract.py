"""LLM extraction: pages in, validated PolicyCoverage out. No money is computed here."""

import json
import re
from typing import Protocol, get_args, get_origin

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.schema import Cited, PolicyCoverage, iter_cited

CAPPED_CONFIDENCE = 0.3  # confidence ceiling when the quote is not on the cited page

SYSTEM_PROMPT = """You extract structured coverage from a health insurance policy document.
You only EXTRACT. You never calculate claim amounts. Reply with ONE JSON object, no prose.

Pages are marked "=== PAGE n ===". Every field is an object:
  {"value": ..., "source_page": n, "source_quote": "...", "confidence": 0.0-1.0}
- source_quote: copied VERBATIM from that page, at most 25 words. Never paraphrase.
- value null (with source_page and source_quote null) means "not stated in the document".
- confidence: 1.0 explicit and unambiguous; 0.5 or less when inferred, ambiguous or conflicting.
- Money is a plain number in rupees (5 lakh = 500000, 1 crore = 10000000). No currency symbols.

Every list item is a full cited object with the item under "value", e.g.
  "sub_limits": [{"value": {"procedure": "cataract", "limit": 40000},
                  "source_page": 2, "source_quote": "...", "confidence": 1.0}]
Never put the item's keys beside source_page; they go inside "value".

Fields:
{
 "sum_insured": cited number,
 "room_rent_cap": cited {"kind":"flat","amount":N} (rupees PER DAY) or
                  {"kind":"pct_si","amount":N} (N percent of sum insured per day).
                  null value if there is no cap, or if it is only a room category with no number,
 "icu_cap": same shape as room_rent_cap, per day,
 "co_pay_pct": cited number 0-100 (the general co-payment; null if none),
 "deductible": cited number in rupees per claim (null if none),
 "sub_limits": [cited {"procedure": lower-case name, "limit": rupees}],
 "waiting_periods": {
   "initial_days": cited integer days,
   "pre_existing_months": cited integer MONTHS (4 years = 48),
   "specific_illness": [cited {"illness": lower-case name, "months": integer}]},
 "exclusions": [cited string: a short lower-case label, max 6 words, one per exclusion],
 "network_only": cited boolean (true only if cashless/cover is restricted to network hospitals)
}
Return every key. Use [] for empty lists."""


class ChatClient(Protocol):
    def chat_json(self, messages: list[dict]) -> str: ...


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", s.lower()).strip()


def quote_on_page(quote: str | None, page: int | None, pages: list[str]) -> bool:
    if not quote or not page or page > len(pages):
        return False
    # pad with spaces so "10" cannot match inside "100"
    return f" {_norm(quote)} " in f" {_norm(pages[page - 1])} "


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    return data


def _salvage(model: type[BaseModel], data: dict, warnings: list[str], path: str = "") -> dict:
    """Keep every field that validates on its own; reset the rest to 'unknown, confidence 0'."""
    out = {}
    for name, info in model.model_fields.items():
        where = f"{path}{name}"
        raw = data.get(name) if isinstance(data, dict) else None
        ann = info.annotation
        if raw is None:
            continue
        try:
            TypeAdapter(ann).validate_python(raw)
            out[name] = raw
            continue
        except ValidationError:
            pass
        if get_origin(ann) is list and isinstance(raw, list):
            item_ann = get_args(ann)[0]
            kept = []
            for i, item in enumerate(raw):
                try:
                    TypeAdapter(item_ann).validate_python(item)
                    kept.append(item)
                except ValidationError:
                    warnings.append(f"{where}[{i}] dropped: invalid after retry")
            out[name] = kept
        elif isinstance(ann, type) and issubclass(ann, BaseModel) and not issubclass(ann, Cited):
            out[name] = _salvage(ann, raw, warnings, f"{where}.")
        else:
            warnings.append(f"{where} invalid after retry; left empty")
    return out


def extract_policy(pages: list[str], client: ChatClient) -> PolicyCoverage:
    """Ask for JSON, validate, retry once with the error, then salvage field by field."""
    doc = "\n\n".join(f"=== PAGE {i} ===\n{t}" for i, t in enumerate(pages, 1))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": doc},
    ]
    warnings: list[str] = []
    data: dict = {}
    coverage: PolicyCoverage | None = None
    for attempt in (1, 2):
        raw = client.chat_json(messages)
        try:
            data = _parse_json(raw)
            coverage = PolicyCoverage.model_validate(data)
            break
        except (
            ValueError,
            ValidationError,
        ) as e:  # json errors and pydantic errors are ValueErrors
            if attempt == 1:
                warnings.append("first answer failed validation; retried once")
                messages += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"That JSON failed validation:\n{str(e)[:1500]}\n"
                        "Return the corrected JSON object only.",
                    },
                ]
    if coverage is None:
        coverage = PolicyCoverage.model_validate(_salvage(PolicyCoverage, data, warnings))
    coverage.warnings = warnings
    verify_citations(coverage, pages)
    return coverage


def verify_citations(coverage: PolicyCoverage, pages: list[str]) -> None:
    """A value whose quote is not on its cited page cannot be trusted, whatever the model says."""
    for _, c in iter_cited(coverage):
        if c.value is None:
            c.quote_verified = None
            continue
        c.quote_verified = quote_on_page(c.source_quote, c.source_page, pages)
        if not c.quote_verified:
            c.confidence = min(c.confidence, CAPPED_CONFIDENCE)


def annotate_review(coverage: PolicyCoverage, threshold: float) -> PolicyCoverage:
    """Flag fields a human should check: low confidence, or a value whose quote did not verify."""
    for _, c in iter_cited(coverage):
        c.needs_review = c.confidence < threshold or (
            c.value is not None and c.quote_verified is False
        )
    return coverage
