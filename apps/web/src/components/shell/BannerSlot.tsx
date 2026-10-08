"use client";

import { X } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";

import { Button } from "@/components/ui/button";
import type { BillingState, Role } from "@/lib/api/types";
import { billingDate, daysUntil, priceOf } from "@/lib/billing/plan";
import { paymentFailedBanner, pricePerMonth, trialEndingBanner } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/ui/tone";
import { cn } from "@/lib/utils";

export type BannerAction =
  | { label: string; href: Route; onClick?: never; pending?: never }
  | { label: string; onClick: () => void; pending?: boolean; href?: never };

export type Banner = {
  id: string;
  tone: "warning" | "danger";
  message: string;
  action?: BannerAction;
  /** Only non-critical banners can be dismissed (UX-SH-04). */
  onDismiss?: () => void;
};

/**
 * UX-SH-04: app-level banners above page content (account needs reconnecting, payment on hold,
 * AI credits exhausted, trial ending). One action each, a `secondary` `sm` Button (DESIGN_SYSTEM
 * §8.5: banner actions); critical states cannot be dismissed. They sit in `<main>`'s flow and keep
 * their height; a full-height frame below takes the rest.
 */
export function BannerSlot({ banners }: { banners: Banner[] }) {
  if (banners.length === 0) return null;
  return (
    <div className="shrink-0 space-y-2 px-4 pt-4 md:px-6" role="status">
      {banners.map((banner) => (
        <div
          key={banner.id}
          data-banner={banner.id}
          className={cn(
            "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg px-4 py-2.5 text-sm",
            TONE_CLASS[banner.tone],
          )}
        >
          <p className="min-w-0 flex-1 basis-60">{banner.message}</p>
          {banner.action?.href ? (
            <Button asChild variant="secondary" size="sm">
              <Link href={banner.action.href}>{banner.action.label}</Link>
            </Button>
          ) : banner.action ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={banner.action.onClick}
              disabled={banner.action.pending}
              aria-busy={banner.action.pending || undefined}
            >
              {banner.action.label}
            </Button>
          ) : null}
          {banner.onDismiss ? (
            <Button variant="ghost" size="icon-sm" aria-label="Dismiss" onClick={banner.onDismiss} className="-mr-2">
              <X aria-hidden />
            </Button>
          ) : null}
        </div>
      ))}
    </div>
  );
}

/** A trial ending within this many days gets the reminder. */
export const TRIAL_REMINDER_DAYS = 3;

/**
 * FR-BIL-06, F-15: while Dodo holds the subscription, the owner sees "Payment failed. Update your
 * payment method by {grace_until} to keep Pro" on every page with Manage billing (the portal); it
 * can't be dismissed. In the trial's last days the owner gets a dismissible reminder of when it
 * ends and what follows. Admins and agents can't change billing (§2.15), so they see neither.
 */
export function billingBanners(
  billing: BillingState | undefined,
  options: {
    role: Role;
    timeZone: string;
    billingHref: Route;
    onManageBilling: () => void;
    managing?: boolean;
    /** Trial reminders already dismissed, by trial end. */
    dismissedTrial?: string | null;
    onDismissTrial?: (trialEndsAt: string) => void;
    now?: Date;
  },
): Banner[] {
  if (!billing || options.role !== "owner") return [];
  const now = options.now ?? new Date();
  if (billing.status === "on_hold") {
    const grace = billing.grace_until ? billingDate(billing.grace_until, options.timeZone, now) : null;
    return [
      {
        id: "payment-failed",
        tone: "danger",
        message: paymentFailedBanner(grace),
        action: { label: "Manage billing", onClick: options.onManageBilling, pending: options.managing },
      },
    ];
  }
  if (billing.status === "trialing" && billing.trial_ends_at) {
    const ends = billing.trial_ends_at;
    const days = daysUntil(ends, now);
    if (days > TRIAL_REMINDER_DAYS || new Date(ends) <= now || options.dismissedTrial === ends) return [];
    const price = priceOf(billing.plan, billing);
    return [
      {
        id: "trial-ending",
        tone: "warning",
        message: trialEndingBanner(
          days,
          billingDate(ends, options.timeZone, now),
          !billing.cancel_at_period_end,
          price ? pricePerMonth(price) : null,
        ),
        action: { label: billing.cancel_at_period_end ? "Keep Pro" : "View billing", href: options.billingHref },
        onDismiss: options.onDismissTrial ? () => options.onDismissTrial?.(ends) : undefined,
      },
    ];
  }
  return [];
}
