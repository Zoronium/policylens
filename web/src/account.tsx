import { ClerkProvider, Show, SignInButton, UserButton, useAuth } from "@clerk/react";
import { useEffect, type ReactNode } from "react";
import { setTokenGetter } from "./api";

const KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

/** True when sign-in is configured. Without a key the site runs signed out, as before. */
export const ACCOUNTS = Boolean(KEY);

function Bridge({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();
  useEffect(() => setTokenGetter(() => getToken()), [getToken]);
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
