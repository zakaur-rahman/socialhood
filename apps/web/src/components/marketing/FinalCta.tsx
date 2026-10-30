import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "./primitives";

/** The three live channels, in the order the site names them: the closing's channel line. */
const CHANNEL_COLOURS = ["var(--ig)", "var(--wa)", "var(--web)"] as const;

/**
 * The last call to action, the first half of the page's closing composition (C-161): it shares the
 * night ground with the footer below it, so the two read as one close. The channel line (the site's
 * motif: Instagram, WhatsApp and website chat) opens it, then the heading at the display size on the
 * page's left edge, and a row with the lede on the left and the one action, the facts and the email
 * on the right. `trialDays` is Pro's trial when Pro is on sale, so the perk is only claimed when it
 * can be taken (C-149).
 */
export function FinalCta({ trialDays = 0 }: { trialDays?: number }) {
  const perks = [
    "Free plan, no card needed",
    ...(trialDays > 0 ? [`${trialDays}-day trial of Pro`] : []),
    "Official Meta APIs, no password asked",
  ];
  return (
    <section className="night close" aria-labelledby="cta-title">
      <div className="wrap close-in">
        <span className="chan-line close-line" aria-hidden>
          {CHANNEL_COLOURS.map((colour) => (
            <i key={colour} style={{ "--c": colour } as CSSProperties} />
          ))}
        </span>
        <h2 id="cta-title" className="close-h">
          Bring every customer conversation into one inbox
        </h2>
        <div className="close-row">
          <p className="close-p">
            Connect Instagram, WhatsApp and your website chat, add what your business knows, and let the AI draft the replies.
          </p>
          <div className="close-act">
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
        </div>
      </div>
    </section>
  );
}
