"use client";

import { SignOutButton } from "@clerk/nextjs";

import { LogoMark } from "@/components/marketing/primitives";
import { Button } from "@/components/ui/button";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { SITE_NAME, siteHref } from "@/lib/marketing/site";

/**
 * What a signed-in visitor sees while the website is live without the API (the website-only
 * deploy, C-145): the account exists, the app doesn't run yet. Without it every screen would fail
 * its first request and show an error.
 */
export function PrelaunchNotice() {
  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-16">
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-8 text-center">
        <LogoMark className="mx-auto size-12 rounded-xl" />
        <h1 className="mt-6 text-xl font-semibold tracking-tight text-fg">Your account is ready</h1>
        <p className="mt-3 text-sm text-fg-secondary">
          {SITE_NAME} opens soon. We&apos;ll email you when your inbox, AI replies and automations are ready to
          use.
        </p>
        <p className="mt-3 text-sm text-fg-secondary">
          Questions? Write to{" "}
          <a className="text-brand-fg underline underline-offset-4" href={`mailto:${SUPPORT_EMAIL}`}>
            {SUPPORT_EMAIL}
          </a>
          .
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild variant="secondary">
            <a href={siteHref("/")}>Back to the website</a>
          </Button>
          <SignOutButton redirectUrl={siteHref("/")}>
            <Button variant="ghost">Sign out</Button>
          </SignOutButton>
        </div>
      </div>
    </main>
  );
}
