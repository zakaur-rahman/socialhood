import { ArrowRight } from "lucide-react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { SIGN_UP_PATH } from "@/lib/marketing/site";

import { LampGlow } from "./effects/lamp";
import { Container, CtaLink } from "./primitives";

/** The last call to action, under the Lamp's light (C-068). The text sits below the glow, on the canvas. */
export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="relative isolate overflow-hidden border-t border-line-subtle bg-canvas">
      <LampGlow />
      <Container className="relative z-10 pt-56 pb-24 text-center sm:pt-60">
        <h2 id="cta-title" className="mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
          Bring every customer conversation into one inbox
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-base text-pretty text-fg-secondary">
          Connect Instagram and WhatsApp, add what your business knows, and let the AI draft the replies.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <CtaLink href={SIGN_UP_PATH} prefetch={false} className="w-full px-6 sm:w-auto">
            Start free <ArrowRight className="size-4" aria-hidden />
          </CtaLink>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-medium text-fg-secondary underline-offset-4 transition-colors duration-150 hover:text-fg hover:underline"
          >
            Questions? {SUPPORT_EMAIL}
          </a>
        </div>
      </Container>
    </section>
  );
}
