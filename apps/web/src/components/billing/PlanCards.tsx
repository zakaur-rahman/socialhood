"use client";

import { KPI, SECTION_TITLE } from "@/styles/tokens";
import { Check, RotateCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { BillingState, PlanOffer } from "@/lib/api/types";
import { TRIAL_DAYS, canStartCheckout, planHighlights, sixMonthOffer } from "@/lib/billing/plan";
import { AGENCY, PLAN_NAME, billingCopy, formatPrice, plannedAmount, type BillingPeriod, type PaidPlan } from "@/lib/copy";
import { cn } from "@/lib/utils";

const TAGLINE: Record<PlanOffer["plan"], string> = {
  free: "To get started",
  pro: "For creators and small businesses",
  max: "For growing businesses with a team",
  agency: "For agencies and people managing several brands",
};

/**
 * UX-SCR-07: the plans side by side, from the public GET /v1/billing/plans (C-049). The current
 * plan is marked; the owner of a Free workspace can start the trial or upgrade from a plan's card.
 * C-174: a Monthly / 6 months switch. A plan with nothing to show for six months keeps its monthly
 * price and button, and Agency is "Coming soon" with a Contact us link until its product is set.
 * C-066: columns from tablets up, the current plan highlighted.
 */
export function PlanCards({
  plans,
  billing,
  isOwner,
  checkout,
}: {
  plans: { data?: { items: PlanOffer[] }; isPending: boolean; isError: boolean; refetch: () => unknown };
  billing: BillingState;
  isOwner: boolean;
  checkout: { start: (plan: PaidPlan, period?: BillingPeriod) => void; pending: boolean };
}) {
  const [period, setPeriod] = useState<BillingPeriod>("month");
  if (plans.isPending) {
    return (
      <div role="status" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-busy="true" aria-label="Loading plans">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} padding="roomy" className="space-y-3">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-3 w-3/4" />
          </Card>
        ))}
      </div>
    );
  }
  if (plans.isError || !plans.data) {
    return (
      <Card role="alert" padding="roomy" className="flex flex-wrap items-center gap-3 text-sm">
        <p className="flex-1 text-fg-secondary">The plans couldn&apos;t load.</p>
        <Button variant="secondary" onClick={() => void plans.refetch()}>
          <RotateCw aria-hidden /> Try again
        </Button>
      </Card>
    );
  }

  const current = billing.plan;
  const mayPay = isOwner && canStartCheckout(billing);
  return (
    <div className="space-y-4">
      {/* Only once something six-month can really be bought; a switch that changes nothing just confuses. */}
      {plans.data.items.some((offer) => sixMonthOffer(offer)?.planned === false) ? (
        <ToggleGroup
          aria-label="Billing period"
          className="sm:w-64"
          value={period}
          onValueChange={(value) => value && setPeriod(value as BillingPeriod)}
        >
          <ToggleGroupItem value="month">Monthly</ToggleGroupItem>
          <ToggleGroupItem value="six_month">6 months</ToggleGroupItem>
        </ToggleGroup>
      ) : null}
      <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Plans">
        {plans.data.items.map((offer) => {
          const isCurrent = offer.plan === current;
          const highlights = planHighlights(offer.entitlements);
          const trialDays = offer.trial_days || TRIAL_DAYS;
          const six = period === "six_month" ? sixMonthOffer(offer) : null;
          return (
            <Card
              asChild
              key={offer.plan}
              padding="roomy"
              tone={isCurrent ? "brand" : "default"}
              // A plan that isn't available yet dims its edge and fill, never its text (UI-ISS-007).
              // The current plan is marked by its brand edge alone: no ring, no glow (UI-ISS-094).
              className={cn("relative flex flex-col", !isCurrent && !offer.available && "border-line-subtle bg-panel-glass")}
              data-testid={`plan-${offer.plan}`}
            >
              <li aria-current={isCurrent ? "true" : undefined}>
                {isCurrent ? (
                  // A 2 px mark: solid, not a gradient (DESIGN_SYSTEM §1.9, marks under 12 px).
                  <span aria-hidden className="absolute inset-x-6 -top-px h-0.5 rounded-full bg-brand" />
                ) : null}
                <div className="flex items-center justify-between gap-2">
                  <h3 className={SECTION_TITLE}>{PLAN_NAME[offer.plan]}</h3>
                  {isCurrent ? (
                    <Badge tone="brand" size="md">
                      Current plan
                    </Badge>
                  ) : !offer.available ? (
                    <Badge size="md">Coming soon</Badge>
                  ) : null}
                </div>
                <p className="text-xs text-fg-secondary">{TAGLINE[offer.plan]}</p>
                <p className={cn("mt-4", KPI)}>
                  {offer.plan === "free" ? (
                    "Free"
                  ) : six ? (
                    <>
                      <span data-testid={`six-month-price-${offer.plan}`}>{six.total}</span>
                      <span className="text-sm font-normal text-fg-secondary"> every 6 months</span>
                      <span className="block text-sm font-normal text-fg-secondary">
                        {six.note}
                        {six.planned ? " when we launch" : ""}
                      </span>
                    </>
                  ) : offer.price ? (
                    <>
                      {formatPrice(offer.price)}
                      <span className="text-sm font-normal text-fg-secondary"> a month</span>
                    </>
                  ) : !offer.available ? (
                    // C-149, C-172: not on sale (no billing on this server yet, or a plan without its
                    // product): the planned price, labelled as planned.
                    <>
                      <span data-testid={`planned-price-${offer.plan}`}>{plannedAmount(offer.plan)}</span>
                      <span className="text-sm font-normal text-fg-secondary"> a month</span>
                      <span className="block text-sm font-normal text-fg-secondary">when we launch</span>
                    </>
                  ) : (
                    <span className="text-base font-normal text-fg-secondary">Price shown at checkout</span>
                  )}
                </p>
                <ul className="mt-5 flex-1 space-y-2 border-t border-line-subtle pt-5 text-sm">
                  {highlights.map((line) => (
                    <li key={line} className="flex items-start gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-brand-fg" aria-hidden />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
                {mayPay && offer.plan !== "free" && offer.available ? (
                  // D-10: the page header's card holds the one primary; a card here is secondary.
                  <Button
                    variant="secondary"
                    size="lg"
                    className="mt-5 w-full"
                    loading={checkout.pending}
                    onClick={() => checkout.start(offer.plan as PaidPlan, six ? "six_month" : "month")}
                  >
                    {!six && billing.trial_eligible && offer.trial_days > 0
                      ? billingCopy.trialCta(trialDays)
                      : `Upgrade to ${PLAN_NAME[offer.plan]}`}
                  </Button>
                ) : offer.plan === "agency" && !offer.available && !isCurrent ? (
                  <Button asChild variant="secondary" size="lg" className="mt-5 w-full">
                    <a href={AGENCY.href}>{AGENCY.cta}</a>
                  </Button>
                ) : null}
              </li>
            </Card>
          );
        })}
      </ul>
    </div>
  );
}
