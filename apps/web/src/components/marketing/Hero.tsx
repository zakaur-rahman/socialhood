import { ArrowRight, BadgeCheck, Languages, Sparkles } from "lucide-react";

import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { DISPLAY } from "@/styles/tokens";

import { Container, CtaLink } from "./primitives";
import { RoutingDiagram } from "./RoutingDiagram";

/** The headline (the page's one h1); the auth pages show it too. */
export const HERO_TITLE = "Every DM. Every comment. One inbox.";
export const HERO_LINE =
  "AI that knows your business drafts or sends the reply on Instagram, WhatsApp and your website, and hands the tricky ones to you.";

const TRUST = [
  { icon: BadgeCheck, text: "Official Meta APIs" },
  { icon: Languages, text: "English, Hindi and Hinglish" },
  { icon: Sparkles, text: "Free plan, no card needed" },
];

/**
 * The first screen (C-141): a short headline, the two ways in, and the routing diagram, every
 * channel into one hub and the right outcome out. Laid out like a bordered centre column with
 * hatched side columns that fade out, a hairline, then the diagram. All of it is server-rendered;
 * only the diagram's pulses move. The product shot follows in its own section (ProductShot).
 */
export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative -mt-16 overflow-hidden pt-16">
      {/* The hero's glow (C-068): a soft brand light from the top centre. */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[40rem] bg-glow-brand-top" />

      <div className="relative">
        {/* The side columns outside the text column: fine hairlines fading out downwards. */}
        <div aria-hidden className="pointer-events-none absolute inset-0 mx-auto hidden max-w-5xl lg:block">
          <div className="hatch-lines absolute inset-y-0 right-full w-screen" />
          <div className="hatch-lines absolute inset-y-0 left-full w-screen" />
        </div>
        <div className="relative mx-auto max-w-5xl lg:border-x lg:border-line-subtle">
          <Container className="pt-14 pb-12 text-center sm:pt-20 sm:pb-14 lg:pt-24 lg:pb-16">
            <h1 id="hero-title" className={cn(DISPLAY, "mx-auto max-w-3xl text-balance")}>
              Every DM. Every comment. <span className="text-brand-fg">One inbox.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-pretty text-fg-secondary sm:text-lg">{HERO_LINE}</p>
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
          </Container>
        </div>
      </div>

      {/* The hairline between the words and the picture. */}
      <div aria-hidden className="border-t border-line-subtle" />

      <Container className="pt-10 pb-14 sm:pt-12 lg:pt-14 lg:pb-20">
        <RoutingDiagram />
      </Container>
    </section>
  );
}
