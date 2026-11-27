"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { keys, useChangePlan, usePlanChangePreview } from "@/lib/api/queries";
import type { BillingState } from "@/lib/api/types";
import { billingDate } from "@/lib/billing/plan";
import { PLAN_NAME, billingCopy, errorMessage, formatPrice, type BillingPeriod, type PaidPlan } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

export type PlanSwitch = { plan: PaidPlan; period: BillingPeriod; price: string | null };

const RANK: Record<BillingState["plan"], number> = { free: 0, pro: 1, max: 2, agency: 3 };

/**
 * C-209: switch a paid plan to another plan or period. Opening it asks Dodo what the change costs
 * now (the difference for the rest of the period, or credit on a downgrade); nothing is charged
 * until the owner confirms. The plan itself changes when Dodo's webhook arrives.
 */
export function ChangePlanDialog({
  billing,
  target,
  onClose,
}: {
  billing: BillingState;
  target: PlanSwitch | null;
  onClose: () => void;
}) {
  const workspace = useCurrentWorkspace();
  const queryClient = useQueryClient();
  const preview = usePlanChangePreview(workspace.id);
  const change = useChangePlan(workspace.id);
  const { mutate: runPreview, reset: resetPreview } = preview;

  useEffect(() => {
    if (target) runPreview({ plan: target.plan, period: target.period });
    else resetPreview();
  }, [target, runPreview, resetPreview]);

  if (!target) return null;
  const name = PLAN_NAME[target.plan];
  const sixMonths = target.period === "six_month";
  const quote = preview.data;
  const due = quote && quote.amount_due_minor > 0 ? formatPrice({ amount_minor: quote.amount_due_minor, currency: quote.currency }) : null;
  const credit = quote && quote.credit_minor > 0 ? formatPrice({ amount_minor: quote.credit_minor, currency: quote.currency }) : null;
  const renews = quote?.next_billing_date ? billingDate(quote.next_billing_date, workspace.timezone) : null;
  const downgrade = RANK[target.plan] < RANK[billing.plan];

  const confirm = () =>
    change.mutate(
      { plan: target.plan, period: target.period },
      {
        onSuccess: () => {
          toast.success(billingCopy.switchStarted(name));
          void queryClient.invalidateQueries({ queryKey: keys.billing(workspace.id) });
          onClose();
        },
        onError: (failure) => toastError(failure),
      },
    );

  return (
    <AlertDialog open onOpenChange={(open) => (open || change.isPending ? undefined : onClose())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{billingCopy.switchTitle(name, sixMonths)}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2" aria-live="polite">
              {preview.isPending ? (
                <span role="status" aria-label="Getting the price" className="block space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </span>
              ) : preview.isError ? (
                <p role="alert">{errorMessage(preview.error) || billingCopy.switchPreviewFailed}</p>
              ) : quote ? (
                <>
                  <p>{due ? billingCopy.switchDueNow(due) : billingCopy.switchNothingDue}</p>
                  {credit ? <p>{billingCopy.switchCredit(credit)}</p> : null}
                  {target.price && renews ? <p>{billingCopy.switchRenews(target.price, renews)}</p> : null}
                  {downgrade ? <p>{billingCopy.switchDowngrade(name)}</p> : null}
                </>
              ) : null}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={change.isPending}>{billingCopy.switchKeep(PLAN_NAME[billing.plan])}</AlertDialogCancel>
          <Button onClick={confirm} loading={change.isPending} disabled={!quote}>
            {due ? billingCopy.switchPay(due) : billingCopy.switchConfirm(name)}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
