import { ArrowRight, Check, ChevronDown } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { formatPrice } from "@/lib/copy";
import { CREDIT_COSTS, type PlanCard, type Pricing as PricingData } from "@/lib/marketing/plans";
import { SECTION_IDS, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";
import { PRO_SIGN_UP_PATH } from "@/lib/resolve";

import { CtaLink, SECTION_EYEBROW, SECTION_TITLE } from "./primitives";

const count = new Intl.NumberFormat("en-US");

/** Shown in place of a price the API couldn't give: never a price written into the page. */
export const PRICE_AT_SIGN_UP = "See pricing when you sign up";

/** Free's big number: zero in the currency Pro is sold in, or the word when there is no price to match. */
function freePrice(pricing: PricingData): string {
  const currency = pricing.plans.find((card) => card.plan === "pro")?.offer?.currency;
  return currency ? formatPrice({ amount_minor: 0, currency }) : "Free";
}

function PriceLine({ card, pricing }: { card: PlanCard; pricing: PricingData }) {
  if (card.plan === "free") {
    return (
      <>
        <p className="price num">{freePrice(pricing)}</p>
        <p className="sub">No card needed</p>
      </>
    );
  }
  if (!card.available) {
    return (
      <>
        <p className="price soon">Coming soon</p>
        <p className="sub">
          {card.plan === "pro"
            ? "Pro isn't available to buy yet. Start on Free today and upgrade when it opens."
            : "A larger plan for teams with multiple members is planned. It isn't available to buy yet."}
        </p>
      </>
    );
  }
  if (card.price) {
    return (
      <>
        <p className="price num">
          {card.price}
          <small> a month</small>
        </p>
        <p className="sub">
          {card.trialDays > 0
            ? `Try Pro free for ${card.trialDays} days, once per workspace. A card is required to start the trial.`
            : "Cancel anytime."}
        </p>
      </>
    );
  }
  return (
    <>
      <p className="price ask">{PRICE_AT_SIGN_UP}</p>
      <p className="sub">
        {card.trialDays > 0 ? `Try Pro free for ${card.trialDays} days, once per workspace.` : "Cancel anytime."}
      </p>
    </>
  );
}

function PlanCardView({ card, pricing, main }: { card: PlanCard; pricing: PricingData; main: boolean }) {
  return (
    <li className={main ? "plan main" : "plan"} aria-labelledby={`plan-${card.plan}`}>
      <div className="plan-top">
        <h3 id={`plan-${card.plan}`}>{card.name}</h3>
        {!card.available ? (
          <span className="tag t-plain">Coming soon</span>
        ) : card.plan === "free" ? (
          <span className="tag t-ok">Available now</span>
        ) : card.trialDays > 0 ? (
          <span className="tag t-draft">{card.trialDays}-day free trial</span>
        ) : null}
      </div>
      <p className="for">{card.tagline}</p>
      <PriceLine card={card} pricing={pricing} />
      {card.available ? (
        <CtaLink
          href={appUrl(card.plan === "pro" ? PRO_SIGN_UP_PATH : SIGN_UP_PATH)}
          prefetch={false}
          variant={main ? "primary" : "secondary"}
        >
          {card.plan === "pro" ? "Start free, then try Pro" : "Start free"}
        </CtaLink>
      ) : null}
      {card.features.length ? (
        <ul className="limits" aria-label={`${card.name} includes`}>
          {card.features.map((feature) => (
            <li key={feature}>
              <Check className="size-4" strokeWidth={2.4} aria-hidden />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/**
 * Free, Pro and Max from GET /v1/billing/plans (lib/marketing/plans.ts), in the site's plan cards
 * (C-155). Prices come only from the API; without one the card says the price is shown at sign-up.
 * A plan that can't be bought yet (Pro while billing is off, C-149; Max until R2) says "Coming
 * soon": Pro still lists what it includes, Max is a line under the cards. The plan to start on is
 * the outlined one: Pro when it is on sale, Free otherwise.
 */
export function Pricing({ pricing, headingLevel = 2 }: { pricing: PricingData; headingLevel?: 1 | 2 }) {
  const { free, pro } = pricing.credits;
  const cards = pricing.plans.filter((card) => card.plan !== "max" || card.available);
  const max = pricing.plans.find((card) => card.plan === "max" && !card.available);
  const proOnSale = pricing.plans.some((card) => card.plan === "pro" && card.available);
  const Heading = headingLevel === 1 ? "h1" : "h2";
  return (
    <section className="sec" id={SECTION_IDS.pricing} aria-labelledby="pricing-title">
      <div className="wrap">
        <div className="split-head">
          <div>
            <p className={SECTION_EYEBROW}>Pricing</p>
            <Heading id="pricing-title" className={SECTION_TITLE}>
              Start free, upgrade when you grow
            </Heading>
          </div>
          <p className="lede">
            Pro adds Auto replies, more accounts, more automations and more AI credits. Cancel anytime: Pro stays until the end
            of the period you&apos;ve paid for.
          </p>
        </div>
        <ul className="plans" aria-label="Plans" style={{ "--plan-cols": cards.length } as CSSProperties}>
          {cards.map((card) => (
            <PlanCardView key={card.plan} card={card} pricing={pricing} main={proOnSale ? card.plan === "pro" : card.plan === "free"} />
          ))}
        </ul>
        <div className="price-foot">
          <div>
            {max ? (
              <p>
                <b>{max.name}:</b> a larger plan for teams with multiple members is planned. It isn&apos;t available to buy yet.
              </p>
            ) : null}
            <p>
              Payments are handled securely by Dodo Payments. Plans don&apos;t include Meta&apos;s WhatsApp messaging fees, which Meta
              charges directly to your business.
            </p>
            {headingLevel === 2 ? (
              <p>
                <Link href="/pricing" className="tlink">
                  Compare every plan limit
                </Link>{" "}
                <ArrowRight className="inline size-4" aria-hidden />
              </p>
            ) : null}
          </div>
          <details className="credits">
            <summary>
              <h3>How AI credits work</h3>
              <ChevronDown className="size-4" aria-hidden />
            </summary>
            <p>
              AI features use credits from your monthly allowance
              {free !== null && pro !== null ? `: ${count.format(free)} on Free and ${count.format(pro)} on Pro` : ""}.
              Credits reset at the start of each billing period, and you&apos;re notified at 80% and 100%.
            </p>
            <p>
              When credits run out, AI features pause until the next period or until you upgrade. The inbox, automations without
              AI and publishing keep working.
            </p>
            <dl>
              {CREDIT_COSTS.map((item) => (
                <div key={item.action} className="cr">
                  <dt>{item.action}</dt>
                  <dd className="num">{item.credits}</dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      </div>
    </section>
  );
}
