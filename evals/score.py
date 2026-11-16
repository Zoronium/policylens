"""Scoring. Pure functions, no LLM. Compares an extracted PolicyCoverage to hand labels.

Field score: scalars are 1 or 0 (numbers compared as Decimals). List fields get F1, where two
items match when their normalised text is equal or one's word set contains the other's.
co_pay_pct and deductible treat null and 0 as the same; so does network_only (null == false).
"""

import re
from decimal import Decimal

from app.extract import quote_on_page
from app.schema import PolicyCoverage, iter_cited

SCALARS = (
    "sum_insured",
    "room_rent_cap",
    "icu_cap",
    "co_pay_pct",
    "deductible",
    "initial_days",
    "pre_existing_months",
    "network_only",
)
LISTS = ("sub_limits", "specific_illness", "exclusions")
FIELDS = SCALARS + LISTS


def _words(s: str) -> frozenset[str]:
    return frozenset(re.sub(r"[^0-9a-z]+", " ", s.lower()).split())


def _text_match(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def _num(x):
    return None if x is None else Decimal(str(x))


def _cap(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return (x["kind"], _num(x["amount"]))
    return (x.kind, _num(x.amount))


def actual_fields(cov: PolicyCoverage) -> dict:
    wp = cov.waiting_periods
    return {
        "sum_insured": _num(cov.sum_insured.value),
        "room_rent_cap": _cap(cov.room_rent_cap.value),
        "icu_cap": _cap(cov.icu_cap.value),
        "co_pay_pct": _num(cov.co_pay_pct.value),
        "deductible": _num(cov.deductible.value),
        "initial_days": _num(wp.initial_days.value),
        "pre_existing_months": _num(wp.pre_existing_months.value),
        "network_only": cov.network_only.value,
        "sub_limits": [(s.value.procedure, _num(s.value.limit)) for s in cov.sub_limits if s.value],
        "specific_illness": [
            (s.value.illness, _num(s.value.months)) for s in wp.specific_illness if s.value
        ],
        "exclusions": [s.value for s in cov.exclusions if s.value],
    }


def expected_fields(e: dict) -> dict:
    return {
        **{k: _num(e[k]) for k in SCALARS if k not in ("room_rent_cap", "icu_cap", "network_only")},
        "room_rent_cap": _cap(e["room_rent_cap"]),
        "icu_cap": _cap(e["icu_cap"]),
        "network_only": e["network_only"],
        "sub_limits": [(s["procedure"], _num(s["limit"])) for s in e["sub_limits"]],
        "specific_illness": [(s["illness"], _num(s["months"])) for s in e["specific_illness"]],
        "exclusions": list(e["exclusions"]),
    }


def _item_match(a, b) -> bool:
    if isinstance(a, tuple):  # (name, number)
        return a[1] == b[1] and _text_match(a[0], b[0])
    return _text_match(a, b)


def _f1(exp: list, act: list) -> float:
    if not exp and not act:
        return 1.0
    recall_hits = sum(any(_item_match(x, y) for y in act) for x in exp)
    precision_hits = sum(any(_item_match(x, y) for x in exp) for y in act)
    if not recall_hits or not precision_hits:
        return 0.0
    r, p = recall_hits / len(exp), precision_hits / len(act)
    return 2 * p * r / (p + r)


def field_score(name: str, exp, act) -> float:
    if name in LISTS:
        return _f1(exp, act)
    if name in ("co_pay_pct", "deductible"):
        exp, act = exp or Decimal(0), act or Decimal(0)
    if name == "network_only":
        exp, act = bool(exp), bool(act)
    return 1.0 if exp == act else 0.0


def field_flagged(name: str, cov: PolicyCoverage) -> bool:
    wp = cov.waiting_periods
    nodes = {
        "sum_insured": [cov.sum_insured],
        "room_rent_cap": [cov.room_rent_cap],
        "icu_cap": [cov.icu_cap],
        "co_pay_pct": [cov.co_pay_pct],
        "deductible": [cov.deductible],
        "initial_days": [wp.initial_days],
        "pre_existing_months": [wp.pre_existing_months],
        "network_only": [cov.network_only],
        "sub_limits": cov.sub_limits,
        "specific_illness": wp.specific_illness,
        "exclusions": cov.exclusions,
    }[name]
    return any(c.needs_review for c in nodes)


def citation_stats(cov: PolicyCoverage, pages: list[str]) -> tuple[int, int]:
    """(cited values whose quote is on the cited page, cited values). Recomputed, not trusted."""
    rows = [c for _, c in iter_cited(cov) if c.value is not None]
    ok = sum(quote_on_page(c.source_quote, c.source_page, pages) for c in rows)
    return ok, len(rows)


def score_policy(cov: PolicyCoverage, expected: dict, pages: list[str]) -> dict:
    exp, act = expected_fields(expected), actual_fields(cov)
    fields = {}
    for name in FIELDS:
        fields[name] = {
            "score": round(field_score(name, exp[name], act[name]), 4),
            "flagged": field_flagged(name, cov),
        }
    ok, n = citation_stats(cov, pages)
    return {"fields": fields, "citations_valid": ok, "citations_total": n}


def summarise(per_policy: dict[str, dict]) -> dict:
    """Headline numbers over all policies."""
    rows = [f for p in per_policy.values() for f in p["fields"].values()]
    n = len(rows)
    flagged = [r for r in rows if r["flagged"]]
    unflagged = [r for r in rows if not r["flagged"]]
    wrong = [r for r in rows if r["score"] < 1]
    cites_ok = sum(p["citations_valid"] for p in per_policy.values())
    cites_n = sum(p["citations_total"] for p in per_policy.values())
    by_field = {
        f: round(sum(p["fields"][f]["score"] for p in per_policy.values()) / len(per_policy), 4)
        for f in FIELDS
    }
    return {
        "policies": len(per_policy),
        "field_accuracy": round(sum(r["score"] for r in rows) / n, 4),
        "field_accuracy_by_field": by_field,
        "accuracy_on_unflagged_fields": (
            round(sum(r["score"] for r in unflagged) / len(unflagged), 4) if unflagged else None
        ),
        "citation_validity": round(cites_ok / cites_n, 4) if cites_n else None,
        "citations_checked": cites_n,
        "low_confidence_share": round(len(flagged) / n, 4),
        "wrong_fields": len(wrong),
        "wrong_fields_flagged": sum(r["flagged"] for r in wrong),
    }
