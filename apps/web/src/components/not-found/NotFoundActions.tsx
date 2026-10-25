"use client";

import { useAuth } from "@clerk/nextjs";
import type { Route } from "next";

import { CtaLink } from "@/components/marketing/primitives";
import { APP_PATH, SIGN_IN_PATH } from "@/lib/marketing/site";

/**
 * The public 404's ways out. Visitors get the home page, pricing and sign-in; once Clerk reports a
 * signed-in user, the app replaces sign-in. Static markup until then, so the page stays cheap.
 */
export function SiteNotFoundActions() {
  const { isLoaded, isSignedIn } = useAuth();
  const signedIn = isLoaded && isSignedIn === true;
  return (
    <>
      <CtaLink href={"/" as Route}>Go to the home page</CtaLink>
      <CtaLink href={"/pricing" as Route} variant="secondary">
        See pricing
      </CtaLink>
      {signedIn ? (
        <CtaLink href={APP_PATH as Route} variant="ghost" prefetch={false}>
          Open the app
        </CtaLink>
      ) : (
        <CtaLink href={SIGN_IN_PATH as Route} variant="ghost" prefetch={false}>
          Sign in
        </CtaLink>
      )}
    </>
  );
}
