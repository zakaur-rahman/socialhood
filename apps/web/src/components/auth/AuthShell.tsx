import type { ReactNode } from "react";

import { AuthLegal, type AuthMode } from "@/components/auth/AuthLegal";
import { HERO_AUDIENCE, HERO_LINE, HERO_TITLE } from "@/components/marketing/landing/copy";
import { LogoMark } from "@/components/marketing/primitives";
import { SITE_NAME, SITE_TAGLINE, siteHref } from "@/lib/marketing/site";
import { cx } from "@/lib/cx";

type Benefit = { title: string; body: string };

// Every line is the public site's own copy (the landing's features, setup steps and trust row); nothing is invented.
const BENEFITS: Record<AuthMode, Benefit[]> = {
  "sign-in": [
    {
      title: "AI replies from your own knowledge",
      body: "It drafts or sends replies using only what's in your knowledge base.",
    },
    {
      title: "One inbox, with a hand-off",
      body: "Instagram DMs and WhatsApp chats arrive in real time. Unsure or upset? It goes to Needs you.",
    },
    {
      title: "Comment and DM automations",
      body: "A comment with your keyword gets the link in a private DM, with an optional public reply.",
    },
  ],
  "sign-up": [
    { title: "Free plan, no card needed", body: "Start free, upgrade when you grow." },
    {
      title: "Set up in three steps",
      body: "Connect your accounts, add your knowledge, then let the AI draft or reply.",
    },
    {
      title: "Official Meta APIs",
      body: "Connect with Instagram's own login and Meta's official setup. Amplychat never asks for your password.",
    },
  ],
};

/** The landing's headline in its phrases ("Every DM.", "Every comment.", "One inbox."). */
const TITLE_PHRASES = HERO_TITLE.split(/(?<=\.)\s+/);

/** The three channels in the site's motif order (Instagram, WhatsApp, website chat), in their marks on night. */
const CHANNEL_MARKS = ["bg-instagram-night", "bg-whatsapp", "bg-web-night"] as const;

/** The logo, linking to the public site's home (on its own host when the app has one, C-146). */
function HomeLink({ className }: { className?: string }) {
  return (
    <a href={siteHref("/")} className={cx("inline-flex min-h-11 items-center gap-2.5 rounded-lg", className)}>
      <LogoMark className="size-8" />
      <span className="text-base font-semibold tracking-tight">{SITE_NAME}</span>
    </a>
  );
}

/**
 * The sign-in and sign-up page (UI-079, redrawn for C-158 in the public site's language).
 *
 * - From `lg`: the site's **night** band on the left (the same colours in Dark and Light, as on the
 *   site), with the logo back to the site, the landing's headline and line, three plain lines of the
 *   site's own copy and the channel motif; Clerk's card on the right on the app's canvas, in the
 *   member's theme (C-129). The panel stays put while the form column scrolls.
 * - Below `lg`: a bar with the logo, the card, and the legal line: the page is the task.
 * - The legal line (AuthLegal) sits at the column's foot on every width.
 *
 * No screenshot, glow, grain or gradient (C-157's rules for the site). The card is Clerk's own, styled
 * by `authCardAppearance` (lib/clerk-appearance.ts): its title is the page's one h1, for every step.
 */
export function AuthShell({ mode, children }: { mode: AuthMode; children: ReactNode }) {
  return (
    <main
      id="main"
      data-auth-shell={mode}
      className="group/auth min-h-dvh bg-canvas text-fg lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]"
    >
      <section
        aria-label={`About ${SITE_NAME}`}
        className="hidden bg-night text-night-ink lg:sticky lg:border-r lg:border-line lg:top-0 lg:flex lg:h-dvh lg:flex-col lg:justify-between lg:gap-10 lg:overflow-y-auto lg:px-12 lg:py-8 xl:px-16 2xl:px-24"
      >
        <HomeLink className="self-start text-night-ink" />
        <div className="max-w-xl">
          {/* Broken only between its phrases, as the landing's H1 is. */}
          <p className="text-site-h2-sm font-bold tracking-site-h2-sm">
            {TITLE_PHRASES.map((phrase, i) => (
              <span key={phrase}>
                {i > 0 && " "}
                <span className="inline-block">{phrase}</span>
              </span>
            ))}
          </p>
          <p className="mt-6 max-w-prose text-site-lede text-night-ink-secondary">
            <b className="font-semibold text-night-ink">{HERO_AUDIENCE}</b> {HERO_LINE}
          </p>
          <ul className="mt-12 space-y-6 [@media(max-height:760px)]:hidden">
            {BENEFITS[mode].map(({ title, body }) => (
              <li key={title}>
                <span className="block text-site-body font-semibold text-night-ink">{title}</span>
                <span className="mt-1 block max-w-prose text-site-label text-night-ink-secondary">{body}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="flex items-center gap-3 text-site-label text-night-ink-tertiary">
          <span aria-hidden className="inline-flex gap-1">
            {CHANNEL_MARKS.map((mark) => (
              <i key={mark} className={cx("size-2 rounded-sm", mark)} />
            ))}
          </span>
          {SITE_TAGLINE}
        </p>
      </section>

      <div className="flex min-h-dvh flex-col px-4 sm:px-8 lg:px-12">
        <header className="flex h-16 shrink-0 items-center lg:hidden">
          <HomeLink />
        </header>
        <div className="flex flex-1 items-start justify-center pt-4 pb-8 sm:items-center sm:py-10">
          <div className="w-full max-w-100">{children}</div>
        </div>
        <AuthLegal mode={mode} className="mx-auto w-full max-w-100 shrink-0 pb-6 text-center" />
      </div>
    </main>
  );
}
