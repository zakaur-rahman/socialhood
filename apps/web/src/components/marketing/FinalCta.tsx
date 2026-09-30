import { ArrowRight } from "lucide-react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { SIGN_UP_PATH } from "@/lib/marketing/site";

import { Container, CtaLink } from "./primitives";

export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="border-t border-line-subtle py-20 sm:py-24">
      <Container>
        <div className="bg-shell-gradient relative overflow-hidden rounded-3xl px-6 py-14 text-center sm:px-12">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_80%_at_50%_0%,var(--color-line-strong),transparent_70%)]"
          />
          <h2 id="cta-title" className="relative mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-balance text-white sm:text-4xl">
            Bring every customer conversation into one inbox
          </h2>
          <p className="relative mx-auto mt-4 max-w-xl text-base text-pretty text-white/80">
            Connect Instagram and WhatsApp, add what your business knows, and let the AI draft the replies.
          </p>
          <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <CtaLink
              href={SIGN_UP_PATH}
              prefetch={false}
              variant="secondary"
              className="w-full border-transparent bg-white px-6 text-brand-deep hover:bg-white/90 sm:w-auto"
            >
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-medium text-white/90 underline-offset-4 hover:underline"
            >
              Questions? {SUPPORT_EMAIL}
            </a>
          </div>
        </div>
      </Container>
    </section>
  );
}
