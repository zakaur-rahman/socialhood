import { ArrowRight, BadgeCheck, Languages, Sparkles } from "lucide-react";
import Image from "next/image";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import type { Platform } from "@/lib/api/types";
import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { DISPLAY } from "@/styles/tokens";

import { ContainerScroll } from "./effects/container-scroll-animation";
import { FlipWords } from "./effects/flip-words";
import { Spotlight } from "./effects/spotlight-new";
import { Container, CtaLink } from "./primitives";
import { SHOTS } from "./shots";

/** The words the headline cycles through; the heading's accessible name lists them all. */
export const HERO_WORDS = ["DMs", "comments", "leads"];
export const HERO_TITLE = "Reply to DMs, comments and leads with AI that knows your business";

const TRUST = [
  { icon: BadgeCheck, text: "Official Meta APIs" },
  { icon: Languages, text: "English, Hindi and Hinglish" },
  { icon: Sparkles, text: "Free plan, no card needed" },
];

/** The "Works with" strip: the platform marks we ship, and plain names for the rest (no third-party logos). */
const WORKS_WITH: { name: string; platform?: Platform; tile?: string; soon?: boolean }[] = [
  { name: "Instagram", platform: "instagram", tile: "bg-instagram-logo-gradient" },
  { name: "WhatsApp", platform: "whatsapp", tile: "bg-whatsapp-logo" },
  { name: "Facebook", platform: "facebook", tile: "bg-facebook-logo", soon: true },
  { name: "Website chat", platform: "web", tile: "bg-web" },
  { name: "Shopify", soon: true },
  { name: "Razorpay" },
  { name: "Google Sheets" },
  { name: "Zapier" },
];

/**
 * The first screen: what Amplychat is, the two ways in, and the real product. The text is
 * server-rendered and still (it is the page's largest paint); one background effect (Spotlight);
 * the screenshot tilts up into place as it scrolls in.
 */
export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative -mt-16 overflow-hidden pt-16">
      <Spotlight />
      {/* The hero's own glow (C-068), not `bg-glow-brand`: a soft brand light from the top centre,
          behind the centred headline and the Spotlight's beams. `bg-glow-brand` rises from a corner
          (120% × 140% at 0 0), a shape made for a card such as Billing's plan hero; here it would
          light one side of a centred layout. Both are brand-soft fading out, from the tokens. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[40rem] bg-glow-brand-top"
      />
      <Container className="relative pt-14 pb-10 sm:pt-20 lg:pt-24">
        <div className="mx-auto max-w-5xl text-center">
          <p className="inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-line bg-panel-glass px-3 py-1.5 text-xs text-fg-secondary">
            <span className="flex items-center gap-1">
              <span className="grid size-5 place-items-center rounded-full bg-instagram-logo-gradient">
                <PlatformGlyph platform="instagram" className="size-3 text-on-brand" />
              </span>
              <span className="grid size-5 place-items-center rounded-full bg-whatsapp-logo">
                <PlatformGlyph platform="whatsapp" className="size-3 text-on-brand" />
              </span>
            </span>
            <span>
              Inbox, AI replies and automations<span className="hidden sm:inline"> for Instagram and WhatsApp</span>
            </span>
          </p>
          <h1 id="hero-title" className={cn(DISPLAY, "mt-6 text-balance")}>
            <span className="sr-only">{HERO_TITLE}</span>
            <span aria-hidden>
              <span className="block">
                Reply to{" "}
                {/* On phones the word takes its own line, centred; wider, it follows "Reply to". */}
                <FlipWords words={HERO_WORDS} className="text-brand-fg max-sm:grid max-sm:justify-items-center" />
              </span>
              <span className="block text-balance">with AI that knows your business</span>
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-pretty text-fg-secondary sm:text-lg">
            Every Instagram DM, comment and WhatsApp chat in one place. Amplychat drafts or sends replies from your own
            business knowledge, and runs comment and DM automations.
          </p>
          <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <CtaLink href={SIGN_UP_PATH} prefetch={false} className="px-6">
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={`#${SECTION_IDS.howItWorks}`} variant="secondary" className="px-6">
              See how it works
            </CtaLink>
          </div>
          <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-fg-secondary" aria-label="At a glance">
            {TRUST.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-1.5">
                <Icon className="size-3.5 text-brand-fg" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>

        <figure className="relative mx-auto mt-14 max-w-5xl sm:mt-16">
          <div aria-hidden className="pointer-events-none absolute -inset-x-6 -top-10 -bottom-6 -z-10 rounded-3xl bg-glow-brand-top blur-2xl" />
          <ContainerScroll>
            <Image
              src={SHOTS.inbox.src}
              width={SHOTS.inbox.width}
              height={SHOTS.inbox.height}
              alt={SHOTS.inbox.alt}
              sizes="(min-width: 1072px) 1008px, calc(100vw - 2.5rem)"
              // On phones the screenshot is the largest paint: fetch it at once, first.
              loading="eager"
              fetchPriority="high"
              className="h-auto w-full"
            />
          </ContainerScroll>
          <figcaption className="mt-4 text-center text-xs text-fg-secondary">
            The Amplychat inbox with example data. The shop, people and messages are made up.
          </figcaption>
        </figure>

        <div className="mx-auto mt-12 max-w-4xl text-center sm:mt-14">
          <p className="text-xs font-medium tracking-wide text-fg-secondary uppercase">Works with</p>
          <ul aria-label="Works with" className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-3">
            {WORKS_WITH.map((item) => (
              <li key={item.name} className="flex items-center gap-2 text-sm font-medium text-fg-secondary">
                {item.platform ? (
                  <span aria-hidden className={cn("grid size-6 place-items-center rounded-md", item.tile)}>
                    <PlatformGlyph platform={item.platform} className="size-3.5 text-on-brand" />
                  </span>
                ) : null}
                {item.name}
                {item.soon ? <span className="rounded-full bg-hover px-1.5 py-0.5 text-2xs font-normal">soon</span> : null}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-fg-secondary">
            <a href={`#${SECTION_IDS.integrations}`} className="underline underline-offset-4 hover:text-fg">
              What runs today, and what is coming
            </a>
          </p>
        </div>
      </Container>
    </section>
  );
}
