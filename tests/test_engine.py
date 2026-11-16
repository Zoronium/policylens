from decimal import Decimal as D

import pytest

from app.schema import PolicyCoverage
from engine import EngineError, Scenario, estimate


def c(value):
    return {"value": value, "source_page": 1, "source_quote": "q", "confidence": 1}


def policy(**over):
    base = {
        "sum_insured": c(500000),
        "room_rent_cap": c({"kind": "flat", "amount": 5000}),
        "icu_cap": c({"kind": "flat", "amount": 10000}),
        "co_pay_pct": c(10),
        "deductible": c(0),
        "sub_limits": [c({"procedure": "cataract", "limit": 40000})],
        "waiting_periods": {
            "initial_days": c(30),
            "pre_existing_months": c(36),
            "specific_illness": [c({"illness": "hernia", "months": 24})],
        },
        "exclusions": [c("cosmetic surgery")],
        "network_only": c(False),
    }
    base.update(over)
    return PolicyCoverage.model_validate(base)


def scen(procedure="appendectomy", rent=4000, age=1000, **kw):
    charges = {
        k: kw.pop(k)
        for k in list(kw)
        if k in ("room", "icu", "doctor", "ot", "pharmacy", "diagnostics", "consumables", "other")
    }
    return Scenario(
        procedure=procedure,
        days_admitted=3,
        room_rent_per_day=rent,
        charges=charges,
        policy_age_days=age,
        **kw,
    )


def step(res, name):
    return next(s for s in res.trail if s.name == name)


def test_simple_claim_within_cap_only_copay_applies():
    r = estimate(policy(), scen(room=12000, doctor=20000, pharmacy=8000))
    assert (r.total_billed, r.payable, r.patient_pays) == (D("40000"), D("36000"), D("4000"))
    assert step(r, "Room rent cap").outcome == "skipped"


def test_room_rent_exactly_at_cap_is_not_reduced():
    r = estimate(policy(), scen(rent=5000, room=15000, doctor=10000))
    assert step(r, "Room rent cap").outcome == "skipped"
    assert r.payable == D("22500")  # 25000 less 10% co-pay


def test_proportionate_deduction_scales_only_room_linked_charges():
    # cap 5000 / rent 8000 = 0.625 on room, doctor, ot
    r = estimate(
        policy(),
        scen(
            rent=8000,
            room=24000,
            doctor=20000,
            ot=16000,
            pharmacy=10000,
            diagnostics=5000,
            consumables=3000,
        ),
    )
    assert r.total_billed == D("78000")
    assert step(r, "Room rent cap").after == D("55500")  # 15000+12500+10000+10000+5000+3000
    assert (r.payable, r.patient_pays) == (D("49950.00"), D("28050.00"))


def test_zero_cap_means_no_room_linked_charge_is_payable():
    p = policy(room_rent_cap=c({"kind": "flat", "amount": 0}), co_pay_pct=c(0))
    r = estimate(p, scen(rent=1000, room=3000, doctor=2000, ot=1000, pharmacy=500))
    assert r.payable == D("500")


def test_no_cap_stated_means_no_cap():
    r = estimate(policy(room_rent_cap=c(None), co_pay_pct=c(0)), scen(rent=99999, room=100000))
    assert r.payable == D("100000")


def test_percent_of_sum_insured_cap():
    p = policy(room_rent_cap=c({"kind": "pct_si", "amount": 1}), co_pay_pct=c(0))  # 1% = 5000
    r = estimate(p, scen(rent=10000, room=20000, pharmacy=1000))
    assert step(r, "Room rent cap").after == D("11000")  # ratio 0.5 on room only


def test_initial_waiting_boundary():
    assert estimate(policy(), scen(age=29)).status == "rejected"
    assert estimate(policy(), scen(age=30, room=1000)).status == "payable"


def test_pre_existing_waiting_boundary_36_months_is_1095_days():
    kw = {"is_pre_existing": True, "room": 1000}
    assert estimate(policy(), scen(age=1094, **kw)).status == "rejected"
    assert estimate(policy(), scen(age=1095, **kw)).status == "payable"
    assert (
        estimate(policy(), scen(age=100, room=1000)).status == "payable"
    )  # not flagged pre-existing


def test_specific_illness_waiting_applies_only_to_that_procedure():
    assert estimate(policy(), scen("Hernia", age=729, room=1000)).status == "rejected"
    assert estimate(policy(), scen("Hernia", age=730, room=1000)).status == "payable"
    assert estimate(policy(), scen("appendectomy", age=100, room=1000)).status == "payable"


def test_exclusion_rejects_and_matches_case_insensitively():
    r = estimate(policy(), scen("Cosmetic  Surgery", room=5000))
    assert r.status == "rejected" and r.payable == 0 and r.patient_pays == D("5000")


def test_sub_limit_caps_the_procedure_then_copay():
    r = estimate(policy(), scen("cataract", doctor=60000))
    assert step(r, "Sub-limit").after == D("40000")
    assert r.payable == D("36000")


def test_deductible_then_copay_then_sub_limit_order():
    p = policy(deductible=c(5000), co_pay_pct=c(20))
    r = estimate(p, scen("cataract", doctor=60000))
    # sub-limit 40000 -> less deductible 35000 -> 80% = 28000
    assert [s.after for s in r.trail[-4:-1]] == [D("40000"), D("35000"), D("28000")]
    assert r.payable == D("28000.00")


def test_deductible_larger_than_claim_gives_zero():
    r = estimate(policy(deductible=c(50000)), scen(room=3000))
    assert r.payable == 0 and r.patient_pays == D("3000")


def test_sum_insured_exhausted_pays_nothing():
    r = estimate(policy(), scen(room=3000, sum_insured_used=500000))
    assert r.payable == 0 and r.patient_pays == D("3000")


def test_sum_insured_partially_remaining_caps_payout():
    p = policy(sum_insured=c(100000), co_pay_pct=c(0), room_rent_cap=c(None))
    r = estimate(p, scen(doctor=90000, sum_insured_used=50000))
    assert r.payable == D("50000") and r.patient_pays == D("40000")


def test_icu_cap_is_per_day_times_icu_days():
    r = estimate(policy(co_pay_pct=c(0)), scen(icu=60000, icu_days=3))
    assert step(r, "ICU cap").after == D("30000")


def test_rounding_is_half_up_to_paise_not_bankers():
    p = policy(room_rent_cap=c({"kind": "flat", "amount": 1}), co_pay_pct=c(0))
    r = estimate(p, scen(rent=2, room="100.05"))  # 100.05 * 0.5 = 50.025
    assert r.payable == D("50.03")


def test_missing_sum_insured_is_an_error_not_a_guess():
    with pytest.raises(EngineError):
        estimate(policy(sum_insured=c(None)), scen(room=1000))


@pytest.mark.parametrize(
    "s",
    [
        scen(rent=8000, room=24000, doctor=20000, pharmacy=10000),
        scen("cataract", doctor=60000, icu=20000, icu_days=1),
        scen("cosmetic surgery", room=1000),
        scen(room=3000, sum_insured_used=499999),
    ],
)
def test_audit_trail_is_continuous_and_ends_at_the_payout(s):
    r = estimate(policy(deductible=c(1000)), s)
    assert (
        r.trail[0].before == r.trail[0].after == r.total_billed
        or r.trail[0].after == r.total_billed
    )
    for a, b in zip(r.trail, r.trail[1:], strict=False):
        assert b.before == a.after
    assert r.trail[-1].after == r.payable
    assert r.payable + r.patient_pays == r.total_billed
    assert all(isinstance(x, D) for x in (r.payable, r.patient_pays, r.total_billed))
