import { analyticsConfigured } from "../posthog";

const REPO = "https://github.com/Zoronium/policylens";

export default function Privacy({ onCookieSettings }: { onCookieSettings: () => void }) {
  return (
    <div className="page prose">
      <h1>Privacy policy</h1>
      <p className="lede">
        PolicyLens is a portfolio demo. This page says what happens to your data when you use it. Last updated 18
        November 2026.
      </p>

      <h2>Who runs it</h2>
      <p>
        PolicyLens is a personal project by its author, published at <a href={REPO}>github.com/Zoronium/policylens</a>.
        For privacy questions or to ask for something to be deleted, open an issue there. Do not put policy text or
        personal details in the issue.
      </p>

      <h2>What you give it</h2>
      <ul>
        <li>
          <strong>Policy text or a file.</strong> What you paste or upload is sent to a language model provider
          (currently Groq, running an open-weight model) to extract the coverage terms. The provider processes it under
          its own terms.
        </li>
        <li>
          <strong>The result.</strong> The extracted coverage and the page text are stored in a MongoDB Atlas database so
          you can open the result and run estimates. There is no delete button yet. Ask for deletion through the
          repository and give the policy id from the address bar.
        </li>
        <li>
          <strong>Claim estimates.</strong> The figures you enter are sent to the server to calculate a payout. They are
          not stored.
        </li>
        <li>
          <strong>Do not upload real personal policies.</strong> The samples are synthetic. A policy extracted while
          signed out can be opened by anyone who has its address.
        </li>
      </ul>

      <h2>Accounts</h2>
      <p>
        Signing in is optional and handled by Clerk, which stores your email address or social login details and sets the
        cookies that keep you signed in. Policies extracted while signed in are stored with your Clerk user id and can
        only be opened by you.
      </p>

      <h2>Analytics</h2>
      {analyticsConfigured ? (
        <p>
          Only if you accept, PostHog records anonymous usage events (steps completed, counts, whether a result needed
          review) and page errors, and stores an identifier in your browser. If you are signed in, the event is tied to
          your Clerk user id. No email, name, policy text, quotes or amounts are sent, and your screen is not recorded. Declining changes nothing about
          how the site works. You can change your choice at any time.
        </p>
      ) : (
        <p>This deployment has no analytics configured, so nothing is collected for analytics.</p>
      )}
      {analyticsConfigured && (
        <p>
          <button type="button" className="btn" onClick={onCookieSettings}>
            Cookie settings
          </button>
        </p>
      )}

      <h2>Cookies and local storage</h2>
      <ul>
        <li>
          <strong>Sign-in (Clerk):</strong> session cookies, needed for signing in. Always on.
        </li>
        <li>
          <strong>Your cookie choice:</strong> one entry in local storage that remembers whether you accepted.
        </li>
        {analyticsConfigured && (
          <li>
            <strong>Analytics (PostHog):</strong> cookies or local storage with an anonymous id. Off until you accept,
            removed when you decline.
          </li>
        )}
      </ul>

      <h2>Logs and abuse limits</h2>
      <p>
        To limit use of the paid language model, the server counts requests per IP address in memory; the counts are not
        saved. The hosting platform and server logs can include IP addresses and are used only to run and secure the
        service.
      </p>

      <h2>Your choices</h2>
      <p>
        You can decline analytics, sign out, avoid uploading anything personal, and ask for stored policies to be deleted.
        Depending on where you live you may have further rights, such as access or correction; ask through the
        repository.
      </p>

      <h2>Not advice</h2>
      <p>
        PolicyLens estimates a payout from a simplified model of a policy. It is not insurance, legal or financial
        advice and does not decide any claim.
      </p>
    </div>
  );
}
