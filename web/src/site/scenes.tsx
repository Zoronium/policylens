import { Badge, Check, Code, Collapse, Row, Stage, Stream, Swap, type Act } from "../stageshow/kit";
import Frame from "./Frame";
import Mascot, { type Mood } from "./Mascot";
import { BILL, inr, PAYOUT, RUN, THINKING, TRAIL } from "./recorded";
import { fmt, tween } from "./tween";
import "./scenes.css";

/* ---------------------------------------------------------------------------------------------- */
/* 1. Read: the policy goes in, the model thinks, structured JSON comes out. Tokens are counted.   */
/* ---------------------------------------------------------------------------------------------- */

const JSON_LINES = [
  "{",
  '  "sum_insured": {',
  '    "value": 500000,',
  '    "source_page": 1,',
  '    "source_quote": "Sum insured: Rs. 5,00,000 per policy year",',
  '    "confidence": 1.0',
  "  },",
  '  "room_rent_cap": { "value": { "kind": "pct_si", "amount": 1 }, …',
];

type R = { phase: Mood; sent: boolean; tokens: number; words: number; code: number; meters: boolean };
const R0: R = { phase: "idle", sent: false, tokens: 0, words: 0, code: 0, meters: false };
const RP: R = { phase: "done", sent: true, tokens: RUN.totalTokens, words: 999, code: JSON_LINES.length, meters: true };

// Phone width: the long quote line wraps onto a continuation line instead of running off the card.
const JSON_COMPACT = [
  "{",
  '  "sum_insured": {',
  '    "value": 500000,',
  '    "source_page": 1,',
  '    "source_quote": "Sum insured:',
  { text: '      Rs. 5,00,000 per policy year",', number: false },
  '    "confidence": 1.0',
  "  }, …",
];

const readText = (compact: boolean) => THINKING.slice(0, compact ? 1 : 3).join(" ");

async function readScript(a: Act<R>) {
  const compact = a.layout === "compact";
  const words = readText(compact).split(" ").length;
  const P = RUN.promptTokens;
  await a.wait(600);
  a.put({ sent: true, phase: "reading" }); // 1,051 tokens go in
  await tween(a, "tokens", 0, P, 900);
  await a.wait(300);
  a.put({ phase: "thinking" }); // 863 more are spent thinking
  for (let i = 1; i <= words; i++) {
    a.put({ words: i, tokens: P + Math.round((RUN.reasoningTokens * i) / words) });
    await a.wait(58);
  }
  await a.wait(400);
  a.put({ phase: "reading" }); // 687 to write the answer
  const T = P + RUN.reasoningTokens;
  const L = (compact ? JSON_COMPACT : JSON_LINES).length;
  for (let i = 1; i <= L; i++) {
    a.put({ code: i, tokens: T + Math.round((RUN.answerTokens * i) / L) });
    await a.wait(240);
  }
  a.put({ phase: "done", meters: true });
  await a.wait(3200);
}

export function ReadScene() {
  return (
    <Stage
      width={640}
      height={480}
      compact={{ below: 600, width: 358, height: 472 }}
      initial={R0}
      poster={RP}
      script={readScript}
      play="once"
      greys="cool"
      className="pl-look sc rs"
    >
      {(s, _r, layout) => {
        const compact = layout === "compact";
        return (
          <Frame compact={compact} title="Reading a policy" className="sc-win">
            <div className="sc-body">
              <Collapse open={s.sent} reveal="drop">
                <div className="rs-ask">
                  <span className="rs-file">harbor_shield_basic.txt · {RUN.pages} pages</span>
                  <span className="rs-msg">Extract the coverage, with page and quote for each value</span>
                </div>
              </Collapse>

              <div className="rs-think">
                <header className="rs-think-head">
                  <Mascot mood={s.phase} size={34} />
                  <span className="sc-strong">Thinking</span>
                  <span className="sc-meter">
                    <span className="sc-count">{fmt(s.tokens)}</span>
                    <span className="sc-unit">tokens so far</span>
                  </span>
                </header>
                <Stream className="rs-stream" text={readText(compact)} count={s.words} />
              </div>

              <Code className="rs-code" lines={compact ? JSON_COMPACT : JSON_LINES} count={s.code} numbers={false} />

              <Collapse open={s.meters}>
                <dl className="rs-meters">
                  <div>
                    <dt>Input</dt>
                    <dd>{fmt(RUN.promptTokens)}</dd>
                  </div>
                  <div>
                    <dt>Thinking</dt>
                    <dd>{fmt(RUN.reasoningTokens)}</dd>
                  </div>
                  <div>
                    <dt>Answer</dt>
                    <dd>{fmt(RUN.answerTokens)}</dd>
                  </div>
                  <div>
                    <dt>Time</dt>
                    <dd>{RUN.seconds} s</dd>
                  </div>
                </dl>
              </Collapse>
            </div>
          </Frame>
        );
      }}
    </Stage>
  );
}

/* ---------------------------------------------------------------------------------------------- */
/* 2. Check: every quote is looked up on the page it cites. A miss is flagged for a person.        */
/* ---------------------------------------------------------------------------------------------- */

const DOC_LINES = [
  "Sum insured: Rs. 5,00,000 per policy year",
  "Room rent is limited to 1% of the sum insured per day.",
  "Co-payment: You pay 10% of every admissible claim.",
  "Deductible: There is no deductible under this plan.",
];

// `hit` is the document line a quote was found on. The last row is an invented miss, labelled as one.
const CHECKS = [
  { field: "Sum insured", quote: "Sum insured: Rs. 5,00,000 per policy year", hit: 0, conf: "100%" },
  { field: "Co-payment", quote: "You pay 10% of every admissible claim", hit: 2, conf: "100%" },
  { field: "Deductible", quote: "There is no deductible under this plan", hit: 3, conf: "100%" },
  { field: "Room rent cap", quote: "Room rent is limited to 2% of the sum insured per day", hit: -1, conf: "30%" },
] as const;

type C = { looking: number; checked: number; hit: number };
const C0: C = { looking: -1, checked: 0, hit: -1 };
const CP: C = { looking: -1, checked: 4, hit: -1 };

async function checkScript(a: Act<C>) {
  await a.wait(700);
  for (let i = 0; i < CHECKS.length; i++) {
    a.put({ looking: i, hit: CHECKS[i].hit }); // the quote is searched for on the page
    await a.wait(i === 3 ? 1100 : 750);
    a.put({ checked: i + 1, hit: -1 });
    await a.wait(450);
  }
  a.put({ looking: -1 });
  await a.wait(3000);
}

export function CheckScene() {
  return (
    <Stage
      width={640}
      height={340}
      compact={{ below: 600, width: 358, height: 544 }}
      initial={C0}
      poster={CP}
      script={checkScript}
      play="once"
      greys="cool"
      className="pl-look sc cs"
    >
      {(s, _r, layout) => {
        const compact = layout === "compact";
        return (
          <Frame compact={compact} title="Checking quotes against page 1" className="sc-win">
            <div className="cs-cols">
              <div className="cs-doc" aria-label="Policy page 1">
                <span className="sc-faint">Page 1 of 3</span>
                {DOC_LINES.map((l, i) => (
                  <p key={l} className="cs-line" data-hit={s.hit === i || undefined}>
                    {l}
                  </p>
                ))}
              </div>
              <div className="cs-list">
                {CHECKS.map((c, i) => {
                  const done = s.checked > i;
                  const miss = c.hit < 0;
                  return (
                    <Row
                      key={c.field}
                      pad={8}
                      lead={<Check on={done && !miss} pending={s.looking === i && !done} size={18} />}
                      title={<span className="sc-name">{c.field}</span>}
                      subtitle={
                        <span className="sc-sub">
                          <Swap id={done ? (miss ? "miss" : "found") : s.looking === i ? "look" : "wait"}>
                            {done
                              ? miss
                                ? "Example miss: quote not on page 1"
                                : "Quote found on page 1"
                              : s.looking === i
                                ? "Looking for the quote"
                                : "Waiting"}
                          </Swap>
                        </span>
                      }
                      meta={
                        <span className="cs-meta" data-on={done || undefined}>
                          {miss ? <Badge tone="warning">Needs review</Badge> : <span className="sc-val">{c.conf}</span>}
                        </span>
                      }
                    />
                  );
                })}
              </div>
            </div>
          </Frame>
        );
      }}
    </Stage>
  );
}

/* ---------------------------------------------------------------------------------------------- */
/* 3. Decide: plain code applies the rules in order. The token meter stays at zero.                */
/* ---------------------------------------------------------------------------------------------- */

type D = { step: number; checked: number; amount: number; final: boolean };
const D0: D = { step: 0, checked: 0, amount: 0, final: false };
const DP: D = { step: TRAIL.length, checked: TRAIL.length, amount: PAYOUT, final: true };

async function decideScript(a: Act<D>) {
  await a.wait(600);
  let prev = 0;
  for (let i = 0; i < TRAIL.length; i++) {
    a.put({ step: i + 1 });
    await tween(a, "amount", prev, TRAIL[i].amount, i === 0 ? 500 : 400);
    prev = TRAIL[i].amount;
    a.put({ checked: i + 1 });
    await a.wait(i < 3 ? 380 : 700);
  }
  a.put({ final: true });
  await a.wait(3200);
}

export function DecideScene() {
  return (
    <Stage
      width={640}
      height={552}
      compact={{ below: 600, width: 358, height: 454 }}
      initial={D0}
      poster={DP}
      script={decideScript}
      play="once"
      greys="cool"
      className="pl-look sc ds"
    >
      {(s, _r, layout) => {
        const compact = layout === "compact";
        return (
          <Frame compact={compact} title="Estimate: cataract, 3 days" className="sc-win">
            <div className="sc-body">
              <header className="ds-head">
                <span className="sc-strong">Bill {inr(BILL)}</span>
                <Badge tone="success">0 tokens</Badge>
              </header>
              <div className="ds-list">
                {TRAIL.map((t, i) => (
                  <Collapse key={t.name} open={s.step > i}>
                    <Row
                      pad={8}
                      lead={<Check on={s.checked > i} pending={s.checked <= i} size={18} />}
                      title={<span className="sc-name">{t.name}</span>}
                      subtitle={compact ? undefined : <span className="sc-sub">{t.note}</span>}
                      meta={
                        <span className="ds-meta">
                          {t.delta !== 0 && <span className="ds-cut">−{inr(-t.delta)}</span>}
                          {!compact && <span className="sc-val">{inr(t.amount)}</span>}
                        </span>
                      }
                    />
                  </Collapse>
                ))}
              </div>
              <div className="ds-pay">
                <div className="ds-pay-text">
                  <span className="sc-faint">
                    <Swap id={s.final ? "pays" : "running"}>{s.final ? "Insurer pays" : "Running amount"}</Swap>
                  </span>
                  <span className="ds-amount">
                    <span className="ds-rupee">₹</span>
                    <span className="ds-num">{fmt(s.amount)}</span>
                  </span>
                </div>
                <Mascot mood={s.final ? "done" : "reading"} size={52} />
              </div>
            </div>
          </Frame>
        );
      }}
    </Stage>
  );
}
