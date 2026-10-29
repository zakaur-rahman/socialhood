import { Plus } from "lucide-react";
import type { ReactNode } from "react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { FAQ, type FaqItem } from "@/lib/marketing/faq";
import { SECTION_IDS } from "@/lib/marketing/site";

import { SECTION_EYEBROW, SECTION_TITLE } from "./primitives";

/**
 * Common questions (C-155 layout): the heading on the left, native <details> on the right, so
 * keyboard and screen reader support come from the browser with no JavaScript. The text comes from
 * lib/marketing/faq.ts, which the FAQPage JSON-LD reads too, so they always match. The landing page
 * uses the defaults; /for-creators and /for-businesses pass their own questions (C-156).
 */
export function Faq({
  items = FAQ,
  id = SECTION_IDS.faq,
  title = "Common questions",
  lede,
}: {
  items?: readonly FaqItem[];
  id?: string;
  title?: string;
  lede?: ReactNode;
}) {
  return (
    <section className="sec faq-sec" id={id} aria-labelledby={`${id}-title`}>
      <div className="wrap faq">
        <div>
          <p className={SECTION_EYEBROW}>FAQ</p>
          <h2 id={`${id}-title`} className={SECTION_TITLE}>
            {title}
          </h2>
          <p className="lede">
            {lede ?? "Short answers about the AI, the platforms and the plans."} Something missing? Write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
          </p>
        </div>
        <div>
          {items.map((item, index) => (
            <details key={item.question} className="qa" open={index === 0}>
              <summary>
                <h3>{item.question}</h3>
                <span className="pm" aria-hidden>
                  <Plus className="size-3.5" />
                </span>
              </summary>
              <p>{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
