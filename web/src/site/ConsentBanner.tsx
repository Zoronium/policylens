import { setConsent, useConsent } from "../consent";
import "./consent.css";

/** Asks once about analytics. Declining is as easy as accepting and the site works the same either way. */
export default function ConsentBanner({ onClose }: { onClose: () => void }) {
  const consent = useConsent();
  const choose = (c: "granted" | "denied") => {
    setConsent(c);
    onClose();
  };
  return (
    <section className="consent" aria-labelledby="consent-h">
      <h2 id="consent-h">Analytics cookies</h2>
      <p>
        With your OK, PostHog counts which steps people use (for example "extraction finished") and reports page
        errors. It never receives the policy text you paste or upload. Cookies that keep you signed in are always on
        and are not affected by this choice. <a href="#/privacy">Privacy policy</a>
      </p>
      <div className="consent-actions">
        <button type="button" className="btn" onClick={() => choose("denied")} aria-pressed={consent === "denied"}>
          Decline
        </button>
        <button type="button" className="btn" onClick={() => choose("granted")} aria-pressed={consent === "granted"}>
          Accept analytics
        </button>
      </div>
    </section>
  );
}
