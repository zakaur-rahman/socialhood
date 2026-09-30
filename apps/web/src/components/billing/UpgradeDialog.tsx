"use client";

import Link from "next/link";
import { useState } from "react";

import { BILLING_HREF } from "@/components/shell/nav";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import { useBilling, useBillingPlans, usageMeter } from "@/lib/api/queries";
import type { BillingState, PlanOffer } from "@/lib/api/types";
import { METRIC_FOR_ENTITLEMENT, TRIAL_DAYS, canCheckout, entitlementOf, priceOf } from "@/lib/billing/plan";
import { billingCopy, planOffers, pricePerMonth, upgradeCopy } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

import { useStartCheckout } from "./use-billing-actions";

/** The limit a 402 names: the problem's own, else the plan's value for that key (older 402s). */
function limitFor(request: UpgradeRequest, billing: BillingState | undefined): number | null | undefined {
  if (typeof request.limit === "number") return request.limit;
  const value = request.entitlement ? entitlementOf(billing?.entitlements, request.entitlement) : undefined;
  return typeof value === "number" ? value : request.limit;
}

/** What Pro offers for the same key, for a Free workspace that hit a limit. */
function proOffer(request: UpgradeRequest, pro: PlanOffer | undefined): string | null {
  if (request.code !== "quota_exceeded" || !request.entitlement || !pro) return null;
  const value = entitlementOf(pro.entitlements, request.entitlement);
  if (value === null) return planOffers(request.entitlement, null, "pro");
  return typeof value === "number" ? planOffers(request.entitlement, value, "pro") : null;
}

/**
 * F-15, T8.4: the upgrade dialog every 402 opens (lib/api/provider.tsx). It names the limit with
 * copy per entitlement (§4.7, C-049), shows the Pro price from GET …/billing, and offers "Start
 * 7-day trial" when eligible, else "Upgrade to Pro", straight to checkout. Only the owner can
 * pay (§2.15): admins get the billing page, agents are told to ask an owner.
 */
export function UpgradeDialog() {
  const { request, close } = useUpgradeDialog();
  const workspace = useCurrentWorkspace();
  const open = request !== null;
  // The last request stays on screen while the dialog closes.
  const [shown, setShown] = useState<UpgradeRequest | null>(request);
  if (request && request !== shown) setShown(request);

  const billing = useBilling(workspace.id, open);
  const plans = useBillingPlans(open);
  const checkout = useStartCheckout(workspace.id);

  if (!shown) return null;

  const state = billing.data;
  const isOwner = workspace.role === "owner";
  const mayPay = isOwner && canCheckout(state);
  const credits = usageMeter(state, METRIC_FOR_ENTITLEMENT.ai_credits_monthly);
  const copy = upgradeCopy(
    { ...shown, limit: limitFor(shown, state) },
    { plan: state?.plan ?? null, resetsOn: credits?.period_end ?? null },
  );
  const pro = plans.data?.items.find((item) => item.plan === "pro");
  const offer = canCheckout(state) ? proOffer(shown, pro) : null;
  const price = priceOf("pro", state, plans.data?.items);
  const perMonth = price ? pricePerMonth(price) : null;
  const trialDays = pro?.trial_days || TRIAL_DAYS;
  const trial = Boolean(state?.trial_eligible);
  const pitch = mayPay ? (trial ? billingCopy.trialOffer(trialDays, perMonth) : perMonth ? billingCopy.proPrice(perMonth) : null) : null;
  const roleNote = isOwner ? null : workspace.role === "admin" ? billingCopy.ownerOnly : billingCopy.askOwner;

  const onOpenChange = (next: boolean) => {
    if (next) return;
    checkout.clearError();
    close();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-line bg-panel sm:max-w-md" data-testid="upgrade-dialog">
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription className="text-fg-secondary">{copy.body}</DialogDescription>
        </DialogHeader>
        {offer || pitch || roleNote ? (
          <div className="space-y-1.5 text-sm">
            {offer ? <p className="font-medium text-fg">{offer}</p> : null}
            {pitch ? <p className="text-fg-secondary">{pitch}</p> : null}
            {roleNote ? <p className="text-fg-secondary">{roleNote}</p> : null}
          </div>
        ) : null}
        {checkout.error ? (
          <p role="alert" className="text-sm text-danger-fg">
            {checkout.error}
          </p>
        ) : null}
        <DialogFooter className="border-line bg-transparent">
          <Button variant="ghost" className="min-h-10 md:min-h-8" onClick={() => onOpenChange(false)}>
            Not now
          </Button>
          {mayPay ? (
            <>
              <Button asChild variant="secondary" className="min-h-10 md:min-h-8">
                <Link href={BILLING_HREF(workspace.slug)} onClick={() => onOpenChange(false)}>
                  Compare plans
                </Link>
              </Button>
              <Button
                className="bg-brand-gradient min-h-10 text-white md:min-h-8"
                disabled={checkout.pending || billing.isPending}
                onClick={() => checkout.start("pro")}
              >
                {checkout.pending ? "Opening checkout…" : trial ? billingCopy.trialCta(trialDays) : billingCopy.upgradeCta}
              </Button>
            </>
          ) : workspace.role !== "agent" ? (
            <Button asChild className="bg-brand-gradient min-h-10 text-white md:min-h-8">
              <Link href={BILLING_HREF(workspace.slug)} onClick={() => onOpenChange(false)}>
                {isOwner ? "View billing" : "See plans"}
              </Link>
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
