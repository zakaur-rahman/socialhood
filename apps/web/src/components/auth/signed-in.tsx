"use client";

import { createContext, useContext, useSyncExternalStore } from "react";

import { signedInHint } from "@/lib/auth/session-hint";

/**
 * Whether the public pages' visitor is signed in, for the header's "Open app" and the 404's way
 * out (C-148). Signed out until the browser says otherwise: the pages are static, so that's what
 * the server rendered. The value comes from Clerk (ClerkSignedIn, one origin) or from the session
 * cookie hint (SignedInHint, the app on its own host, where the public site loads no Clerk).
 */
const SignedInContext = createContext(false);

export function useSignedIn(): boolean {
  return useContext(SignedInContext);
}

export function SignedInState({ value, children }: { value: boolean; children: React.ReactNode }) {
  return <SignedInContext.Provider value={value}>{children}</SignedInContext.Provider>;
}

const noSubscription = () => () => {};

/** The cookie hint: signed out on the server and while hydrating, then what the cookie says. */
export function SignedInHint({ children }: { children: React.ReactNode }) {
  const signedIn = useSyncExternalStore(noSubscription, () => signedInHint(document.cookie), () => false);
  return <SignedInState value={signedIn}>{children}</SignedInState>;
}
