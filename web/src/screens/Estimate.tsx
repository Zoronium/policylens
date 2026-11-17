import { useId, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, type AuditStep, type Charges, type Estimate as Result, type Policy, type Scenario } from "../api";
import { drop, inr, rupee } from "../format";
import posthog, { posthogEnabled } from "../posthog";
import { Alert, Icon, Skeleton } from "../ui";

const CHARGE_LABELS: [keyof Charges, string][] = [
  ["room", "Room"],
  ["icu", "ICU"],
  ["doctor", "Doctor fees"],
  ["ot", "Operation theatre"],
  ["pharmacy", "Pharmacy"],
  ["diagnostics", "Diagnostics"],
  ["consumables", "Consumables"],
  ["other", "Other"],
];

interface Form {
  procedure: string;
  days: string;
  rent: string;
  icuDays: string;
  age: string;
  preExisting: boolean;
  used: string;
  charges: Record<keyof Charges, string>;
}

function exampleFor(p: Policy): Form {
  const c = p.coverage;
  const si = Number(c.sum_insured.value ?? 0);
  const cap = c.room_rent_cap.value;
  const capDay = cap ? (cap.kind === "flat" ? Number(cap.amount) : (si * Number(cap.amount)) / 100) : 4000;
  const rent = Math.round(capDay * 1.6) || 6000;
  const procedure = c.sub_limits.find((s) => s.value)?.value?.procedure ?? "appendectomy";
  return {
    procedure,
    days: "3",
    rent: String(rent),
    icuDays: "0",
    age: "800",
    preExisting: false,
    used: "0",
    charges: {
      room: String(rent * 3),
      icu: "0",
      doctor: "25000",
      ot: "18000",
      pharmacy: "12000",
      diagnostics: "6000",
      consumables: "4000",
      other: "2000",
    },
  };
}

const AMOUNT = /^\d{1,12}(\.\d{1,2})?$/;
const COUNT = /^\d{1,6}$/;

function MoneyField({
  label,
  value,
  onChange,
  error,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
}) {
  const id = useId();
  const ok = AMOUNT.test(value);
  return (
    <div className="field money">
      <label htmlFor={id}>{label}</label>
      <div className="input-affix">
        <span aria-hidden="true">{rupee}</span>
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          value={value}
          aria-invalid={error ? true : undefined}
          aria-describedby={`${id}-p`}
          onChange={(e) => onChange(e.target.value.replace(/[,\s]/g, ""))}
        />
      </div>
      <p id={`${id}-p`} className={error ? "hint err" : "hint num"}>
        {error ?? (ok ? `${rupee}${inr(value)}` : " ")}
      </p>
    </div>
  );
}

function CountField({
  label,
  value,
  onChange,
  error,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        inputMode="numeric"
        autoComplete="off"
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={`${id}-p`}
        onChange={(e) => onChange(e.target.value)}
      />
      <p id={`${id}-p`} className={error ? "hint err" : "hint"}>
        {error ?? hint ?? " "}
      </p>
    </div>
  );
}

function validate(f: Form) {
  const e: Record<string, string> = {};
  if (!f.procedure.trim()) e.procedure = "Enter the procedure.";
  for (const [k, v] of [["days", f.days], ["icuDays", f.icuDays], ["age", f.age]] as const)
    if (!COUNT.test(v)) e[k] = "Whole number, 0 or more.";
  for (const [k, v] of [["rent", f.rent], ["used", f.used]] as const)
    if (!AMOUNT.test(v)) e[k] = "Amount in rupees, up to 2 decimals.";
  for (const [k] of CHARGE_LABELS) if (!AMOUNT.test(f.charges[k])) e[`c_${k}`] = "Amount in rupees.";
  return e;
}

function toScenario(f: Form): Scenario {
  return {
    procedure: f.procedure.trim(),
    days_admitted: Number(f.days),
    room_rent_per_day: f.rent,
    icu_days: Number(f.icuDays),
    charges: f.charges,
    policy_age_days: Number(f.age),
    is_pre_existing: f.preExisting,
    sum_insured_used: f.used,
  };
}

function PolicyStrip({ p }: { p: Policy }) {
  const c = p.coverage;
  const bits: string[] = [];
  if (c.sum_insured.value) bits.push(`Sum insured ${rupee}${inr(c.sum_insured.value)}`);
  const cap = c.room_rent_cap.value;
  if (cap) bits.push(cap.kind === "flat" ? `Room cap ${rupee}${inr(cap.amount)}/day` : `Room cap ${cap.amount}% of SI/day`);
  if (c.deductible.value) bits.push(`Deductible ${rupee}${inr(c.deductible.value)}`);
  if (c.co_pay_pct.value) bits.push(`Co-pay ${c.co_pay_pct.value}%`);
  return <p className="strip">{bits.join("  ·  ") || "No cost terms extracted."}</p>;
}

export default function Estimate({ policy, onBack }: { policy: Policy; onBack: () => void }) {
  const [form, setForm] = useState<Form>(() => exampleFor(policy));
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const errors = useMemo(() => validate(form), [form]);
  const shown = touched ? errors : {};

  const names = useMemo(() => {
    const c = policy.coverage;
    const all = [
      ...c.sub_limits.map((s) => s.value?.procedure),
      ...c.waiting_periods.specific_illness.map((s) => s.value?.illness),
      ...c.exclusions.map((s) => s.value),
    ].filter((x): x is string => !!x);
    return [...new Set(all)];
  }, [policy]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setCharge = (k: keyof Charges, v: string) => setForm((f) => ({ ...f, charges: { ...f.charges, [k]: v } }));

  async function run(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length) return;
    setBusy(true);
    setError(null);
    try {
      const estimate = await api.estimate(policy.id, toScenario(form));
      if (posthogEnabled) {
        const appliedRuleCount = estimate.trail.filter((step) => step.outcome === "applied").length;
        const rejectedRuleCount = estimate.trail.filter((step) => step.outcome === "rejected").length;
        posthog.capture("claim_estimate_calculated", {
          estimate_status: estimate.status,
          applied_rule_count: appliedRuleCount,
          rejected_rule_count: rejectedRuleCount,
        });
      }
      setResult(estimate);
    } catch (err) {
      if (posthogEnabled) posthog.capture("claim_estimate_failed");
      setResult(null);
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Estimate a claim</h1>
          <PolicyStrip p={policy} />
        </div>
        <button className="btn" onClick={onBack}>
          Review coverage
        </button>
      </div>

      <div className="est-grid">
        <form className="panel scen" onSubmit={run} noValidate>
          <fieldset>
            <legend>Admission</legend>
            <div className="field">
              <label htmlFor="proc">Procedure</label>
              <input
                id="proc"
                list="procs"
                autoComplete="off"
                value={form.procedure}
                aria-invalid={shown.procedure ? true : undefined}
                aria-describedby="proc-h"
                onChange={(e) => set("procedure", e.target.value)}
              />
              <datalist id="procs">
                {names.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
              <p id="proc-h" className={shown.procedure ? "hint err" : "hint"}>
                {shown.procedure ?? "Matched by exact name against sub-limits, exclusions and specific illnesses."}
              </p>
            </div>
            <div className="two">
              <CountField label="Days admitted" value={form.days} onChange={(v) => set("days", v)} error={shown.days} />
              <CountField label="ICU days" value={form.icuDays} onChange={(v) => set("icuDays", v)} error={shown.icuDays} />
            </div>
            <MoneyField label="Room rent per day" value={form.rent} onChange={(v) => set("rent", v)} error={shown.rent} />
            <CountField
              label="Policy age in days"
              value={form.age}
              onChange={(v) => set("age", v)}
              error={shown.age}
              hint={COUNT.test(form.age) ? `About ${(Number(form.age) / 365).toFixed(1)} years` : undefined}
            />
            <label className="check">
              <input type="checkbox" checked={form.preExisting} onChange={(e) => set("preExisting", e.target.checked)} />
              Pre-existing condition
            </label>
            <MoneyField label="Already paid this policy year" value={form.used} onChange={(v) => set("used", v)} error={shown.used} />
          </fieldset>

          <fieldset>
            <legend>Itemised charges</legend>
            <div className="two">
              {CHARGE_LABELS.map(([k, label]) => (
                <MoneyField key={k} label={label} value={form.charges[k]} onChange={(v) => setCharge(k, v)} error={shown[`c_${k}`]} />
              ))}
            </div>
          </fieldset>

          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Calculating" : "Calculate payout"}
              {!busy && <Icon name="arrow" />}
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => { setForm(exampleFor(policy)); setTouched(false); }}>
              Reset example
            </button>
          </div>
        </form>

        <section className="result" aria-live="polite" aria-labelledby="res-h">
          <h2 id="res-h" className="sr-only">
            Result
          </h2>
          {error && <Alert title="Could not calculate">{error}</Alert>}
          {busy && !result && <Skeleton lines={6} />}
          {!result && !busy && !error && (
            <div className="empty-result">
              <h3>No estimate yet</h3>
              <p>
                Enter the admission details and charges, then calculate. You will get the payout, what the patient
                pays, and each rule that moved the number.
              </p>
            </div>
          )}
          {result && <ResultView r={result} procedure={form.procedure} />}
        </section>
      </div>
    </div>
  );
}

function ResultView({ r, procedure }: { r: Result; procedure: string }) {
  const [hideSkipped, setHideSkipped] = useState(false);
  const billed = Number(r.total_billed) || 1;
  const share = Math.max(0, Math.min(100, (Number(r.payable) / billed) * 100));
  const steps = hideSkipped ? r.trail.filter((s) => s.outcome !== "skipped") : r.trail;
  return (
    <>
      <div className={`verdict ${r.status}`}>
        <p className="v-label">{r.status === "payable" ? "Insurer pays" : "Claim rejected"}</p>
        <p className="v-amount num">
          <span>{rupee}</span>
          {inr(r.payable)}
        </p>
        <div className="bar" role="img" aria-label={`Insurer pays ${share.toFixed(0)} percent of the bill`}>
          <span style={{ width: `${share}%` }} />
        </div>
        <dl className="v-split">
          <div>
            <dt>Patient pays</dt>
            <dd className="num">
              {rupee}
              {inr(r.patient_pays)}
            </dd>
          </div>
          <div>
            <dt>Total billed</dt>
            <dd className="num">
              {rupee}
              {inr(r.total_billed)}
            </dd>
          </div>
        </dl>
        {r.rejection_reason && <p className="v-reason">{r.rejection_reason}</p>}
        <p className="v-note">
          Calculated by the rules engine for <em>{procedure}</em>. No model was involved in this number.
        </p>
      </div>

      <div className="trail-head">
        <h2>How we got there</h2>
        <label className="check">
          <input type="checkbox" checked={hideSkipped} onChange={(e) => setHideSkipped(e.target.checked)} />
          Hide steps with no effect
        </label>
      </div>
      <ol className="trail">
        {steps.map((s) => (
          <Step key={s.step} s={s} />
        ))}
      </ol>
    </>
  );
}

function Step({ s }: { s: AuditStep }) {
  const delta = drop(s.before, s.after);
  const dec = (v: string) => inr(v, true);
  return (
    <li className={`step ${s.outcome}`}>
      <span className="node" aria-hidden="true">
        {s.outcome === "rejected" ? <Icon name="x" size={13} /> : s.step}
      </span>
      <div className="s-body">
        <h3>
          {s.name}
          <span className="sr-only">, {s.outcome === "skipped" ? "no effect" : s.outcome}</span>
        </h3>
        <p className="s-rule">{s.rule}</p>
        {s.note && <p className="s-note">{s.note}</p>}
      </div>
      <div className="s-fig">
        {s.step === 1 ? (
          <p className="after num">
            {rupee}
            {dec(s.after)}
          </p>
        ) : s.outcome === "skipped" || (s.outcome === "applied" && delta.abs === "0.00") ? (
          <p className="nochange">
            {s.outcome === "skipped" ? "No change" : "Checked, no change"}{" "}
            <span className="num">
              {rupee}
              {dec(s.after)}
            </span>
          </p>
        ) : (
          <>
            <p className="delta num">
              {delta.down ? "−" : "+"}
              {rupee}
              {inr(delta.abs, true)}
            </p>
            <p className="after num">
              <span className="was">{rupee}{dec(s.before)}</span>
              <Icon name="arrow" size={13} />
              {rupee}
              {dec(s.after)}
            </p>
          </>
        )}
      </div>
    </li>
  );
}
