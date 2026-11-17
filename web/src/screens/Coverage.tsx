import { useMemo, useState, type ReactNode } from "react";
import type { Cited, DailyCap, Policy } from "../api";
import { days, inr, months, pct, rupee } from "../format";
import posthog, { posthogEnabled } from "../posthog";
import { Alert, Icon, ReviewChip } from "../ui";

interface Row {
  key: string;
  label: string;
  value: ReactNode;
  stated: boolean;
  cited: Cited<unknown>;
}
interface Group {
  title: string;
  note?: string;
  rows: Row[];
  empty: string;
}

function capText(c: DailyCap | null, si: string | null): ReactNode {
  if (!c) return null;
  if (c.kind === "flat")
    return (
      <>
        {rupee}
        {inr(c.amount)} per day
      </>
    );
  const abs = si ? (Number(si) * Number(c.amount)) / 100 : null;
  return (
    <>
      {c.amount}% of sum insured per day
      {abs !== null && (
        <span className="muted">
          {" "}
          ({rupee}
          {inr(abs)})
        </span>
      )}
    </>
  );
}

function buildGroups(p: Policy): Group[] {
  const c = p.coverage;
  const si = c.sum_insured.value;
  const scalar = <T,>(key: string, label: string, cited: Cited<T>, fmt: (v: T) => ReactNode, none = "Not stated"): Row => ({
    key,
    label,
    cited: cited as Cited<unknown>,
    stated: cited.value !== null,
    value: cited.value !== null ? fmt(cited.value) : none,
  });
  const money = (v: string) => (
    <>
      {rupee}
      {inr(v)}
    </>
  );
  return [
    {
      title: "Cover and cost sharing",
      empty: "",
      rows: [
        scalar("sum_insured", "Sum insured", c.sum_insured, money),
        scalar("room_rent_cap", "Room rent cap", c.room_rent_cap, (v) => capText(v, si), "No cap stated"),
        scalar("icu_cap", "ICU cap", c.icu_cap, (v) => capText(v, si), "No cap stated"),
        scalar("co_pay_pct", "Co-payment", c.co_pay_pct, (v) => `${v}% of each claim`, "None stated"),
        scalar("deductible", "Deductible", c.deductible, (v) => <>{money(v)} per claim</>, "None stated"),
        scalar("network_only", "Network hospitals only", c.network_only, (v) => (v ? "Yes" : "No")),
      ],
    },
    {
      title: "Waiting periods",
      empty: "",
      rows: [
        scalar("initial", "Initial waiting period", c.waiting_periods.initial_days, days, "None stated"),
        scalar("pre", "Pre-existing conditions", c.waiting_periods.pre_existing_months, months, "None stated"),
        ...c.waiting_periods.specific_illness.map((s, i) =>
          scalar(`sp${i}`, `Specific illness: ${s.value?.illness ?? "unreadable"}`, s, (v) => months(v.months)),
        ),
      ],
    },
    {
      title: "Sub-limits",
      note: "Caps on what is paid for a named procedure.",
      empty: "No sub-limits found in this policy.",
      rows: c.sub_limits.map((s, i) =>
        scalar(`sub${i}`, s.value?.procedure ?? "unreadable", s, (v) => <>{money(v.limit)}</>),
      ),
    },
    {
      title: "Exclusions",
      note: "Treatments the policy does not pay for.",
      empty: "No exclusions found in this policy.",
      rows: c.exclusions.map((s, i) => scalar(`ex${i}`, s.value ?? "unreadable", s, () => "Not covered")),
    },
  ];
}

/** Split page text around the quote. Whitespace-insensitive and case-insensitive. */
function locate(page: string, quote: string): [string, string, string] | null {
  const words = quote.trim().split(/\s+/).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words[0]) return null;
  const m = new RegExp(words.join("\\s+"), "i").exec(page);
  return m ? [page.slice(0, m.index), m[0], page.slice(m.index + m[0].length)] : null;
}

function Source({ policy, cited }: { policy: Policy; cited: Cited<unknown> }) {
  const page = cited.source_page;
  const text = page ? policy.pages[page - 1] : undefined;
  const parts = text && cited.source_quote ? locate(text, cited.source_quote) : null;
  if (!page || !cited.source_quote) {
    return (
      <div className="source">
        <p className="muted">
          The model gave no source for this value. Check it against the document before relying on it.
        </p>
      </div>
    );
  }
  return (
    <div className="source">
      <p className="source-head">
        <span>
          Source, page {page}
          {policy.pages.length > 1 ? ` of ${policy.pages.length}` : ""}
        </span>
        {cited.quote_verified === false && <span className="bad">Quote not found on this page</span>}
        {cited.quote_verified === true && (
          <span className="ok">
            <Icon name="check" size={14} /> Quote found on this page
          </span>
        )}
      </p>
      <blockquote>{cited.source_quote}</blockquote>
      {text !== undefined && (
        <div
          className="page-text"
          tabIndex={0}
          role="region"
          aria-label={`Text of page ${page}`}
          ref={(el) => {
            const mark = el?.querySelector("mark") as HTMLElement | null;
            if (el && mark) el.scrollTop = Math.max(0, mark.offsetTop - el.clientHeight / 3);
          }}
        >
          {parts ? (
            <>
              {parts[0]}
              <mark>{parts[1]}</mark>
              {parts[2]}
            </>
          ) : (
            text
          )}
        </div>
      )}
    </div>
  );
}

export default function Coverage({ policy, onEstimate }: { policy: Policy; onEstimate: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const groups = useMemo(() => buildGroups(policy), [policy]);
  const all = groups.flatMap((g) => g.rows);
  const stated = all.filter((r) => r.stated);
  const flagged = all.filter((r) => r.cited.needs_review);
  const name = policy.source_name ?? "Pasted text";
  const startEstimate = () => {
    if (posthogEnabled)
      posthog.capture("claim_estimate_started", {
        needs_human_review: policy.needs_human_review,
        review_field_count: policy.review_fields.length,
      });
    onEstimate();
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Extracted coverage</h1>
          <p className="lede meta">
            {name} · {policy.pages.length} {policy.pages.length === 1 ? "page" : "pages"} · read by{" "}
            <code>{policy.model}</code>
          </p>
        </div>
        <button className="btn btn-primary" onClick={startEstimate} disabled={policy.coverage.sum_insured.value === null}>
          Estimate a claim <Icon name="arrow" />
        </button>
      </div>

      {policy.coverage.sum_insured.value === null && (
        <Alert title="Sum insured was not found">
          The payout calculation needs it. Add the missing page to the text and extract again.
        </Alert>
      )}
      {policy.coverage.warnings.length > 0 && (
        <div className="notice">
          <strong>Extraction notes</strong>
          <ul>
            {policy.coverage.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className={`summary ${flagged.length ? "summary-flag" : ""}`}>
        <p>
          {flagged.length > 0 ? (
            <>
              <ReviewChip>
                {flagged.length} {flagged.length === 1 ? "value needs" : "values need"} human review
              </ReviewChip>{" "}
              <span className="muted">
                of {stated.length} stated. Flagged when confidence is below the threshold or the quote is not on the
                cited page.
              </span>
            </>
          ) : (
            <>
              <strong>All {stated.length} stated values are above the review threshold</strong>
              <span className="muted"> and every quote was found on its cited page.</span>
            </>
          )}
        </p>
        {flagged.length > 0 && (
          <label className="check">
            <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} />
            Show only flagged
          </label>
        )}
      </div>

      {groups.map((g) => {
        const rows = onlyFlagged ? g.rows.filter((r) => r.cited.needs_review) : g.rows;
        if (onlyFlagged && rows.length === 0) return null;
        return (
          <section key={g.title} className="group" aria-labelledby={`g-${g.title}`}>
            <div className="group-head">
              <h2 id={`g-${g.title}`}>{g.title}</h2>
              {g.note && <p className="muted">{g.note}</p>}
            </div>
            {rows.length === 0 ? (
              <p className="empty">{g.empty}</p>
            ) : (
              <ul className="ledger" role="list">
                <li className="ledger-cols" aria-hidden="true">
                  <span>Field</span>
                  <span>Value</span>
                  <span className="r">Confidence</span>
                  <span />
                </li>
                {rows.map((r) => {
                  const isOpen = open === r.key;
                  const c = r.cited;
                  return (
                    <li key={r.key} className={`lrow ${c.needs_review ? "flagged" : ""} ${isOpen ? "open" : ""}`}>
                      <button
                        type="button"
                        className="lrow-btn"
                        aria-expanded={isOpen}
                        aria-controls={`src-${r.key}`}
                        onClick={() => {
                          if (!isOpen && posthogEnabled)
                            posthog.capture("coverage_source_opened", {
                              coverage_field: r.key,
                              needs_human_review: c.needs_review,
                            });
                          setOpen(isOpen ? null : r.key);
                        }}
                      >
                        <span className="f-label">{r.label}</span>
                        <span className={`f-value ${r.stated ? "" : "unstated"}`}>{r.value}</span>
                        <span className="f-conf">
                          {c.needs_review && <ReviewChip>Review</ReviewChip>}
                          <span className="num">{r.stated || c.confidence > 0 ? pct(c.confidence) : "n/a"}</span>
                        </span>
                        <span className="f-open">
                          <span className="sr-only">{isOpen ? "Hide source" : "Show source"}</span>
                          <Icon name="chevron" />
                        </span>
                      </button>
                      {isOpen && (
                        <div id={`src-${r.key}`}>
                          <Source policy={policy} cited={c} />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
