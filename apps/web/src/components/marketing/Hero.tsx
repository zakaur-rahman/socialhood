import { ArrowRight } from "lucide-react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";

import { InboxPreview } from "./InboxPreview";
import { Container, CtaLink } from "./primitives";

/** The first screen: what Social Hood is, for whom, and the two ways in. */
export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-40 h-[36rem] bg-[radial-gradient(50%_60%_at_50%_30%,var(--color-brand-soft),transparent_70%)]"
      />
      <Container className="relative pt-14 pb-16 sm:pt-20 lg:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-line bg-panel/70 px-3 py-1.5 text-xs text-fg-secondary">
            <span className="flex items-center gap-1">
              <span className="grid size-5 place-items-center rounded-full bg-instagram">
                <PlatformGlyph platform="instagram" className="size-3 text-white" />
              </span>
              <span className="grid size-5 place-items-center rounded-full bg-whatsapp">
                <PlatformGlyph platform="whatsapp" className="size-3 text-white" />
              </span>
            </span>
            Inbox, AI replies and automations
          </p>
          <h1
            id="hero-title"
            className="mt-6 text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl"
          >
            The AI inbox for businesses that sell on Instagram and WhatsApp
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-pretty text-fg-secondary sm:text-lg">
            Every DM, comment and WhatsApp chat in one place. Social Hood drafts or sends replies from your own business
            knowledge, runs comment and DM automations, and answers in English, Hindi and Hinglish.
          </p>
          <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <CtaLink href={SIGN_UP_PATH} prefetch={false} className="px-6">
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={`#${SECTION_IDS.howItWorks}`} variant="secondary" className="px-6">
              See how it works
            </CtaLink>
          </div>
          <p className="mt-4 text-xs text-fg-secondary">Free plan, no card needed.</p>
        </div>
        <div className="mx-auto mt-14 max-w-5xl sm:mt-16">
          <InboxPreview />
        </div>
      </Container>
    </section>
  );
}
