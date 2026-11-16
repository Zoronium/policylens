# engine/

Pure Python. No LLM, no network, no floats. `tests/test_engine_purity.py` imports the package in a
fresh interpreter and fails if `httpx`, `app.llm`, `app.extract` or `openai` get loaded.

`estimate(coverage, scenario)` returns the payable amount, what the patient pays, and an audit
trail with one entry per step (rule applied, amount before, amount after).

## Order of rules

1. Waiting periods (initial, pre-existing if flagged, specific illness if the procedure matches)
2. Exclusions
3. Room rent cap with proportionate deduction, then ICU cap
4. Procedure sub-limit
5. Deductible
6. Co-payment
7. Sum insured ceiling

A rejection at step 1 or 2 stops the calculation: payable is 0, the patient pays the whole bill.

## Assumptions (simplifications, stated on purpose)

- **Money.** `Decimal` throughout. Every step is rounded to paise with `ROUND_HALF_UP`, so the
  trail adds up on paper. Rounding at each step can differ by a paisa from rounding once at the end.
- **Waiting boundary is inclusive.** A claim is payable when `policy_age_days >= waiting days`.
  Months become days as `months * 365 / 12` (24 months = 730, 36 months = 1095). Real policies
  count calendar months from the start date; this engine only receives an age in days.
- **Pre-existing** applies only when the scenario sets `is_pre_existing`. The engine does not decide
  medically whether something is pre-existing.
- **Accident exception** to the initial waiting period is not modelled.
- **Room rent cap.** `null` means no cap. `0` means no room cover, so the ratio is 0. A percent cap
  is a percentage of the sum insured, per day. Ratio = cap / actual room rent per day, applied only
  when actual exceeds cap.
- **Which charges are scaled by the ratio:** room, doctor and OT. Pharmacy, consumables and
  diagnostics are not (IRDAI barred insurers from treating pharmacy, consumables, implants, devices
  and diagnostics as "associated medical expenses"). "Other" is not scaled either: it is a catch-all
  we cannot attribute to the room. ICU is not scaled; it has its own cap. Sources are secondary
  articles, not the circular itself, and they disagree about ICU, so treat this list as an
  assumption to check against the policy wording:
  [Business Standard](https://www.business-standard.com/amp/article/companies/out-of-pocket-expenses-of-policyholders-to-fall-after-new-irdai-guidelines-120061200007_1.html),
  [Reliance General](https://www.reliancegeneral.co.in/Insurance/Knowledge-Center/Insurance-Reads/IRDAI-Redefining-Sub-Limit-Rules-for-Health-Insurance.aspx).
- **ICU cap** is a per-day cap times `icu_days`, applied to the ICU line only.
- **Sub-limit** caps the whole eligible amount for that procedure after the room step, not each
  line. It is per claim; no per-year accumulation.
- **Deductible** is per claim, taken before the co-pay. No annual accumulation.
- **Co-pay** is one flat percentage. Conditional co-pays (by age, by hospital type) are not modelled.
- **Sum insured ceiling** is `sum_insured - sum_insured_used` (what the caller says was already
  paid this policy year). Floater logic, restoration and no-claim bonus are not modelled.
- **Procedure matching** for exclusions, sub-limits and specific illnesses is normalised exact
  match (lower case, punctuation and spacing ignored). "Cataract surgery" does not match
  "cataract". The UI offers the policy's own procedure names to pick from.
- **Missing values.** No sum insured raises `EngineError` (HTTP 422) rather than guessing. A missing
  deductible or co-pay is treated as 0, and a missing waiting period as none.
- **Network-only** is extracted but not used: the scenario has no hospital field.
