import { Plus } from "lucide-react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { FAQ } from "@/lib/marketing/faq";
import { SECTION_IDS } from "@/lib/marketing/site";

import { SECTION_EYEBROW, SECTION_TITLE } from "./primitives";

/**
 * The product guide's common questions (C-155 layout): the heading on the left, native <details>
 * on the right, so keyboard and screen reader support come from the browser with no JavaScript.
 * The text is lib/marketing/faq.ts, which the FAQPage JSON-LD reads too, so they always match.
 */
export function Faq() {
  return (
    <section className="sec faq-sec" id={SECTION_IDS.faq} aria-labelledby="faq-title">
      <div className="wrap faq">
        <div>
          <p className={SECTION_EYEBROW}>FAQ</p>
          <h2 id="faq-title" className={SECTION_TITLE}>
            Common questions
          </h2>
          <p className="lede">
            Short answers about the AI, the platforms and the plans. Something missing? Write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
          </p>
        </div>
        <div>
          {FAQ.map((item, index) => (
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
