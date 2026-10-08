import { Check, Coins } from "lucide-react";
import type { CSSProperties } from "react";

import { Badge } from "@/components/ui/badge";
import { CREDIT_COSTS, type PlanCard, type Pricing as PricingData } from "@/lib/marketing/plans";
import { SECTION_IDS, SIGN_UP_PATH } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { MovingBorderFrame } from "./effects/moving-border";
import { Container, CtaLink, SectionHeading } from "./primitives";

const count = new Intl.NumberFormat("en-US");

/** Shown in place of a price the API couldn't give: never a price written into the page. */
export const PRICE_AT_SIGN_UP = "See pricing when you sign up";

function PriceLine({ card }: { card: PlanCard }) {
  if (card.plan === "free") {
    return (
      <p className="mt-5">
        <span className="text-4xl font-semibold tracking-tight">Free</span>
        <span className="mt-1 block text-sm text-fg-secondary">No card needed</span>
      </p>
    );
  }
  if (!card.available) {
    return <p className="mt-5 text-2xl font-semibold tracking-tight text-fg-secondary">Coming soon</p>;
  }
  if (card.price) {
    return (
      <p className="mt-5">
        <span className="text-4xl font-semibold tracking-tight tabular-nums">{card.price}</span>
        <span className="text-sm text-fg-secondary"> a month</span>
      </p>
    );
  }
  return <p className="mt-5 text-lg font-semibold text-fg">{PRICE_AT_SIGN_UP}</p>;
}

function PlanCardView({ card, index }: { card: PlanCard; index: number }) {
  const featured = card.plan === "pro" && card.available;
  const body = <PlanCardBody card={card} featured={featured} />;
  return (
    <li data-reveal style={{ "--reveal-delay": `${index * 100}ms` } as CSSProperties} className="relative flex flex-col">
      {featured ? (
        // C-068: Pro's edge carries a moving brand glow (still with reduced motion).
        <MovingBorderFrame className="flex-1 shadow-2xl shadow-brand/15">{body}</MovingBorderFrame>
      ) : (
        <div
          className={cn(
            "flex-1 rounded-2xl border bg-panel transition-colors duration-slow",
            card.available ? "border-line hover:border-line-strong" : "border-dashed border-line bg-panel/50",
          )}
        >
          {body}
        </div>
      )}
    </li>
  );
}

function PlanCardBody({ card, featured }: { card: PlanCard; featured: boolean }) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="flex items-center gap-2">
        <h3 id={`plan-${card.plan}`} className="text-lg font-semibold">
          {card.name}
        </h3>
        {featured && card.trialDays > 0 ? (
          <Badge size="md" tone="brand" className="ml-auto">
            {card.trialDays}-day free trial
          </Badge>
        ) : null}
        {!card.available ? (
          <Badge size="md" className="ml-auto">
            Coming soon
          </Badge>
        ) : null}
      </div>
      <p className="mt-1 text-sm text-fg-secondary">{card.tagline}</p>
      <PriceLine card={card} />
      {featured && card.trialDays > 0 ? (
        <p className="mt-2 text-sm text-fg-secondary">
          Try Pro free for {card.trialDays} days, once per workspace. A card is required to start the trial.
        </p>
      ) : null}

      {card.available ? (
        <>
          <CtaLink
            href={SIGN_UP_PATH}
            prefetch={false}
            variant={featured ? "primary" : "secondary"}
            className="mt-6 w-full"
          >
            {card.plan === "pro" ? "Start free, then try Pro" : "Start free"}
          </CtaLink>
          {card.plan === "pro" ? (
            <p className="mt-2 text-center text-xs text-fg-secondary">Start the trial from Settings → Billing after you sign up.</p>
          ) : null}
          <ul className="mt-6 space-y-2.5 border-t border-line pt-6 text-sm" aria-label={`${card.name} includes`}>
            {card.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2.5">
                <Check className="mt-0.5 size-4 shrink-0 text-brand-fg" aria-hidden />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-6 text-sm leading-relaxed text-fg-secondary">
          A larger plan for teams with multiple members is planned. It isn&apos;t available to buy yet.
        </p>
      )}
    </div>
  );
}

/**
 * Free, Pro and Max from GET /v1/billing/plans (lib/marketing/plans.ts). Prices come only from
 * the API; without one the card says the price is shown at sign-up. Pro's card has the moving
 * border (C-068); Max is "Coming soon".
 */
export function Pricing({ pricing }: { pricing: PricingData }) {
  const { free, pro } = pricing.credits;
  return (
    <section id={SECTION_IDS.pricing} aria-labelledby="pricing-title" className="scroll-mt-24 border-t border-line-subtle py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="pricing-title"
          eyebrow="Pricing"
          title="Start free, upgrade when you grow"
          intro="Pro adds Auto replies, more accounts, more automations and more AI credits. Cancel anytime: Pro stays until the end of the period you've paid for."
        />
        <ul className="mx-auto mt-14 grid max-w-5xl gap-4 lg:grid-cols-3" aria-label="Plans">
          {pricing.plans.map((card, index) => (
            <PlanCardView key={card.plan} card={card} index={index} />
          ))}
        </ul>
        <p className="mx-auto mt-6 max-w-3xl text-center text-xs leading-relaxed text-fg-secondary">
          {pricing.source === "fallback" ? "Prices couldn't be loaded just now; you'll see the current price when you sign up. " : null}
          Payments are handled securely by Dodo Payments. Plans don&apos;t include Meta&apos;s WhatsApp messaging fees,
          which Meta charges directly to your business.
        </p>

        <div data-reveal className="mx-auto mt-12 max-w-5xl rounded-2xl border border-line bg-panel/60 p-6 sm:p-8">
          <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand-fg">
                  <Coins className="size-5" aria-hidden />
                </span>
                <h3 className="text-lg font-semibold">How AI credits work</h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-fg-secondary">
                AI features use credits from your monthly allowance
                {free !== null && pro !== null ? `: ${count.format(free)} on Free and ${count.format(pro)} on Pro` : ""}.
                Credits reset at the start of each billing period, and you&apos;re notified at 80% and 100%.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-fg-secondary">
                When credits run out, AI features pause until the next period or until you upgrade. The inbox, automations
                without AI and publishing keep working.
              </p>
            </div>
            <dl className="grid content-start gap-x-6 text-sm sm:grid-cols-2">
              {CREDIT_COSTS.map((item) => (
                <div key={item.action} className="flex items-baseline justify-between gap-3 border-b border-line-subtle py-2.5">
                  <dt className="text-fg-secondary">{item.action}</dt>
                  <dd className="shrink-0 font-medium tabular-nums">{item.credits}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </Container>
    </section>
  );
}
