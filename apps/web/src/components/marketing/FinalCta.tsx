import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { SECTION_IDS, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { MINI_ROWS, SOURCES } from "./landing/data";
import { CtaLink } from "./primitives";

/**
 * The last call to action, on a night band (C-155), with a small inbox where a few example messages
 * land (CSS only; still with reduced motion). `trialDays` is Pro's trial when Pro is on sale, so the
 * perk is only claimed when it can be taken (C-149).
 */
export function FinalCta({ trialDays = 0, pricingHref = `#${SECTION_IDS.pricing}` }: { trialDays?: number; pricingHref?: string }) {
  const perks = [
    "Free plan, no card needed",
    ...(trialDays > 0 ? [`${trialDays}-day trial of Pro`] : []),
    "Official Meta APIs, no password asked",
  ];
  return (
    <section className="night close" aria-labelledby="cta-title">
      <div className="wrap close-grid">
        <div>
          <h2 id="cta-title">Bring every customer conversation into one inbox</h2>
          <p className="close-p">Connect Instagram and WhatsApp, add what your business knows, and let the AI draft the replies.</p>
          <div className="ctas">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={pricingHref} variant="secondary">
              See pricing
            </CtaLink>
            <a href={`mailto:${SUPPORT_EMAIL}`} className="btn btn-ghost">
              Questions? {SUPPORT_EMAIL}
            </a>
          </div>
          <ul className="facts" aria-label="What you get">
            {perks.map((perk) => (
              <li key={perk}>
                <Check className="size-4" strokeWidth={2.4} aria-hidden />
                {perk}
              </li>
            ))}
          </ul>
        </div>
        <div className="mini" aria-hidden>
          <div className="mini-h">
            <b>Inbox</b>
            <span>Today</span>
          </div>
          <ul className="mini-list">
            {MINI_ROWS.map((row) => (
              <li key={row.name} className={row.falling ? "mrow2 falling" : "mrow2"}>
                <span className="app" style={{ "--c": SOURCES[row.source].colour } as CSSProperties}>
                  <i />
                </span>
                <span className="grow">
                  <b>{row.name}</b> {row.text}
                </span>
                <span className={`tag t-${row.tone}`}>{row.tag}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
