"use client";

import { useAuth } from "@clerk/nextjs";
import type { Route } from "next";

import { CtaLink } from "@/components/marketing/primitives";
import { APP_PATH, SIGN_IN_PATH, appUrl, siteHref } from "@/lib/marketing/site";

/**
 * The public 404's ways out. Visitors get the home page, pricing and sign-in; once Clerk reports a
 * signed-in user, the app replaces sign-in. Static markup until then, so the page stays cheap.
 */
export function SiteNotFoundActions() {
  const { isLoaded, isSignedIn } = useAuth();
  const signedIn = isLoaded && isSignedIn === true;
  return (
    <>
      <CtaLink href={siteHref("/") as Route}>Go to the home page</CtaLink>
      <CtaLink href={siteHref("/pricing") as Route} variant="secondary">
        See pricing
      </CtaLink>
      {signedIn ? (
        <CtaLink href={appUrl(APP_PATH) as Route} variant="ghost" prefetch={false}>
          Open the app
        </CtaLink>
      ) : (
        <CtaLink href={appUrl(SIGN_IN_PATH) as Route} variant="ghost" prefetch={false}>
          Sign in
        </CtaLink>
      )}
    </>
  );
}
