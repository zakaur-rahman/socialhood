import { AuthProvider } from "./AuthProvider";
import { ClerkSignedIn } from "./ClerkSignedIn";

/**
 * What the root layout wraps every page in (C-148). This is the one-origin version
 * (NEXT_PUBLIC_APP_URL unset: local dev, e2e, CI): Clerk's provider on every page, as before, and
 * the public header's "signed in" from Clerk.
 *
 * With the app on its own host, next.config.ts aliases this module to RootAuth.split.tsx, which
 * loads no Clerk at all. A module swap rather than an `if`: every client component a layout imports
 * ships with its pages whether it renders or not, so the choice has to be made at build time.
 */
export function RootAuth({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ClerkSignedIn>{children}</ClerkSignedIn>
    </AuthProvider>
  );
}
