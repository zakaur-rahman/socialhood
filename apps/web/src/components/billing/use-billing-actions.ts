"use client";

import { useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/errors";
import { useCheckout, usePortal } from "@/lib/api/queries";
import { browser } from "@/lib/billing/browser";
import { billingCopy, errorMessage } from "@/lib/copy";

/** C-049: 409 when a paid plan exists, 422 for Max until R2, 503 when Dodo isn't there. */
export function checkoutErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return billingCopy.checkoutConflict;
    if (error.status === 422) return billingCopy.maxUnavailable;
    if (error.status === 503) return billingCopy.paymentsUnavailable;
    if (error.status === 403) return billingCopy.ownerOnly;
  }
  return errorMessage(error);
}

export function portalErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return billingCopy.noBillingAccount;
    if (error.status === 503) return billingCopy.paymentsUnavailable;
    if (error.status === 403) return billingCopy.ownerOnly;
  }
  return errorMessage(error);
}

/**
 * F-15 Checkout: POST …/billing/checkout, then the browser goes to Dodo. The button stays busy
 * while the page unloads. Nothing changes here on success: the webhook changes the plan.
 */
export function useStartCheckout(wid: string) {
  const checkout = useCheckout(wid);
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const start = (plan: "pro" | "max" = "pro") => {
    setError(null);
    checkout.mutate(plan, {
      onSuccess: (session) => {
        setLeaving(true);
        browser.assign(session.checkout_url);
      },
      onError: (failure) => setError(checkoutErrorMessage(failure)),
    });
  };
  return { start, pending: checkout.isPending || leaving, error, clearError: () => setError(null) };
}

/** FR-BIL-04 Manage billing: Dodo's customer portal in a new tab. */
export function useOpenPortal(wid: string) {
  const portal = usePortal(wid);
  const open = () => {
    const tab = browser.openPending();
    portal.mutate(undefined, {
      onSuccess: (session) => tab.go(session.portal_url),
      onError: (failure) => {
        tab.cancel();
        toast.error(portalErrorMessage(failure));
      },
    });
  };
  return { open, pending: portal.isPending };
}
