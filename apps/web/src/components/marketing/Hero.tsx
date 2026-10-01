import { ArrowRight, BadgeCheck, Languages, Sparkles } from "lucide-react";
import Image from "next/image";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";

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

/**
 * The first screen: what Social Hood is, the two ways in, and the real product. The text is
 * server-rendered and still (it is the page's largest paint); one background effect (Spotlight);
 * the screenshot tilts up into place as it scrolls in.
 */
export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative -mt-16 overflow-hidden pt-16">
      <Spotlight />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[40rem] bg-[radial-gradient(50%_55%_at_50%_0%,var(--color-brand-soft),transparent_70%)]"
      />
      <Container className="relative pt-14 pb-10 sm:pt-20 lg:pt-24">
        <div className="mx-auto max-w-5xl text-center">
          <p className="inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-line bg-panel/70 px-3 py-1.5 text-xs text-fg-secondary">
            <span className="flex items-center gap-1">
              <span className="grid size-5 place-items-center rounded-full bg-instagram">
                <PlatformGlyph platform="instagram" className="size-3 text-white" />
              </span>
              <span className="grid size-5 place-items-center rounded-full bg-whatsapp">
                <PlatformGlyph platform="whatsapp" className="size-3 text-white" />
              </span>
            </span>
            <span>
              Inbox, AI replies and automations<span className="hidden sm:inline"> for Instagram and WhatsApp</span>
            </span>
          </p>
          <h1 id="hero-title" className="mt-6 text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
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
            Every Instagram DM, comment and WhatsApp chat in one place. Social Hood drafts or sends replies from your own
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

        <figure className="mx-auto mt-14 max-w-5xl sm:mt-16">
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
            The Social Hood inbox with example data. The shop, people and messages are made up.
          </figcaption>
        </figure>
      </Container>
    </section>
  );
}
