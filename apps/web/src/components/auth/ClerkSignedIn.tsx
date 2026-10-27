"use client";

import { useAuth } from "@clerk/nextjs";

import { SignedInState } from "./signed-in";

/** Signed in, as Clerk reports it once loaded (one origin: Clerk is on every page anyway). */
export function ClerkSignedIn({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  return <SignedInState value={isLoaded && isSignedIn === true}>{children}</SignedInState>;
}
