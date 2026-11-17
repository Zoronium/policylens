import { ClerkProvider, Show, SignInButton, UserButton, useAuth } from "@clerk/react";
import { useEffect, useRef, type ReactNode } from "react";
import { setTokenGetter } from "./api";
import { useConsent } from "./consent";
import posthog, { posthogEnabled } from "./posthog";

const KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

/** True when sign-in is configured. Without a key the site runs signed out, as before. */
export const ACCOUNTS = Boolean(KEY);

function Bridge({ children }: { children: ReactNode }) {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const identifiedUserId = useRef<string | null>(null);
  const consent = useConsent(); // re-run identify when the visitor accepts or withdraws

  useEffect(() => setTokenGetter(() => getToken()), [getToken]);

  useEffect(() => {
    if (!posthogEnabled || !isLoaded) return;

    if (isSignedIn && userId) {
      if (identifiedUserId.current !== userId) {
        if (identifiedUserId.current) posthog.reset();

        posthog.identify(userId); // the Clerk id only: no email or name leaves for analytics
        identifiedUserId.current = userId;
      }
      return;
    }

    if (identifiedUserId.current) {
      posthog.reset();
      identifiedUserId.current = null;
    }
  }, [isLoaded, isSignedIn, userId, consent]);

  return children;
}

export function AccountProvider({ children }: { children: ReactNode }) {
  if (!KEY) return children;
  return (
    <ClerkProvider publishableKey={KEY} afterSignOutUrl="#/">
      <Bridge>{children}</Bridge>
    </ClerkProvider>
  );
}

/** Sign in (email code or passkey, switched on in the Clerk dashboard); once in, My policies and the account menu. */
export function AccountNav({ current }: { current: boolean }) {
  if (!ACCOUNTS) return null;
  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="modal">
          <button type="button" className="btn">
            Sign in
          </button>
        </SignInButton>
      </Show>
      <Show when="signed-in">
        <a href="#/mine" aria-current={current ? "page" : undefined}>
          My policies
        </a>
        <UserButton />
      </Show>
    </>
  );
}

export { Show, SignInButton };
