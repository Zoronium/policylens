"""The shape of what the LLM extracts. Every field is cited: value + page + verbatim quote."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

MAX_QUOTE_WORDS = 25


def _clip_words(v):
    # Models overshoot the word limit. Keeping a prefix keeps the quote verbatim.
    if isinstance(v, str):
        return " ".join(v.split()[:MAX_QUOTE_WORDS]) or None
    return v


Quote = Annotated[str | None, BeforeValidator(_clip_words)]
Money = Annotated[Decimal, Field(ge=0)]  # INR
Pct = Annotated[Decimal, Field(ge=0, le=100)]


class Cited[T](BaseModel):
    value: T | None = None  # None = "not stated in the document"
    source_page: int | None = Field(default=None, ge=1)
    source_quote: Quote = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    # Set by the server, never by the LLM:
    quote_verified: bool | None = None  # quote found on the cited page?
    needs_review: bool = False


class DailyCap(BaseModel):
    """A per-day cap: a flat rupee amount, or a percentage of the sum insured."""

    kind: Literal["flat", "pct_si"]
    amount: Money

    @model_validator(mode="after")
    def _pct_range(self):
        if self.kind == "pct_si" and self.amount > 100:
            raise ValueError("pct_si amount must be <= 100")
        return self


class SubLimit(BaseModel):
    procedure: str
    limit: Money


class SpecificWait(BaseModel):
    illness: str
    months: int = Field(ge=0)


class WaitingPeriods(BaseModel):
    initial_days: Cited[int] = Cited[int]()
    pre_existing_months: Cited[int] = Cited[int]()
    specific_illness: list[Cited[SpecificWait]] = []


class PolicyCoverage(BaseModel):
    sum_insured: Cited[Money] = Cited[Money]()
    room_rent_cap: Cited[DailyCap] = Cited[DailyCap]()  # per day; None = no cap stated
    icu_cap: Cited[DailyCap] = Cited[DailyCap]()  # per day
    co_pay_pct: Cited[Pct] = Cited[Pct]()
    deductible: Cited[Money] = Cited[Money]()
    sub_limits: list[Cited[SubLimit]] = []
    waiting_periods: WaitingPeriods = WaitingPeriods()
    exclusions: list[Cited[str]] = []
    network_only: Cited[bool] = Cited[bool]()
    warnings: list[str] = []  # set by the server: retries, dropped items


def iter_cited(node, path: str = "") -> Iterator[tuple[str, Cited]]:
    """Yield (path, Cited) for every cited field in a coverage object."""
    if isinstance(node, Cited):
        yield path, node
    elif isinstance(node, BaseModel):
        for name in type(node).model_fields:
            yield from iter_cited(getattr(node, name), f"{path}.{name}" if path else name)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from iter_cited(item, f"{path}[{i}]")
