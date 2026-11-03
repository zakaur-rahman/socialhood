import { ArrowRight, ChevronDown } from "lucide-react";
import Link from "next/link";

import { NEED_MORE, PLAN_NAME, PRICE_TAX_NOTE } from "@/lib/copy";
import { CREDIT_COSTS, type Pricing as PricingData } from "@/lib/marketing/plans";
import { SECTION_IDS } from "@/lib/marketing/site";

import { PlanGrid } from "./PlanGrid";
import { PAGE_HEADING, SECTION_EYEBROW, UTILITY_TITLE } from "./primitives";

const count = new Intl.NumberFormat("en-US");

/**
 * Free, Creator, Business and Agency from GET /v1/billing/plans (lib/marketing/plans.ts), in the site's
 * plan cards (PlanGrid). Prices come only from the API; a paid plan that isn't on sale (billing off,
 * C-149; a plan until its product is set) shows its planned price, labelled as planned, and says it
 * can't be bought yet.
 */
export function Pricing({ pricing, headingLevel = 2 }: { pricing: PricingData; headingLevel?: 1 | 2 }) {
  const { free, pro, max, agency } = pricing.credits;
  const agencyOnSale = pricing.plans.some((card) => card.plan === "agency" && card.available);
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
        <PlanGrid pricing={pricing} />
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
              {free !== null && pro !== null && max !== null && agency !== null
                ? `: ${count.format(free)} on ${PLAN_NAME.free}, ${count.format(pro)} on ${PLAN_NAME.pro}, ${count.format(max)} on ${PLAN_NAME.max} and ${count.format(agency)} on ${PLAN_NAME.agency}${agencyOnSale ? "" : " (coming soon)"}`
                : ""}.
              Credits reset every month, including on plans paid every 6 months, and you&apos;re notified at 80% and 100%.
            </p>
            <p>
              When credits run out, AI features pause until they reset or until you upgrade. The inbox, automations without
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
