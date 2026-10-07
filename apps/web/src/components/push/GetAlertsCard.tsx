"use client";

import type { Route } from "next";
import Link from "next/link";

import { AlertAction } from "@/components/ui/alert";
import type { NotificationItem } from "@/lib/api/types";
import { usePushOffer } from "@/lib/push/use-push-device";

import { InstallPrompt } from "./InstallPrompt";

/** The notifications that make phone alerts worth offering (F-19): an escalation or a new lead. */
const OFFER_AFTER = new Set(["ai_escalated", "new_lead"]);

export function shouldOfferAlerts(items: NotificationItem[]): boolean {
  return items.some((item) => OFFER_AFTER.has(item.type));
}

/**
 * F-19: after the first escalation or lead notification, the notifications panel offers "Get
 * alerts on your phone": on iPhone the Add to Home Screen steps first, where the browser can
 * install the app its Install button, and everywhere Turn on alerts (Settings → Notifications).
 * Dismissed, it stays dismissed in this browser.
 */
export function GetAlertsCard({
  items,
  slug,
  onNavigate,
}: {
  items: NotificationItem[];
  slug: string;
  onNavigate?: () => void;
}) {
  const offer = usePushOffer();
  if (!offer || !shouldOfferAlerts(items)) return null;
  return (
    <InstallPrompt
      storageKey="socialhood:get-alerts-dismissed"
      title="Get alerts on your phone"
      body="Know as soon as a conversation needs you or a new lead writes, even when Social Hood isn't open."
      always
      className="m-3 mb-1"
      action={
        <AlertAction asChild>
          <Link href={`/w/${slug}/settings/notifications` as Route} onClick={onNavigate}>
            Turn on alerts
          </Link>
        </AlertAction>
      }
    />
  );
}
