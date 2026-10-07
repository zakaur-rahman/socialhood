import Image from "next/image";

import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";

import { Timeline } from "./effects/timeline";
import { Container, CtaLink, SectionHeading } from "./primitives";
import { SHOTS, type Shot } from "./shots";

const STEPS: { title: string; body: string; shot: Shot; maxWidth: string }[] = [
  {
    title: "Connect your accounts",
    body: "Connect your Instagram professional account with Instagram's own login, and your WhatsApp Business number through Meta's official setup. Social Hood never asks for your password.",
    shot: SHOTS.connect,
    maxWidth: "max-w-xl",
  },
  {
    title: "Add your knowledge",
    body: "Prices, products, delivery, returns, timings and FAQs, as text, a link or a file. Test a question to see how the AI would answer before customers ask.",
    shot: SHOTS.knowledge,
    maxWidth: "max-w-md",
  },
  {
    title: "Let the AI draft or reply",
    body: "Start with Suggest and send the drafts you like. On Pro, switch an account to Auto: the AI replies when it's confident and hands everything else to you.",
    shot: SHOTS.aiDraft,
    maxWidth: "max-w-lg",
  },
];

/** The three setup steps on a timeline whose rail fills as they scroll past, each with its real screen. */
export function HowItWorks() {
  return (
    <section
      id={SECTION_IDS.howItWorks}
      aria-labelledby="how-title"
      className="scroll-mt-24 border-t border-line-subtle bg-panel/30 py-20 sm:py-24"
    >
      <Container>
        <SectionHeading id="how-title" eyebrow="How it works" title="Set up in three steps" intro="Screens from the app, with example data." />
        <div className="mx-auto mt-14 max-w-5xl">
          <Timeline
            items={STEPS.map((step) => ({
              title: step.title,
              content: (
                <div data-reveal>
                  <p className="max-w-xl text-base leading-relaxed text-fg-secondary">{step.body}</p>
                  <div className={`mt-6 overflow-hidden rounded-2xl border border-line bg-panel p-1.5 shadow-floating ${step.maxWidth}`}>
                    <Image
                      src={step.shot.src}
                      width={step.shot.width}
                      height={step.shot.height}
                      alt={step.shot.alt}
                      sizes="(min-width: 768px) 36rem, calc(100vw - 6rem)"
                      className="h-auto w-full rounded-xl"
                    />
                  </div>
                </div>
              ),
            }))}
          />
        </div>
        <div className="mt-14 flex justify-center">
          <CtaLink href={SIGN_UP_PATH} prefetch={false}>
            Start free
          </CtaLink>
        </div>
      </Container>
    </section>
  );
}
