import { useState } from "react";
import { Icon } from "../ui";
import HeroDemo from "./HeroDemo";
import Mascot from "./Mascot";
import { EVALS, RUN } from "./recorded";
import "./site.css";

export default function Home() {
  const [run, setRun] = useState(0);
  return (
    <>
      <section className="hero" aria-labelledby="hero-h">
        <div className="hero-copy">
          <h1 id="hero-h">A model reads the policy. Plain code works out the payout.</h1>
          <p className="hero-lede">
            PolicyLens pulls the coverage terms out of a health insurance policy, each with a page number and a quote
            you can check. Then a fixed set of rules calculates what the insurer should pay. Every rupee has a line in
            the audit trail.
          </p>
          <div className="cta-row">
            <a className="btn btn-primary btn-lg" href="#/try">
              Try it with a sample policy <Icon name="arrow" />
            </a>
            <a className="btn btn-lg" href="#/how">
              See how it works
            </a>
          </div>
          <p className="hero-proof">
            In the recorded run on this page, reading the policy took {RUN.totalTokens.toLocaleString("en-IN")} tokens.
            Working out the payout took none.
          </p>
        </div>
        <div className="hero-demo" id="hero-demo">
          <HeroDemo key={run} />
          <div className="demo-foot">
            <button className="replay" type="button" onClick={() => setRun((n) => n + 1)}>
              Replay
            </button>
          </div>
        </div>
      </section>

      <section className="band" aria-labelledby="steps-h">
        <div className="wrap">
          <h2 id="steps-h">What happens to a policy</h2>
          <ol className="three">
            <li>
              <span className="three-n">1</span>
              <h3>Read</h3>
              <p>
                The model returns structured coverage. For every value it gives the page and a verbatim quote from
                that page.
              </p>
            </li>
            <li>
              <span className="three-n">2</span>
              <h3>Check</h3>
              <p>
                The server looks for each quote on the page it cites. A value with a missing quote or a low
                confidence is flagged for a person.
              </p>
            </li>
            <li>
              <span className="three-n">3</span>
              <h3>Decide</h3>
              <p>
                Waiting period, exclusions, room rent cap, sub-limit, deductible, co-pay, sum insured: plain code
                applies them in order. No model is involved.
              </p>
            </li>
          </ol>
          <p className="more">
            <a href="#/how">Watch each step run, with the recorded tokens and reasoning</a>
          </p>
        </div>
      </section>

      <section className="wrap numbers" aria-labelledby="num-h">
        <h2 id="num-h">How well does it read?</h2>
        <dl className="stats">
          <div>
            <dt>Field accuracy</dt>
            <dd>{EVALS.accuracy}</dd>
          </div>
          <div>
            <dt>Quotes found on the cited page</dt>
            <dd>{EVALS.citations}</dd>
          </div>
          <div>
            <dt>Fields flagged for review</dt>
            <dd>{EVALS.flagged}</dd>
          </div>
        </dl>
        <p className="caveat">
          One run on {EVALS.policies} synthetic policies ({EVALS.fields} fields, {EVALS.citationCount} quotes). The
          policies were written and labelled by the same person in fairly regular layouts, so read these as an upper
          bound. The one wrong field was not flagged, so the review flag has not yet been shown to catch errors on this
          set.
        </p>
      </section>

      <section className="closing" aria-labelledby="close-h">
        <div className="wrap closing-in">
          <Mascot mood="idle" size={84} />
          <div>
            <h2 id="close-h">Try it on a sample policy</h2>
            <p>
              Reading a policy uses a paid model, so the public demo limits how often it can run. Estimating a claim
              uses no model.
            </p>
          </div>
          <a className="btn btn-primary btn-lg" href="#/try">
            Add a policy <Icon name="arrow" />
          </a>
        </div>
      </section>
    </>
  );
}
