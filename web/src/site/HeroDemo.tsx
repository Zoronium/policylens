import { Collapse, Row, Stage, Stream, Swap, type Act } from "../stageshow/kit";
import Frame from "./Frame";
import Mascot, { type Mood } from "./Mascot";
import { BILL, FIELDS, inr, PAYOUT, RUN, THINKING, TRAIL } from "./recorded";
import { fmt, tween } from "./tween";
import "./hero.css";

// The whole product in one story, played once as it scrolls into view. Left: the model reads the policy
// (tokens counting up, its own reasoning streaming, three cited fields landing). Right: the rules
// engine decides (the bill stepping down to the payout) while its token meter stays at zero.
// Words are the recorded ones in recorded.ts. The poster is the payoff.

type S = { phase: Mood; tokens: number; words: number; fields: number; step: number; amount: number; done: boolean };

const initial: S = { phase: "idle", tokens: 0, words: 0, fields: 0, step: 0, amount: 0, done: false };
const poster: S = { phase: "done", tokens: RUN.totalTokens, words: 999, fields: 3, step: 4, amount: PAYOUT, done: true };

const thinkText = (compact: boolean) => THINKING.slice(0, compact ? 1 : 2).join(" ");
const STEPS = TRAIL.filter((t) => t.delta !== 0); // the three that change the amount

async function script(a: Act<S>) {
  const compact = a.layout === "compact";
  const words = thinkText(compact).split(" ").length;
  const P = RUN.promptTokens;
  await a.wait(700);
  a.put({ phase: "reading" }); // the policy goes in
  await tween(a, "tokens", 0, P, 800);
  await a.wait(300);
  a.put({ phase: "thinking" });
  for (let i = 1; i <= words; i++) {
    a.put({ words: i, tokens: P + Math.round((RUN.reasoningTokens * i) / words) }); // 863 spent thinking
    await a.wait(55);
  }
  await a.wait(350);
  a.put({ phase: "reading" }); // the answer is written
  const T = P + RUN.reasoningTokens;
  for (let i = 1; i <= 3; i++) {
    a.put({ fields: i, tokens: T + Math.round((RUN.answerTokens * i) / 3) });
    await a.wait(420);
  }
  a.put({ phase: "done" });
  await a.wait(900);
  a.put({ step: 1 }); // the engine takes over
  await tween(a, "amount", 0, BILL, 500);
  await a.wait(300);
  let prev = BILL;
  for (let i = 0; i < STEPS.length; i++) {
    a.put({ step: 2 + i });
    await tween(a, "amount", prev, STEPS[i].amount, 450);
    prev = STEPS[i].amount;
    await a.wait(350);
  }
  a.put({ done: true });
  await a.wait(2400);
}

export default function HeroDemo() {
  return (
    <Stage
      width={720}
      height={420}
      compact={{ below: 600, width: 358, height: 660 }}
      initial={initial}
      poster={poster}
      script={script}
      play="once"
      greys="cool"
      className="pl-look hd"
    >
      {(s, _rect, layout) => {
        const compact = layout === "compact";
        return (
          <Frame compact={compact} title="Harbor Shield · Care Basic" className="hd-win">
            <div className="hd-cols">
              <section className="hd-col" aria-label="The model reads">
                <header className="hd-head">
                  <Mascot mood={s.phase} size={30} />
                  <span className="hd-title">The model reads</span>
                  <span className="hd-meter">
                    <span className="hd-count">{fmt(s.tokens)}</span>
                    <span className="hd-unit">tokens</span>
                  </span>
                </header>
                <div className="hd-think">
                  <span className="hd-label">Thinking, excerpt</span>
                  <Stream className="hd-stream" text={thinkText(compact)} count={s.words} />
                </div>
                <div className="hd-list">
                  {FIELDS.map((f, i) => (
                    <Collapse key={f.label} open={s.fields > i}>
                      <Row
                        pad={8}
                        title={<span className="hd-name">{f.label}</span>}
                        subtitle={compact ? undefined : <span className="hd-sub">Page {f.page}, quote found</span>}
                        meta={<span className="hd-val">{f.value}</span>}
                      />
                    </Collapse>
                  ))}
                </div>
              </section>

              <section className="hd-col" aria-label="The rules decide">
                <header className="hd-head">
                  <span className="hd-title">The rules decide</span>
                  <span className="hd-meter hd-meter--zero">
                    <span className="hd-count">0</span>
                    <span className="hd-unit">tokens</span>
                  </span>
                </header>
                <div className="hd-list">
                  <Collapse open={s.step >= 1}>
                    <Row pad={8} title={<span className="hd-name">Bill as submitted</span>} meta={<span className="hd-val">{inr(BILL)}</span>} />
                  </Collapse>
                  {STEPS.map((t, i) => (
                    <Collapse key={t.name} open={s.step >= 2 + i}>
                      <Row
                        pad={8}
                        title={<span className="hd-name">{t.name}</span>}
                        subtitle={compact ? undefined : <span className="hd-sub">{t.note}</span>}
                        meta={<span className="hd-val hd-val--cut">−{inr(-t.delta)}</span>}
                      />
                    </Collapse>
                  ))}
                </div>
                <div className="hd-pay">
                  <span className="hd-label">
                    <Swap id={s.done ? "pays" : "running"}>{s.done ? "Insurer pays" : "Running amount"}</Swap>
                  </span>
                  <span className="hd-amount">
                    <span className="hd-rupee">₹</span>
                    <span className="hd-num">{fmt(s.amount)}</span>
                  </span>
                </div>
              </section>
            </div>
          </Frame>
        );
      }}
    </Stage>
  );
}
