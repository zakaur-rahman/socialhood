import { ChevronDown } from "lucide-react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { FAQ } from "@/lib/marketing/faq";
import { cn } from "@/lib/utils";
import { SECTION_IDS } from "@/lib/marketing/site";

import { MARKETING_HEADING } from "@/styles/tokens";

import { Container, MARKETING_CARD_GLASS, SECTION_EYEBROW } from "./primitives";

/**
 * The product guide's common questions as an accordion. Native <details>: keyboard and screen
 * reader support come from the browser, with no JavaScript.
 */
export function Faq() {
  return (
    <section id={SECTION_IDS.faq} aria-labelledby="faq-title" className="scroll-mt-24 border-t border-line-subtle py-16 sm:py-20">
      <Container className="grid gap-10 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-14">
        <div className="text-center lg:sticky lg:top-28 lg:self-start lg:text-left">
          <p className={SECTION_EYEBROW}>FAQ</p>
          <h2 id="faq-title" className={cn(MARKETING_HEADING, "mt-3 text-balance")}>
            Common questions
          </h2>
          <p className="mt-4 text-base leading-relaxed text-pretty text-fg-secondary">
            Short answers about the AI, the platforms and the plans. Something missing? Write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-fg underline underline-offset-4">
              {SUPPORT_EMAIL}
            </a>
            .
          </p>
        </div>
        <div data-reveal className={cn(MARKETING_CARD_GLASS, "divide-y divide-line overflow-hidden")}>
          {FAQ.map((item) => (
            <div key={item.question}>
            <h3 className="sr-only">{item.question}</h3>
            <details className="group">
              <summary className="flex min-h-14 cursor-pointer list-none items-center gap-4 px-5 py-3 text-left text-base font-medium transition-colors duration-normal hover:bg-hover focus-visible:-outline-offset-2 [&::-webkit-details-marker]:hidden">
                <span className="flex-1 text-base font-medium">{item.question}</span>
                <ChevronDown
                  className="size-5 shrink-0 text-fg-secondary transition-transform duration-normal group-open:rotate-180 motion-reduce:transition-none"
                  aria-hidden
                />
              </summary>
              <p className="px-5 pb-5 text-sm leading-relaxed text-fg-secondary">{item.answer}</p>
            </details>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
