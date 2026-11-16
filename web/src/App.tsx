import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Policy } from "./api";
import Coverage from "./screens/Coverage";
import Estimate from "./screens/Estimate";
import Upload from "./screens/Upload";
import { Alert, Skeleton } from "./ui";

type Route = { screen: "upload" } | { screen: "coverage" | "estimate"; id: string };

function parseHash(): Route {
  const m = /^#\/p\/([\w-]+)(\/estimate)?$/.exec(window.location.hash);
  if (!m) return { screen: "upload" };
  return { screen: m[2] ? "estimate" : "coverage", id: m[1] };
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseHash);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const on = () => setRoute(parseHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const id = route.screen === "upload" ? null : route.id;
  useEffect(() => {
    if (!id) return;
    if (policy?.id === id) return;
    let live = true;
    setLoadError(null);
    api
      .getPolicy(id)
      .then((p) => live && setPolicy(p))
      .catch((e: ApiError) => live && setLoadError(e.message));
    return () => {
      live = false;
    };
  }, [id, policy?.id]);

  useEffect(() => {
    const names = { upload: "Add a policy", coverage: "Extracted coverage", estimate: "Estimate a claim" };
    document.title = `${names[route.screen]} · PolicyLens`;
    window.scrollTo({ top: 0 });
  }, [route.screen]);

  const go = useCallback((hash: string) => {
    window.location.hash = hash;
  }, []);

  const ready = id && policy?.id === id ? policy : null;
  const step = route.screen === "upload" ? 1 : route.screen === "coverage" ? 2 : 3;

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="top">
        <div className="top-inner">
          <a className="brand" href="#/" aria-label="PolicyLens, add a policy">
            <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
              <rect width="32" height="32" rx="7" fill="var(--accent)" />
              <circle cx="15" cy="15" r="6" fill="none" stroke="#fff" strokeWidth="2.5" />
              <path d="M20 20l5 5" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            PolicyLens
          </a>
          <nav aria-label="Steps" className="steps">
            <a href="#/" aria-current={step === 1 ? "step" : undefined}>
              <span className="n">1</span>Policy
            </a>
            <StepLink n={2} label="Coverage" current={step === 2} href={ready ? `#/p/${ready.id}` : null} />
            <StepLink n={3} label="Estimate" current={step === 3} href={ready ? `#/p/${ready.id}/estimate` : null} />
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        {route.screen === "upload" && <Upload onDone={(p) => { setPolicy(p); go(`#/p/${p.id}`); }} />}
        {route.screen !== "upload" && loadError && (
          <div className="page">
            <Alert title="Could not load this policy">{loadError}</Alert>
            <p>
              <a href="#/">Add a policy</a>
            </p>
          </div>
        )}
        {route.screen !== "upload" && !loadError && !ready && (
          <div className="page" aria-busy="true">
            <Skeleton lines={5} />
          </div>
        )}
        {route.screen === "coverage" && ready && (
          <Coverage policy={ready} onEstimate={() => go(`#/p/${ready.id}/estimate`)} />
        )}
        {route.screen === "estimate" && ready && <Estimate policy={ready} onBack={() => go(`#/p/${ready.id}`)} />}
      </main>

      <footer className="foot">
        <div className="foot-inner">
          <span>
            The model reads the document. A fixed set of rules calculates the payout. All sample policies are
            synthetic.
          </span>
        </div>
      </footer>
    </>
  );
}

function StepLink({ n, label, current, href }: { n: number; label: string; current: boolean; href: string | null }) {
  if (!href)
    return (
      <span className="step-off" aria-disabled="true">
        <span className="n">{n}</span>
        {label}
      </span>
    );
  return (
    <a href={href} aria-current={current ? "step" : undefined}>
      <span className="n">{n}</span>
      {label}
    </a>
  );
}
