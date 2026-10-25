import { ChevronDown } from "lucide-react";

import { FAQ } from "@/lib/marketing/faq";
import { cn } from "@/lib/utils";
import { SECTION_IDS } from "@/lib/marketing/site";

import { Container, MARKETING_CARD_GLASS, SectionHeading } from "./primitives";

/**
 * The product guide's common questions as an accordion. Native <details>: keyboard and screen
 * reader support come from the browser, with no JavaScript.
 */
export function Faq() {
  return (
    <section id={SECTION_IDS.faq} aria-labelledby="faq-title" className="scroll-mt-24 border-t border-line-subtle py-20 sm:py-24">
      <Container>
        <SectionHeading id="faq-title" eyebrow="FAQ" title="Common questions" />
        <div data-reveal className={cn(MARKETING_CARD_GLASS, "mx-auto mt-12 max-w-3xl divide-y divide-line overflow-hidden")}>
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
