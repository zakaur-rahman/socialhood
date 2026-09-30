import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";

import { Container, CtaLink, SectionHeading } from "./primitives";

const STEPS = [
  {
    title: "Connect your accounts",
    body: "Connect your Instagram professional account with Instagram's own login, and your WhatsApp Business number through Meta's official setup. Social Hood never asks for your password.",
  },
  {
    title: "Add your knowledge",
    body: "Prices, products, delivery, returns, timings and FAQs, as text, a link or a file. Test a question to see how the AI would answer before customers ask.",
  },
  {
    title: "Let the AI draft or reply",
    body: "Start with Suggest and send the drafts you like. On Pro, switch an account to Auto: the AI replies when it's confident and hands everything else to you.",
  },
];

export function HowItWorks() {
  return (
    <section
      id={SECTION_IDS.howItWorks}
      aria-labelledby="how-title"
      className="scroll-mt-20 border-t border-line-subtle bg-panel/40 py-20 sm:py-24"
    >
      <Container>
        <SectionHeading id="how-title" eyebrow="How it works" title="Set up in three steps" />
        <ol className="mt-14 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative rounded-2xl border border-line bg-canvas p-6">
              <span
                aria-hidden
                className="bg-brand-gradient grid size-9 place-items-center rounded-full text-sm font-semibold text-white tabular-nums"
              >
                {index + 1}
              </span>
              <h3 className="mt-4 text-base font-semibold">
                <span className="sr-only">Step {index + 1}: </span>
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{step.body}</p>
            </li>
          ))}
        </ol>
        <div className="mt-10 flex justify-center">
          <CtaLink href={SIGN_UP_PATH} prefetch={false}>
            Start free
          </CtaLink>
        </div>
      </Container>
    </section>
  );
}
