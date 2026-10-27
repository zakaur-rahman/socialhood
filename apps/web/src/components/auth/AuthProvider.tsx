import { ClerkProvider } from "@clerk/nextjs";

import { clerkAppearance } from "@/lib/clerk-appearance";
import { SITE_NAME, appOrigin, siteHref, siteUrl } from "@/lib/marketing/site";

// C-146: with the app on its own host, sign-out lands on the public site's home page, which Clerk
// allows only for origins it is told about.
const app = appOrigin();
const allowedRedirectOrigins = app ? [siteUrl(), app] : undefined;

/**
 * Clerk's provider with the product's appearance and copy. Where it sits (C-148): with one origin
 * (NEXT_PUBLIC_APP_URL unset: local dev, e2e, CI) the root layout wraps every page in it, as
 * before; with the app on its own host only the signed-in app and Clerk's pages (`app/(clerk)`)
 * are wrapped, so the public site ships no Clerk.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    // Clerk Core 3: the provider sits inside <body>.
    <ClerkProvider
      appearance={clerkAppearance}
      // The cards' titles name the product from SITE_NAME, not from the Clerk dashboard's
      // application name (C-139); the sign-up subtitle: the Free plan needs no card, as the
      // landing page says.
      localization={{
        signIn: { start: { title: `Sign in to ${SITE_NAME}`, subtitle: "Welcome back. Sign in to continue." } },
        signUp: { start: { title: `Create your ${SITE_NAME} account`, subtitle: "No credit card required." } },
      }}
      signInFallbackRedirectUrl="/app"
      signUpFallbackRedirectUrl="/app"
      afterSignOutUrl={siteHref("/")}
      allowedRedirectOrigins={allowedRedirectOrigins}
    >
      {children}
    </ClerkProvider>
  );
}
