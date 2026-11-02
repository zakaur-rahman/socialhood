import { ArrowRight, Check, ChevronDown } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { AGENCY, AGENCY_AI_CREDITS, NEED_MORE, PLAN_NAME, PRICE_TAX_NOTE, formatPrice } from "@/lib/copy";
import { CREDIT_COSTS, type PlanCard, type Pricing as PricingData } from "@/lib/marketing/plans";
import { SECTION_IDS, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";
import { PRO_SIGN_UP_PATH } from "@/lib/resolve";

import { CtaLink, PAGE_HEADING, SECTION_EYEBROW, UTILITY_TITLE } from "./primitives";

const count = new Intl.NumberFormat("en-US");

/** Shown in place of a price the API couldn't give: never a price written into the page. */
export const PRICE_AT_SIGN_UP = "See pricing when you sign up";

/** Free's big number: zero in the currency Creator is sold in, or the word when there is no price to match. */
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
    // C-172: not on sale (billing off, or no product yet): the planned price, labelled as planned.
    return (
      <>
        {card.planned ? (
          // C-173: the number and "a month" on one line, "when we launch" on the line below.
          <p className="price num" data-testid={`planned-price-${card.plan}`}>
            {card.planned.amount}
            <small> a month</small>
          </p>
        ) : (
          <p className="price soon">Coming soon</p>
        )}
        <p className="sub">
          {card.planned ? "Planned price, when we launch. " : ""}
          {card.name} isn&apos;t available to buy yet. Start on Free today and upgrade when it opens.
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
            ? `Try ${card.name} free for ${card.trialDays} days, once per workspace. A card is required to start the trial.`
            : "Cancel anytime."}
        </p>
      </>
    );
  }
  return (
    <>
      <p className="price ask">{PRICE_AT_SIGN_UP}</p>
      <p className="sub">
        {card.trialDays > 0 ? `Try ${card.name} free for ${card.trialDays} days, once per workspace.` : "Cancel anytime."}
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
          {card.plan === "pro" ? "Start free, then try Creator" : "Start free"}
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
 * C-173: Agency is a card, not a plan yet: its price, a "Coming soon" tag and a Contact us link; no
 * plan key, no checkout, no sign-up link. The lines are the same key lines the other cards show.
 */
function AgencyCard() {
  return (
    <li className="plan" aria-labelledby="plan-agency" data-testid="plan-agency">
      <div className="plan-top">
        <h3 id="plan-agency">{AGENCY.name}</h3>
        <span className="tag t-plain">{AGENCY.soon}</span>
      </div>
      <p className="for">{AGENCY.tagline}</p>
      <p className="price num" data-testid="price-agency">
        {AGENCY.price}
        <small> {AGENCY.priceNote}</small>
      </p>
      <p className="sub">{AGENCY.note}</p>
      <CtaLink href={AGENCY.href} prefetch={false} variant="secondary">
        {AGENCY.cta}
      </CtaLink>
      <ul className="limits" aria-label={`${AGENCY.name} includes`}>
        {AGENCY.lines.map((feature) => (
          <li key={feature}>
            <Check className="size-4" strokeWidth={2.4} aria-hidden />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}

/**
 * Free, Creator and Business from GET /v1/billing/plans (lib/marketing/plans.ts), then the Agency
 * card (C-173: coming soon, Contact us), in the site's plan cards (C-155). Prices come only from the API; a
 * paid plan that isn't on sale (billing off, C-149; Business until its product is set) shows its
 * planned price, labelled "when we launch", and says it can't be bought yet. The plan to start on
 * is the outlined one: Creator when it is on sale, Free otherwise.
 */
export function Pricing({ pricing, headingLevel = 2 }: { pricing: PricingData; headingLevel?: 1 | 2 }) {
  const { free, pro, max } = pricing.credits;
  const cards = pricing.plans;
  const proOnSale = pricing.plans.some((card) => card.plan === "pro" && card.available);
  const Heading = headingLevel === 1 ? "h1" : "h2";
  return (
    <section className="sec" id={SECTION_IDS.pricing} aria-labelledby="pricing-title">
      <div className="wrap">
        <div className="split-head">
          <div>
            {headingLevel === 1 ? <p className={SECTION_EYEBROW}>Pricing</p> : null}
            <Heading id="pricing-title" className={headingLevel === 1 ? PAGE_HEADING : UTILITY_TITLE}>
              Start free, upgrade when you grow
            </Heading>
          </div>
          <p className="lede">
            Contacts are unlimited on every plan. Creator adds Auto replies, WhatsApp, more automations and more AI credits.
            Cancel anytime: a paid plan stays until the end of the period you&apos;ve paid for.
          </p>
        </div>
        <ul className="plans" aria-label="Plans" style={{ "--plan-cols": cards.length + 1 } as CSSProperties}>
          {cards.map((card) => (
            <PlanCardView key={card.plan} card={card} pricing={pricing} main={proOnSale ? card.plan === "pro" : card.plan === "free"} />
          ))}
          <AgencyCard />
        </ul>
        <p className="need-more" data-testid="need-more">
          {NEED_MORE.text}{" "}
          <a href={NEED_MORE.href} className="tlink">
            {NEED_MORE.cta}
          </a>
          .
        </p>
        {/* Under the cards, one stack on the cards' edges (C-157 organize): the credits disclosure as wide as
            the plan grid, then the fine print and the link to every limit. */}
        <div className="price-foot">
          <details className="credits">
            <summary>
              <h3>How AI credits work</h3>
              <ChevronDown className="size-4" aria-hidden />
            </summary>
            <p>
              AI features use credits from your monthly allowance
              {free !== null && pro !== null && max !== null
                ? `: ${count.format(free)} on ${PLAN_NAME.free}, ${count.format(pro)} on ${PLAN_NAME.pro}, ${count.format(max)} on ${PLAN_NAME.max} and ${count.format(AGENCY_AI_CREDITS)} on ${AGENCY.name} (coming soon)`
                : ""}.
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
          <div className="price-notes">
            <p>{PRICE_TAX_NOTE}</p>
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
        </div>
      </div>
    </section>
  );
}
