import { BadgeCheck, Inbox, ListChecks, Sparkles, Zap, type LucideIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { HERO_TITLE } from "@/components/marketing/Hero";
import { LogoMark } from "@/components/marketing/primitives";
import { SHOTS } from "@/components/marketing/shots";
import { cn } from "@/lib/utils";

type AuthMode = "sign-in" | "sign-up";

type Benefit = { icon: LucideIcon; title: string; body: string };

// Every line is the landing page's own copy (Features, HowItWorks, the Hero's trust row); nothing is invented.
const BENEFITS: Record<AuthMode, Benefit[]> = {
  "sign-in": [
    {
      icon: Sparkles,
      title: "AI replies from your own knowledge",
      body: "It drafts or sends replies using only what's in your knowledge base, in English, Hindi and Hinglish.",
    },
    {
      icon: Inbox,
      title: "One inbox, with a hand-off",
      body: "Instagram DMs and WhatsApp chats arrive in real time. Unsure or upset? It goes to Needs you.",
    },
    {
      icon: Zap,
      title: "Comment and DM automations",
      body: "A comment with your keyword gets the link in a private DM, with an optional public reply.",
    },
  ],
  "sign-up": [
    { icon: Sparkles, title: "Free plan, no card needed", body: "Start free, upgrade when you grow." },
    {
      icon: ListChecks,
      title: "Set up in three steps",
      body: "Connect your accounts, add your knowledge, then let the AI draft or reply.",
    },
    {
      icon: BadgeCheck,
      title: "Official Meta APIs",
      body: "Connect with Instagram's own login and Meta's official setup. Social Hood never asks for your password.",
    },
  ],
};

function BenefitList({ mode, className, itemClass }: { mode: AuthMode; className?: string; itemClass?: string }) {
  return (
    <ul className={className}>
      {BENEFITS[mode].map(({ icon: Icon, title, body }) => (
        <li key={title} className={cn("flex gap-3", itemClass)}>
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand-fg">
            <Icon className="size-4" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-fg">{title}</span>
            <span className="block text-sm text-fg-secondary">{body}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * The sign-in and sign-up page (UI-079): a brand panel in the landing page's language (promise,
 * benefits, the real inbox screen) beside Clerk's card. From `lg` the page is exactly one viewport
 * tall and the screenshot fades out at the panel's bottom and right. Below `lg` the panel shrinks to
 * a header (logo and promise), the card follows, and from `md` the benefits and an untilted inbox
 * shot fill the space below it. The card is Clerk's own, styled by `authAppearance`: the logo,
 * its title (the page's h1) and subtitle, the Google button, the fields and the "Sign in" / "Sign
 * up" switch in its footer, so every step (verify your email, second factor) has one h1.
 */
export function AuthShell({ mode, children }: { mode: AuthMode; children: ReactNode }) {
  return (
    <main id="main" className="flex min-h-dvh flex-col lg:grid lg:h-dvh lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:grid-rows-1 lg:overflow-hidden">
      <section
        aria-label="About Social Hood"
        className="relative overflow-hidden px-4 pt-6 pb-2 sm:px-8 lg:flex lg:min-h-0 lg:flex-col lg:border-r lg:border-line lg:px-12 lg:pt-10 lg:pb-0 xl:px-16 2xl:px-24"
      >
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-glow-brand" />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-repeat opacity-5"
          style={{ backgroundImage: "url(/grain.jpg)" }}
        />
        <div className="relative max-w-xl">
          <Link href="/" className="inline-flex min-h-10 items-center gap-2.5 rounded-lg">
            <LogoMark className="size-9" />
            <span className="text-base font-semibold tracking-tight">Social Hood</span>
          </Link>
          <p className="mt-3 text-sm text-pretty text-fg-secondary lg:mt-6 lg:text-2xl lg:leading-tight lg:font-semibold lg:tracking-tight lg:text-fg xl:text-3xl 2xl:text-4xl">
            {HERO_TITLE}
          </p>
          <BenefitList
            mode={mode}
            className="mt-6 hidden space-y-3 lg:block"
            itemClass="[@media(max-height:860px)]:last:hidden"
          />
        </div>
        {/* The screenshot bleeds off the panel's bottom and right, fading into the panel colour. */}
        <div className="relative mt-6 hidden min-h-0 flex-1 lg:block">
          <div className="absolute top-0 left-0 w-[118%] [mask-composite:intersect] [mask-image:linear-gradient(to_bottom,black_55%,transparent_96%),linear-gradient(to_right,black_45%,transparent_82%)]">
            <div className="w-[92%] [transform-origin:left_center] [transform:perspective(1600px)_rotateY(-9deg)_rotateX(3deg)]">
              <div className="rounded-2xl border border-line-strong bg-panel p-1.5 shadow-2xl shadow-brand/15 xl:p-2">
                <div className="overflow-hidden rounded-xl border border-line bg-canvas">
                  <Image
                    src={SHOTS.inbox.src}
                    width={SHOTS.inbox.width}
                    height={SHOTS.inbox.height}
                    alt={SHOTS.inbox.alt}
                    sizes="(min-width: 1024px) 65vw, 1px"
                    className="h-auto w-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="relative flex flex-col items-center justify-center gap-5 px-4 py-6 sm:px-8 lg:justify-start lg:overflow-y-auto lg:px-10 lg:py-12 lg:before:flex-1 lg:before:content-[''] lg:after:flex-1 lg:after:content-['']">
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-glow-brand opacity-50" />
        <div className="relative w-full max-w-sm">{children}</div>
      </section>

      {/* Tablet: the space below the card, with the same benefits and the inbox shot (untilted). */}
      <section aria-label="What Social Hood does" className="hidden px-8 pt-4 pb-12 md:block lg:hidden">
        <div className="mx-auto max-w-3xl">
          <BenefitList mode={mode} className="grid grid-cols-3 gap-6" />
          <div className="mt-10 rounded-2xl border border-line-strong bg-panel p-2 shadow-2xl shadow-brand/15">
            <div className="overflow-hidden rounded-xl border border-line bg-canvas">
              <Image
                src={SHOTS.inbox.src}
                width={SHOTS.inbox.width}
                height={SHOTS.inbox.height}
                alt={SHOTS.inbox.alt}
                sizes="(min-width: 768px) 704px, 1px"
                className="h-auto w-full"
              />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

/**
 * The sign-in and sign-up card, as the owner asked (2026-10-17): the Social Hood logo inside the
 * card, Clerk's title and subtitle, one bordered Google button, the "or" divider, bordered fields,
 * a full-width Continue, and the switch link plus "Secured by Clerk" in the footer. The colours
 * come from the app-wide `clerkAppearance` (root layout); these are layout and shape only, on the
 * app's tokens.
 */
export const authAppearance = {
  options: {
    logoPlacement: "inside",
    logoImageUrl: "/icons/icon-192.png",
    logoLinkUrl: "/",
    socialButtonsVariant: "blockButton",
  },
  elements: {
    cardBox: {
      width: "100%",
      border: "1px solid var(--color-line)",
      borderRadius: "0.75rem",
      boxShadow: "var(--shadow-overlay)",
    },
    logoBox: { justifyContent: "center", height: "2.5rem" },
    logoImage: { borderRadius: "0.625rem" },
    socialButtonsBlockButton: {
      border: "1px solid var(--color-line-control)",
      backgroundColor: "transparent",
      boxShadow: "none",
      "&:hover": { backgroundColor: "var(--color-hover)" },
    },
    dividerLine: { backgroundColor: "var(--color-line)" },
    formFieldInput: {
      border: "1px solid var(--color-line-control)",
      backgroundColor: "var(--color-field)",
      boxShadow: "none",
      "&:focus": { borderColor: "var(--color-brand)" },
    },
    formButtonPrimary: { width: "100%" },
  },
} as const;
