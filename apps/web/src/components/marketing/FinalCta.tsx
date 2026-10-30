import { ArrowRight, Check } from "lucide-react";

import { FEATURES_PATH, HOW_IT_WORKS_PATH, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "./primitives";

/**
 * The last call to action, the first half of the page's closing composition (C-161 v2): it shares
 * the night ground with the footer below it, so the two read as one close. A glowing purple dome
 * (pure CSS, decorative) rises behind a centred heading with "every conversation" in the accent, as the
 * hero sets "One inbox.", then the lede, two actions and one row of facts. `trialDays` is Pro's trial
 * when Pro is on sale, so the perk is only claimed when it can be taken (C-149). The second action
 * points to how it works, or to every feature on the how-it-works page itself (`from`).
 */
export function FinalCta({ trialDays = 0, from }: { trialDays?: number; from?: "how-it-works" }) {
  const second = from === "how-it-works" ? { href: FEATURES_PATH, label: "See every feature" } : { href: HOW_IT_WORKS_PATH, label: "See how it works" };
  const perks = [
    "Free plan, no card required",
    ...(trialDays > 0 ? [`Try Pro free for ${trialDays} days`] : []),
    "Official Meta APIs, no password needed",
  ];
  return (
    <section className="night close" aria-labelledby="cta-title">
      <span className="close-arc" aria-hidden />
      <div className="wrap close-in">
        <h2 id="cta-title" className="close-h">
          Ready to take control of <em>every conversation</em>?
        </h2>
        <p className="close-p">
          Connect Instagram, WhatsApp and your website chat, add what your business knows, and let the AI draft or send the replies.
        </p>
        <div className="ctas close-ctas">
          <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
            Start free <ArrowRight className="size-4" aria-hidden />
          </CtaLink>
          <CtaLink href={second.href} variant="secondary">
            {second.label}
          </CtaLink>
        </div>
        <ul className="facts close-facts" aria-label="What you get">
          {perks.map((perk) => (
            <li key={perk}>
              <Check className="size-4" strokeWidth={2.4} aria-hidden />
              {perk}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
