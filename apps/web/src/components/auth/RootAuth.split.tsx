import { SignedInHint } from "./signed-in";

/**
 * RootAuth with the app on its own host (C-148; next.config.ts aliases RootAuth.tsx to this file).
 * The public pages load none of Clerk: "signed in" comes from the session cookie hint, and the
 * signed-in app and Clerk's pages get Clerk's provider from app/(clerk)/layout.tsx.
 */
export function RootAuth({ children }: { children: React.ReactNode }) {
  return <SignedInHint>{children}</SignedInHint>;
}
