import { useState, type ReactNode } from "react";
import { Icon } from "../ui";
import Mascot from "./Mascot";
import { CheckScene, DecideScene, ReadScene } from "./scenes";
import { RUN } from "./recorded";
import "./site.css";

function Scene({ n, title, copy, fact, children }: { n: number; title: string; copy: ReactNode; fact: ReactNode; children: ReactNode }) {
  const [run, setRun] = useState(0);
  return (
    <section className="scene" aria-labelledby={`sc-${n}`}>
      <div className="scene-copy">
        <span className="scene-label">Step {n}</span>
        <h2 id={`sc-${n}`}>{title}</h2>
        <p>{copy}</p>
        <p className="fact">{fact}</p>
      </div>
      <div className="scene-demo" key={run} id={`scene-${n}`}>
        {children}
        <div className="demo-foot">
          <button className="replay" type="button" onClick={() => setRun((r) => r + 1)}>
            Replay
          </button>
        </div>
      </div>
    </section>
  );
}

export default function How() {
  return (
    <>
      <div className="how-hero">
        <div>
          <h1>Three steps, and only the first one uses a model</h1>
          <p>
            Watch a policy go through PolicyLens. The numbers and the model's own words below come from one real run;
            the animation replays them.
          </p>
        </div>
        <Mascot mood="reading" size={96} label="Lens, the PolicyLens mascot, reading" />
      </div>
      <p className="how-note">
        Recorded {RUN.date}: {RUN.model} on {RUN.provider}, the synthetic Harbor Shield sample, {RUN.pages} pages.
      </p>

      <Scene
        n={1}
        title="The model reads, and thinks, and the tokens add up"
        copy="The policy goes in as text. The model reasons about it, then writes structured coverage: each value with the page it came from and a quote from that page. Reasoning tokens are billed like any others."
        fact={
          <>
            {RUN.promptTokens.toLocaleString("en-IN")} tokens in, {RUN.reasoningTokens} spent thinking, {RUN.answerTokens} to
            write the answer: {RUN.totalTokens.toLocaleString("en-IN")} in {RUN.seconds} seconds. The thinking text is the model's own,
            cut for length.
          </>
        }
      >
        <ReadScene />
      </Scene>

      <Scene
        n={2}
        title="The server checks every quote"
        copy="A model can cite a page and still misquote it. So the server looks for each quote on the page it names. A quote that is not there caps the confidence at 30 percent and the value goes to a person for review."
        fact="In the recorded run every quote was found. The last row, a misread 2 percent room rent limit, is an invented miss that shows what a flag looks like."
      >
        <CheckScene />
      </Scene>

      <Scene
        n={3}
        title="Plain code decides, and the token meter stays at zero"
        copy="The payout comes from a fixed sequence of rules: waiting period, exclusions, room rent cap with proportionate deduction, sub-limit, deductible, co-pay, sum insured. Each step shows the amount before and after. Same inputs, same answer."
        fact="This is the engine's real output for a cataract admission with a ₹91,000 bill. It spent no tokens, because it contains no model."
      >
        <DecideScene />
      </Scene>

      <section className="closing" aria-labelledby="how-close">
        <div className="wrap closing-in">
          <Mascot mood="idle" size={84} />
          <div>
            <h2 id="how-close">Run it on a policy</h2>
            <p>Paste a policy or start from a sample, review what was extracted, then estimate a claim.</p>
          </div>
          <a className="btn btn-primary btn-lg" href="#/try">
            Try it with a sample policy <Icon name="arrow" />
          </a>
        </div>
      </section>
    </>
  );
}
