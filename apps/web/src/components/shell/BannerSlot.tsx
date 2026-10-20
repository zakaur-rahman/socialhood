"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";

import { Alert, AlertAction } from "@/components/ui/alert";
import type { BillingState, Role } from "@/lib/api/types";
import { billingDate, daysUntil, priceOf } from "@/lib/billing/plan";
import { paymentFailedBanner, pricePerMonth, trialEndingBanner } from "@/lib/copy";

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
 * AI credits exhausted, trial ending), drawn with Alert (DESIGN_SYSTEM §8.2): one action each, danger
 * banners announced at once, critical states cannot be dismissed. They sit in `<main>`'s flow and keep
 * their height; a full-height frame below takes the rest.
 */
export function BannerSlot({ banners }: { banners: Banner[] }) {
  if (banners.length === 0) return null;
  return (
    <div className="shrink-0 space-y-2 px-4 pt-4 md:px-6">
      {banners.map((banner) => (
        // The Alert is the live region: `alert` for danger (payment on hold), `status` otherwise.
        <Alert
          key={banner.id}
          data-banner={banner.id}
          tone={banner.tone}
          icon={<TriangleAlert />}
          onDismiss={banner.onDismiss}
          action={
            banner.action?.href ? (
              <AlertAction asChild>
                <Link href={banner.action.href}>{banner.action.label}</Link>
              </AlertAction>
            ) : banner.action ? (
              <AlertAction onClick={banner.action.onClick} loading={banner.action.pending}>
                {banner.action.label}
              </AlertAction>
            ) : undefined
          }
        >
          {banner.message}
        </Alert>
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
