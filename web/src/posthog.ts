import posthog from "posthog-js";

const key = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
const host = import.meta.env.VITE_POSTHOG_HOST as string | undefined;

/** True when a PostHog project is configured. Without it there is nothing to ask consent for. */
export const analyticsConfigured = Boolean(key && host);

/**
 * True only while the visitor has said yes. Call sites check it at event time (a live binding), so nothing
 * is sent, and PostHog is not even initialised, until consent is given.
 */
export let posthogEnabled = false;

let started = false;

export function startAnalytics() {
  if (!key || !host) return;
  if (!started) {
    posthog.init(key, {
      api_host: host,
      defaults: "2026-08-30",
      // The project may have replay switched on remotely; policy text is on screen, so never record it.
      disable_session_recording: true,
      capture_exceptions: {
        capture_unhandled_errors: true,
        capture_unhandled_rejections: true,
        capture_console_errors: false,
      },
    });
    started = true;
  } else {
    posthog.set_config({ persistence: "localStorage+cookie" });
    posthog.opt_in_capturing();
  }
  posthogEnabled = true;
}

/** PostHog's own cookies and storage all start with ph_ or __ph_. Ours (pl_consent) does not. */
export function wipePosthogState() {
  const mine = /^(__)?ph_/;
  for (const store of [localStorage, sessionStorage])
    for (const k of Object.keys(store)) if (mine.test(k)) store.removeItem(k);
  const host = location.hostname;
  for (const part of document.cookie.split(";")) {
    const name = part.split("=")[0].trim();
    if (!mine.test(name)) continue;
    for (const domain of ["", `;domain=${host}`, `;domain=.${host}`])
      document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/${domain}`;
  }
}

/** Withdraw: stop capturing and delete the anonymous id and every other PostHog cookie or storage entry. */
export function stopAnalytics() {
  posthogEnabled = false;
  if (!started) return;
  posthog.opt_out_capturing();
  posthog.set_config({ persistence: "memory" }); // stop it re-writing cookies and storage
  try {
    wipePosthogState();
  } catch {
    /* storage blocked: nothing was stored */
  }
}

export default posthog;
