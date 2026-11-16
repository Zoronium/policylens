import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, hasSession, type Policy, type Sample } from "../api";
import Mascot from "../site/Mascot";
import { Alert, Icon, Skeleton } from "../ui";

function pretty(name: string) {
  return name
    .replace(/^\d+_/, "")
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

function insurerLine(text: string) {
  return text.split("\n").find((l) => l.includes("(fictional)"))?.replace(/\s*\(fictional\)/, "") ?? "";
}

export default function Upload({ onDone }: { onDone: (p: Policy) => void }) {
  const [mode, setMode] = useState<"paste" | "file">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [samplesError, setSamplesError] = useState(false);
  const [needCode, setNeedCode] = useState(false);
  const [code, setCode] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamplesError(true));
    api.health().then((h) => setNeedCode(h.auth_required && !hasSession())).catch(() => {});
  }, []);

  useEffect(() => {
    if (!busy) return;
    setElapsed(0);
    const t = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, [busy]);

  const canSubmit = (mode === "paste" ? text.trim().length > 0 : file !== null) && (!needCode || code.trim().length > 0);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    if (mode === "paste") form.append("text", text);
    else form.append("file", file!);
    try {
      if (needCode) {
        await api.login(code);
        setNeedCode(false);
        setCode("");
      }
      onDone(await api.createPolicy(form));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setNeedCode(true);
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  if (busy)
    return (
      <div className="page">
        <div className="busy-head">
          <Mascot mood="thinking" size={64} />
          <h1>Reading the policy</h1>
        </div>
        <p className="lede" role="status">
          The model is extracting coverage and quoting its sources. Every quote is then checked against the page it
          cites. {elapsed}s elapsed; most policies take 10 to 40 seconds.
        </p>
        <div className="busy-grid" aria-hidden="true">
          <Skeleton lines={4} />
          <Skeleton lines={4} />
          <Skeleton lines={3} />
        </div>
      </div>
    );

  return (
    <div className="page">
      <h1>Add a policy</h1>
      <p className="lede">
        Paste the text of a health insurance policy or upload a PDF. The model extracts what the policy says,
        with the page and quote for each value. It never calculates a payout.
      </p>

      <div className="upload-grid">
        <form onSubmit={submit} className="panel" aria-describedby={error ? "upload-error" : undefined}>
          <div className="seg" role="radiogroup" aria-label="Policy source">
            <label>
              <input type="radio" name="mode" checked={mode === "paste"} onChange={() => setMode("paste")} />
              <span>Paste text</span>
            </label>
            <label>
              <input type="radio" name="mode" checked={mode === "file"} onChange={() => setMode("file")} />
              <span>Upload file</span>
            </label>
          </div>

          {mode === "paste" ? (
            <div className="field">
              <label htmlFor="policy-text">Policy text</label>
              <textarea
                id="policy-text"
                rows={14}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={"Paste the policy wording here.\nMark page breaks with a line like: --- Page 2 ---"}
              />
              <p className="hint">Without page markers the whole text is read as page 1.</p>
            </div>
          ) : (
            <div className="field">
              <label htmlFor="policy-file">PDF or text file</label>
              <div
                className="drop"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files[0];
                  if (f) setFile(f);
                }}
              >
                <Icon name="file" size={22} />
                {file ? (
                  <p>
                    <strong>{file.name}</strong>
                    <span className="muted"> {(file.size / 1024).toFixed(0)} KB</span>
                  </p>
                ) : (
                  <p>Drop a file here, or choose one.</p>
                )}
                <input
                  id="policy-file"
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <p className="hint">Text-based PDFs only, up to 10 MB. Scanned pages need OCR first.</p>
            </div>
          )}

          {needCode && (
            <div className="field">
              <label htmlFor="access-code">Access code</label>
              <input
                id="access-code"
                type="text"
                autoComplete="one-time-code"
                spellCheck={false}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="XXXX-XXXX"
              />
              <p className="hint">
                Reading a policy uses a paid model, so it needs a code. Codes change every hour; ask the owner for the
                current one. Estimating a claim does not need a code.
              </p>
            </div>
          )}

          {error && (
            <div id="upload-error">
              <Alert title="Extraction failed">{error}</Alert>
            </div>
          )}

          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={!canSubmit}>
              Extract coverage <Icon name="arrow" />
            </button>
          </div>
        </form>

        <aside aria-labelledby="samples-h">
          <h2 id="samples-h">Or start from a sample</h2>
          <p className="hint">Synthetic policies in the IRDAI Customer Information Sheet style. Insurers are fictional.</p>
          {samples === null && !samplesError && <Skeleton lines={3} />}
          {samplesError && <p className="hint">Samples could not be loaded.</p>}
          {samples && (
            <ul className="samples">
              {samples.map((s) => (
                <li key={s.name}>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("paste");
                      setText(s.text);
                      setError(null);
                    }}
                  >
                    <span className="s-name">{pretty(s.name)}</span>
                    <span className="s-sub">{insurerLine(s.text)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <section className="split" aria-labelledby="split-h">
        <h2 id="split-h" className="sr-only">
          Who does what
        </h2>
        <div>
          <h3>The model reads</h3>
          <p>
            Sum insured, room rent cap, co-pay, deductible, waiting periods, sub-limits and exclusions, each with a
            confidence score, the page and a verbatim quote. Values it cannot back up are flagged for a person.
          </p>
        </div>
        <div>
          <h3>The rules decide</h3>
          <p>
            The payout comes from a fixed sequence of rules in plain code: waiting period, exclusions, room rent
            cap, sub-limit, deductible, co-pay, sum insured. No model is involved, and every step is shown.
          </p>
        </div>
      </section>
    </div>
  );
}
