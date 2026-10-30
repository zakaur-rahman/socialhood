import type { Route } from "next";
import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { FAQ, FAQ_PATH, type FaqItem } from "@/lib/marketing/faq";
import { SECTION_IDS } from "@/lib/marketing/site";

import { SECTION_EYEBROW, UTILITY_TITLE } from "./primitives";

/**
 * Common questions (C-155 layout): the heading on the left, native <details> on the right, so
 * keyboard and screen reader support come from the browser with no JavaScript. The text comes from
 * lib/marketing/faq.ts, which the FAQPage JSON-LD reads too, so they always match. The landing page
 * uses the defaults, with no label over the heading and a link to every question on /faq (C-157);
 * /for-creators and /for-businesses pass their own questions and keep their "FAQ" label (C-156).
 */
export function Faq({
  items = FAQ,
  id = SECTION_IDS.faq,
  title = "Common questions",
  lede,
  eyebrow,
  allLink = items === FAQ,
}: {
  items?: readonly FaqItem[];
  id?: string;
  title?: string;
  lede?: ReactNode;
  eyebrow?: string;
  /** A "See all questions" link to /faq under the list. */
  allLink?: boolean;
}) {
  return (
    <section className="sec faq-sec" id={id} aria-labelledby={`${id}-title`}>
      <div className="wrap faq">
        <div className="faq-head">
          {eyebrow ? <p className={SECTION_EYEBROW}>{eyebrow}</p> : null}
          <h2 id={`${id}-title`} className={UTILITY_TITLE}>
            {title}
          </h2>
          <p className="lede">
            {lede ?? "Short answers about the AI, the platforms and the plans."} Something missing? Write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
          </p>
        </div>
        <div className="faq-list">
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
          {allLink ? (
            <p className="faq-all">
              <Link href={FAQ_PATH as Route} className="tlink">
                See all questions
              </Link>{" "}
              <ArrowRight className="inline size-4" aria-hidden />
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
