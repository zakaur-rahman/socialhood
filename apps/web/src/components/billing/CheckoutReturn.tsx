"use client";

import { CircleCheck, Clock, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { BillingState } from "@/lib/api/types";
import { canCheckout } from "@/lib/billing/plan";
import { PLAN_NAME, billingCopy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** F-15: the return page polls GET …/billing every 3 s for up to 60 s. */
export const CONFIRM_POLL_MS = 3_000;
export const CONFIRM_TIMEOUT_MS = 60_000;

export type ConfirmPhase = "waiting" | "confirmed" | "slow";

/** A paid plan is what the webhook grants; the return URL alone changes nothing (FR-BIL-02). */
export function isConfirmed(billing: BillingState | undefined): boolean {
  return Boolean(billing) && !canCheckout(billing);
}

/**
 * Waiting for Dodo's signed webhook after checkout (F-15): confirmed once GET …/billing shows a
 * paid plan (usage.updated refetches it; the page also polls), slow after 60 s.
 */
export function useCheckoutConfirmation(active: boolean, billing: BillingState | undefined): ConfirmPhase | null {
  const [timedOut, setTimedOut] = useState(false);
  const confirmed = isConfirmed(billing);
  useEffect(() => {
    if (!active || confirmed) return;
    const timer = window.setTimeout(() => setTimedOut(true), CONFIRM_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [active, confirmed]);
  if (!active) return null;
  if (confirmed) return "confirmed";
  return timedOut ? "slow" : "waiting";
}

/** The notice at the top of the billing page after Dodo sends the browser back. */
export function CheckoutReturn({
  phase,
  billing,
  onDone,
}: {
  phase: ConfirmPhase;
  billing: BillingState | undefined;
  onDone: () => void;
}) {
  const trial = billing?.status === "trialing";
  const title =
    phase === "waiting"
      ? billingCopy.confirming
      : phase === "confirmed"
        ? trial
          ? billingCopy.confirmedTrial
          : billingCopy.confirmed(PLAN_NAME[billing?.plan ?? "pro"])
        : billingCopy.slow;
  const body = phase === "waiting" ? billingCopy.confirmingBody : phase === "confirmed" ? billingCopy.confirmedBody : null;
  const Icon = phase === "waiting" ? LoaderCircle : phase === "confirmed" ? CircleCheck : Clock;
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "mb-6 flex flex-wrap items-start gap-3 rounded-xl border p-4",
        phase === "confirmed" ? "border-success/40 bg-success/10" : "border-brand-line bg-brand-soft",
      )}
    >
      <Icon
        className={cn(
          "mt-0.5 size-5 shrink-0",
          phase === "waiting" && "motion-safe:animate-spin",
          phase === "confirmed" ? "text-success" : "text-brand-fg",
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1 basis-60">
        <p className="text-sm font-semibold">{title}</p>
        {body ? <p className="text-sm text-fg-secondary">{body}</p> : null}
      </div>
      {phase === "waiting" ? null : (
        <Button variant="ghost" className="min-h-10 md:min-h-8" onClick={onDone}>
          Done
        </Button>
      )}
    </div>
  );
}
