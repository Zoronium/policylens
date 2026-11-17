import { useSyncExternalStore } from "react";
import { startAnalytics, stopAnalytics, wipePosthogState } from "./posthog";

export type Consent = "granted" | "denied" | null; // null = not asked yet

const KEY = "pl_consent";
const listeners = new Set<() => void>();

function read(): Consent {
  try {
    const v = localStorage.getItem(KEY);
    return v === "granted" || v === "denied" ? v : null;
  } catch {
    return null; // storage blocked: ask again next visit, send nothing meanwhile
  }
}

let current: Consent = read();
if (current === "granted") startAnalytics();
else {
  try {
    wipePosthogState(); // leftovers from an earlier visit or a withdrawn choice
  } catch {
    /* storage blocked */
  }
}

export function setConsent(next: Consent) {
  current = next;
  try {
    if (next) localStorage.setItem(KEY, next);
    else localStorage.removeItem(KEY);
  } catch {
    /* the choice still applies for this visit */
  }
  if (next === "granted") startAnalytics();
  else stopAnalytics();
  listeners.forEach((l) => l());
}

export function useConsent(): Consent {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => current,
  );
}
