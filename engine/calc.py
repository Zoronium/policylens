"""Deterministic claim estimate. No LLM, no network, no floats: Decimal in, Decimal out.

Every step quantises to paise (ROUND_HALF_UP) so the audit trail adds up on paper.
See engine/README.md for the assumptions.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from app.schema import DailyCap, PolicyCoverage
from engine.models import AuditStep, EstimateResult, Scenario

PAISE = Decimal("0.01")
ROOM_LINKED = ("room", "doctor", "ot")  # scaled by proportionate deduction
CHARGE_NAMES = ("room", "icu", "doctor", "ot", "pharmacy", "diagnostics", "consumables", "other")


class EngineError(ValueError):
    """The policy lacks something the calculation cannot do without."""


def q(x: Decimal) -> Decimal:
    return x.quantize(PAISE, rounding=ROUND_HALF_UP)


def inr(x: Decimal) -> str:
    return f"Rs {x:,.2f}"


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", s.lower()).strip()


def months_to_days(m: int) -> Decimal:
    return Decimal(m) * 365 / 12  # multiply first so 24 months is exactly 730 days


def _days(x: Decimal) -> str:
    return f"{q(x).normalize():f}"


def _cap_per_day(cap: DailyCap, sum_insured: Decimal) -> Decimal:
    return q(cap.amount if cap.kind == "flat" else sum_insured * cap.amount / 100)


def _total(c: dict[str, Decimal]) -> Decimal:
    return q(sum(c.values(), Decimal(0)))


def estimate(cov: PolicyCoverage, sc: Scenario) -> EstimateResult:
    si = cov.sum_insured.value
    if si is None:
        raise EngineError("Sum insured was not extracted for this policy; it needs human review.")
    charges: dict[str, Decimal] = {n: q(getattr(sc.charges, n)) for n in CHARGE_NAMES}
    billed = _total(charges)
    trail: list[AuditStep] = []
    cur = billed

    def add(name, rule, outcome, after, note=""):
        nonlocal cur
        step = AuditStep(
            step=len(trail) + 1,
            name=name,
            rule=rule,
            outcome=outcome,
            before=cur,
            after=after,
            note=note,
        )
        trail.append(step)
        cur = after

    def reject(name, rule, reason):
        add(name, rule, "rejected", Decimal(0), reason)
        return EstimateResult(
            status="rejected",
            total_billed=billed,
            payable=Decimal(0),
            patient_pays=billed,
            rejection_reason=reason,
            trail=trail,
        )

    add("Bill as submitted", "Sum of itemised charges", "applied", billed)

    # 1. Waiting periods. Payable once policy_age_days >= waiting days (boundary is inclusive).
    wp = cov.waiting_periods
    waits: list[tuple[str, Decimal]] = []
    if wp.initial_days.value:
        waits.append(("initial waiting period", Decimal(wp.initial_days.value)))
    if sc.is_pre_existing and wp.pre_existing_months.value:
        waits.append(
            (
                "pre-existing disease waiting period",
                months_to_days(wp.pre_existing_months.value),
            )
        )
    for item in wp.specific_illness:
        if item.value and norm(item.value.illness) == norm(sc.procedure):
            waits.append(
                (
                    f"specific illness waiting period ({item.value.illness})",
                    months_to_days(item.value.months),
                )
            )
    breached = [(n, d) for n, d in waits if sc.policy_age_days < d]
    if breached:
        n, d = max(breached, key=lambda x: x[1])
        return reject(
            "Waiting period",
            f"{n}: {_days(d)} days; policy age is {sc.policy_age_days} days",
            f"Claim is inside the {n}.",
        )
    if waits:
        rule = "; ".join(f"{n}: {_days(d)} days" for n, d in waits)
        add(
            "Waiting period",
            f"{rule} (policy age {sc.policy_age_days} days)",
            "applied",
            cur,
            "All applicable waiting periods are complete.",
        )
    else:
        add("Waiting period", "No waiting period applies", "skipped", cur)

    # 2. Exclusions: normalised exact match on the procedure name.
    for ex in cov.exclusions:
        if ex.value and norm(ex.value) == norm(sc.procedure):
            return reject(
                "Exclusion",
                f"Excluded: {ex.value}",
                f"'{sc.procedure}' is an excluded treatment.",
            )
    add("Exclusions", f"'{sc.procedure}' is not on the exclusion list", "skipped", cur)

    # 3a. Room rent cap with proportionate deduction.
    rc = cov.room_rent_cap.value
    if rc is None:
        add("Room rent cap", "No room rent cap stated", "skipped", cur)
    else:
        cap = _cap_per_day(rc, si)
        rent = q(sc.room_rent_per_day)
        if rent <= cap:
            add(
                "Room rent cap",
                f"Cap {inr(cap)} per day; room rent {inr(rent)} is within it",
                "skipped",
                cur,
            )
        else:
            ratio = cap / rent  # cap 0 -> ratio 0: no room-linked charge is payable
            for n in ROOM_LINKED:
                charges[n] = q(charges[n] * ratio)
            add(
                "Room rent cap",
                f"Cap {inr(cap)} per day; room rent {inr(rent)}. "
                f"Ratio = {inr(cap)} / {inr(rent)} = {ratio:.4f}",
                "applied",
                _total(charges),
                "Ratio applied to room, doctor and OT charges. Pharmacy, diagnostics, "
                "consumables, ICU and other are not scaled.",
            )

    # 3b. ICU cap: a plain cap on the ICU line (ICU is not scaled by the room ratio).
    ic = cov.icu_cap.value
    if ic is None or sc.icu_days == 0 or charges["icu"] == 0:
        add("ICU cap", "No ICU cap stated, or no ICU stay billed", "skipped", cur)
    else:
        per_day = _cap_per_day(ic, si)
        allowed = q(per_day * sc.icu_days)
        if charges["icu"] > allowed:
            charges["icu"] = allowed
            add(
                "ICU cap",
                f"Cap {inr(per_day)} per day x {sc.icu_days} days = {inr(allowed)}",
                "applied",
                _total(charges),
            )
        else:
            add("ICU cap", f"ICU charges are within {inr(allowed)}", "skipped", cur)

    # 4. Sub-limit on the whole eligible procedure amount.
    sub = next(
        (
            s.value.limit
            for s in cov.sub_limits
            if s.value and norm(s.value.procedure) == norm(sc.procedure)
        ),
        None,
    )
    if sub is None:
        add("Sub-limit", f"No sub-limit for '{sc.procedure}'", "skipped", cur)
    elif cur > q(sub):
        add(
            "Sub-limit",
            f"Limit for {sc.procedure}: {inr(q(sub))}",
            "applied",
            q(sub),
            "Eligible amount is capped at the procedure limit.",
        )
    else:
        add(
            "Sub-limit",
            f"Limit for {sc.procedure}: {inr(q(sub))}; amount is within it",
            "skipped",
            cur,
        )

    # 5. Deductible, per claim.
    ded = q(cov.deductible.value or Decimal(0))
    if ded == 0:
        add("Deductible", "No deductible", "skipped", cur)
    else:
        add(
            "Deductible",
            f"Deductible {inr(ded)} per claim",
            "applied",
            max(cur - ded, Decimal(0)),
            "The patient bears the deductible first.",
        )

    # 6. Co-pay on what remains.
    pct = cov.co_pay_pct.value or Decimal(0)
    if pct == 0:
        add("Co-payment", "No co-payment", "skipped", cur)
    else:
        add(
            "Co-payment",
            f"Co-payment {pct.normalize():f}%: insurer pays {(100 - pct).normalize():f}%",
            "applied",
            q(cur * (100 - pct) / 100),
        )

    # 7. Sum insured ceiling, net of what was already paid this year.
    available = max(q(si) - q(sc.sum_insured_used), Decimal(0))
    if cur > available:
        add(
            "Sum insured ceiling",
            f"Sum insured {inr(q(si))} less already paid {inr(q(sc.sum_insured_used))} "
            f"leaves {inr(available)}",
            "applied",
            available,
            "Payout cannot exceed the remaining sum insured.",
        )
    else:
        add(
            "Sum insured ceiling",
            f"Remaining sum insured {inr(available)} covers the payout",
            "skipped",
            cur,
        )

    return EstimateResult(
        status="payable",
        total_billed=billed,
        payable=cur,
        patient_pays=q(billed - cur),
        trail=trail,
    )
