import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { CHANNELS, MINI_ROWS, SOURCES } from "./landing/data";
import { CtaLink } from "./primitives";

/**
 * The last call to action, on a night band (C-155; C-157: one action, the email as a line of text,
 * and a still inbox with no loop). `trialDays` is Pro's trial when Pro is on sale, so the perk is only
 * claimed when it can be taken (C-149).
 */
export function FinalCta({ trialDays = 0 }: { trialDays?: number }) {
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
          <p className="close-p">
            Connect Instagram, WhatsApp and your website chat, add what your business knows, and let the AI draft the replies.
          </p>
          <div className="ctas">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
          </div>
          <ul className="facts" aria-label="What you get">
            {perks.map((perk) => (
              <li key={perk}>
                <Check className="size-4" strokeWidth={2.4} aria-hidden />
                {perk}
              </li>
            ))}
          </ul>
          <p className="close-mail">
            Questions? Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
          </p>
        </div>
        <div className="mini" data-ui="" aria-hidden>
          <span className="chan-line" aria-hidden>
            {CHANNELS.map((key) => (
              <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
            ))}
          </span>
          <div className="mini-h">
            <b>Inbox</b>
            <span>Today</span>
          </div>
          <ul className="mini-list">
            {MINI_ROWS.map((row) => (
              <li key={row.name} className="mrow2">
                <span className={row.source === "comment" ? "app app-ring" : "app"} style={{ "--c": SOURCES[row.source].colour } as CSSProperties}>
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
