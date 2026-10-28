import type { Route } from "next";

import { CtaLink } from "@/components/marketing/primitives";
import { SignedInSwitch } from "@/components/marketing/SignedInSwitch";
import { APP_PATH, SIGN_IN_PATH, appUrl, siteHref } from "@/lib/marketing/site";

/**
 * The public 404's ways out. Visitors get the home page, pricing and sign-in; once the browser
 * knows the visitor is signed in (useSignedIn, C-148), the app replaces sign-in. Static markup
 * until then, so the page stays cheap. The links render on the server and SignedInSwitch picks
 * one in the browser: the root not-found ships with every page's first load, so it must not bring
 * `cn` or Button into the browser (C-152).
 */
export function SiteNotFoundActions() {
  return (
    <>
      <CtaLink href={siteHref("/") as Route}>Go to the home page</CtaLink>
      <CtaLink href={siteHref("/pricing") as Route} variant="secondary">
        See pricing
      </CtaLink>
      <SignedInSwitch
        signedIn={
          <CtaLink href={appUrl(APP_PATH) as Route} variant="ghost" prefetch={false}>
            Open the app
          </CtaLink>
        }
        signedOut={
          <CtaLink href={appUrl(SIGN_IN_PATH) as Route} variant="ghost" prefetch={false}>
            Sign in
          </CtaLink>
        }
      />
    </>
  );
}
