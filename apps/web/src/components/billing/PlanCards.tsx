"use client";

import { Check, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { BillingState, PlanOffer } from "@/lib/api/types";
import { TRIAL_DAYS, canCheckout, planHighlights } from "@/lib/billing/plan";
import { PLAN_NAME, billingCopy, formatPrice } from "@/lib/copy";
import { cn } from "@/lib/utils";

const TAGLINE: Record<PlanOffer["plan"], string> = {
  free: "To get started",
  pro: "For a growing business",
  max: "For teams and high volume",
};

/**
 * UX-SCR-07: the plans side by side, from the public GET /v1/billing/plans (C-049). The current
 * plan is marked; the owner of a Free workspace can start the trial or upgrade from Pro's card.
 * Max is shown as coming (R2). C-066: three columns from tablets up, the current plan highlighted.
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
  checkout: { start: (plan: "pro" | "max") => void; pending: boolean };
}) {
  if (plans.isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-3" aria-busy="true" aria-label="Loading plans">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-3 rounded-2xl border border-line bg-panel p-5">
            <Skeleton className="h-4 w-16 bg-raised motion-reduce:animate-none" />
            <Skeleton className="h-6 w-24 bg-raised motion-reduce:animate-none" />
            <Skeleton className="h-3 w-3/4 bg-raised motion-reduce:animate-none" />
          </div>
        ))}
      </div>
    );
  }
  if (plans.isError || !plans.data) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-5 text-sm">
        <p className="flex-1 text-fg-secondary">The plans couldn&apos;t load.</p>
        <Button variant="secondary" className="min-h-10 md:min-h-8" onClick={() => void plans.refetch()}>
          <RotateCw aria-hidden /> Try again
        </Button>
      </div>
    );
  }

  const current = billing.plan;
  const mayPay = isOwner && canCheckout(billing);
  return (
    <ul className="grid gap-4 md:grid-cols-3" aria-label="Plans">
      {plans.data.items.map((offer) => {
        const isCurrent = offer.plan === current;
        const highlights = planHighlights(offer.entitlements);
        const trialDays = offer.trial_days || TRIAL_DAYS;
        return (
          <li
            key={offer.plan}
            aria-current={isCurrent ? "true" : undefined}
            className={cn(
              "relative flex flex-col rounded-2xl border bg-panel p-5 md:p-6",
              isCurrent ? "border-brand ring-1 ring-brand-line shadow-lg shadow-brand/10" : "border-line",
              !offer.available && !isCurrent && "opacity-80",
            )}
          >
            {isCurrent ? (
              <span aria-hidden className="bg-brand-gradient absolute inset-x-6 -top-px h-0.5 rounded-full" />
            ) : null}
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">{PLAN_NAME[offer.plan]}</h3>
              {isCurrent ? (
                <span className="rounded-full bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-fg">Current plan</span>
              ) : !offer.available ? (
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs font-medium text-fg-secondary">Coming soon</span>
              ) : null}
            </div>
            <p className="text-xs text-fg-secondary">{TAGLINE[offer.plan]}</p>
            <p className="mt-4 text-3xl font-semibold tracking-tight tabular-nums">
              {offer.plan === "free" ? (
                "Free"
              ) : offer.price ? (
                <>
                  {formatPrice(offer.price)}
                  <span className="text-sm font-normal text-fg-secondary"> a month</span>
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
            {mayPay && offer.plan === "pro" && offer.available ? (
              <Button
                className="bg-brand-gradient mt-5 min-h-10 w-full text-white md:min-h-9"
                disabled={checkout.pending}
                onClick={() => checkout.start("pro")}
              >
                {checkout.pending
                  ? "Opening checkout…"
                  : billing.trial_eligible && offer.trial_days > 0
                    ? billingCopy.trialCta(trialDays)
                    : billingCopy.upgradeCta}
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
