from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class Charges(BaseModel):
    room: Money = Decimal(0)
    icu: Money = Decimal(0)
    doctor: Money = Decimal(0)
    ot: Money = Decimal(0)
    pharmacy: Money = Decimal(0)
    diagnostics: Money = Decimal(0)
    consumables: Money = Decimal(0)
    other: Money = Decimal(0)


class Scenario(BaseModel):
    procedure: str = Field(min_length=1)
    days_admitted: int = Field(ge=0)
    room_rent_per_day: Money
    icu_days: int = Field(default=0, ge=0)
    charges: Charges
    policy_age_days: int = Field(ge=0)
    is_pre_existing: bool = False
    sum_insured_used: Money = Decimal(0)  # already paid out this policy year


class EstimateRequest(BaseModel):
    policy_id: str
    scenario: Scenario


class AuditStep(BaseModel):
    step: int
    name: str
    rule: str  # the policy rule applied, with the numbers used
    outcome: Literal["applied", "skipped", "rejected"]
    before: Money
    after: Money
    note: str = ""


class EstimateResult(BaseModel):
    status: Literal["payable", "rejected"]
    total_billed: Money
    payable: Money
    patient_pays: Money
    rejection_reason: str | None = None
    trail: list[AuditStep]
