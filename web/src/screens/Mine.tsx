import { useEffect, useState } from "react";
import { Show, SignInButton } from "../account";
import { api, type PolicySummary } from "../api";
import { Alert, Skeleton } from "../ui";

function List() {
  const [items, setItems] = useState<PolicySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .mine()
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, []);
  if (error) return <Alert title="Could not load your policies">{error}</Alert>;
  if (!items) return <Skeleton lines={4} />;
  if (!items.length)
    return (
      <p className="hint">
        Nothing saved yet. Policies you extract while signed in are saved here. <a href="#/try">Add a policy</a>
      </p>
    );
  return (
    <ul className="samples">
      {items.map((p) => (
        <li key={p.id}>
          <a href={`#/p/${p.id}`}>
            <span className="s-name">{p.source_name ?? "Pasted policy"}</span>
            <span className="s-sub">
              {new Date(p.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
              {p.needs_human_review ? " · needs review" : ""}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export default function Mine() {
  return (
    <div className="page">
      <h1>My policies</h1>
      <Show when="signed-in">
        <p className="lede">Policies you extracted while signed in. Only you can open them.</p>
        <List />
      </Show>
      <Show when="signed-out">
        <p className="lede">Sign in to keep the policies you extract and come back to them.</p>
        <SignInButton mode="modal">
          <button type="button" className="btn btn-primary">
            Sign in
          </button>
        </SignInButton>
      </Show>
    </div>
  );
}
