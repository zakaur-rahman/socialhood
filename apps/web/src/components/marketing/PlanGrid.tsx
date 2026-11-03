"use client";

import { Check } from "lucide-react";
import { useState, type CSSProperties } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { AGENCY, formatPrice } from "@/lib/copy";
import type { PlanCard, Pricing as PricingData } from "@/lib/marketing/plans";
import { SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";
import { PRO_SIGN_UP_PATH } from "@/lib/resolve";

import { CtaLink } from "./primitives";

/** Shown in place of a price the API couldn't give: never a price written into the page. */
export const PRICE_AT_SIGN_UP = "See pricing when you sign up";

type Period = "month" | "six_month";

/** Free's big number: zero in the currency Creator is sold in, or the word when there is no price to match. */
function freePrice(pricing: PricingData): string {
  const currency = pricing.plans.find((card) => card.plan === "pro")?.offer?.currency;
  return currency ? formatPrice({ amount_minor: 0, currency }) : "Free";
}

function PriceLine({ card, pricing, six }: { card: PlanCard; pricing: PricingData; six: boolean }) {
  if (card.plan === "free") {
    return (
      <>
        <p className="price num">{freePrice(pricing)}</p>
        <p className="sub">No card needed</p>
      </>
    );
  }
  if (six && card.sixMonth) {
    const { total, note, planned } = card.sixMonth;
    return (
      <>
        <p className="price num" data-testid={`six-month-price-${card.plan}`}>
          {total}
          <small> every 6 months</small>
        </p>
        <p className="sub">
          {note}. {planned ? (card.plan === "agency" ? AGENCY.note : "Planned price, when we launch.") : "Cancel anytime."}
        </p>
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
          {card.plan === "agency" ? (
            AGENCY.note
          ) : (
            <>
              {card.planned ? "Planned price, when we launch. " : ""}
              {card.name} isn&apos;t available to buy yet. Start on Free today and upgrade when it opens.
            </>
          )}
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

function PlanCardView({ card, pricing, main, six }: { card: PlanCard; pricing: PricingData; main: boolean; six: boolean }) {
  const showingSix = six && card.sixMonth !== null;
  return (
    <li className={main ? "plan main" : "plan"} aria-labelledby={`plan-${card.plan}`} data-testid={`plan-${card.plan}`}>
      <div className="plan-top">
        <h3 id={`plan-${card.plan}`}>{card.name}</h3>
        {!card.available ? (
          <span className="tag t-plain">Coming soon</span>
        ) : card.plan === "free" ? (
          <span className="tag t-ok">Available now</span>
        ) : card.trialDays > 0 && !showingSix ? (
          <span className="tag t-draft">{card.trialDays}-day free trial</span>
        ) : null}
      </div>
      <p className="for">{card.tagline}</p>
      <PriceLine card={card} pricing={pricing} six={six} />
      {card.available ? (
        <CtaLink
          href={appUrl(card.plan === "pro" && !showingSix ? PRO_SIGN_UP_PATH : SIGN_UP_PATH)}
          prefetch={false}
          variant={main ? "primary" : "secondary"}
        >
          {card.plan === "pro" && !showingSix ? "Start free, then try Creator" : "Start free"}
        </CtaLink>
      ) : card.plan === "agency" ? (
        <CtaLink href={AGENCY.href} prefetch={false} variant="secondary">
          {AGENCY.cta}
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
 * The plan cards (C-155) under a Monthly / 6 months switch (C-174). A plan with nothing to show for six
 * months keeps its monthly price and button; with no such plan at all there is no switch. The plan to
 * start on is the outlined one: Creator when it is on sale, Free otherwise.
 */
export function PlanGrid({ pricing }: { pricing: PricingData }) {
  const [period, setPeriod] = useState<Period>("month");
  const cards = pricing.plans;
  const proOnSale = cards.some((card) => card.plan === "pro" && card.available);
  return (
    <>
      {cards.some((card) => card.sixMonth) ? (
        <ToggleGroup
          aria-label="Billing period"
          className="plan-period w-full sm:w-64"
          value={period}
          onValueChange={(value) => value && setPeriod(value as Period)}
        >
          <ToggleGroupItem value="month">Monthly</ToggleGroupItem>
          <ToggleGroupItem value="six_month">6 months</ToggleGroupItem>
        </ToggleGroup>
      ) : null}
      <ul className="plans" aria-label="Plans" style={{ "--plan-cols": cards.length } as CSSProperties}>
        {cards.map((card) => (
          <PlanCardView
            key={card.plan}
            card={card}
            pricing={pricing}
            main={proOnSale ? card.plan === "pro" : card.plan === "free"}
            six={period === "six_month"}
          />
        ))}
      </ul>
    </>
  );
}
