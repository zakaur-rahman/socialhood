/**
 * The billing state as the UI reads it (F-15, UX-SCR-07, FR-BIL-02…06). GET …/billing is the only
 * source (TR-BIL-04); these functions only phrase it. Nothing here grants a plan: that arrives
 * from Dodo's signed webhook as usage.updated (C-049).
 */
import type { BillingPrice, BillingState, EntitlementValue, PlanOffer, UsageMeter } from "@/lib/api/types";
import { PLAN_NAME, billingCopy, pricePerMonth, shortDate, type PlanName } from "@/lib/copy";
import { dayKey } from "@/lib/tz";

const DAY_MS = 86_400_000;

/** FR-BIL-03: the Pro trial's length until the plan list says otherwise. */
export const TRIAL_DAYS = 7;

/** A timestamp as a date in the workspace timezone: "3 Oct", or "3 Oct 2027" in another year. */
export function billingDate(iso: string, timeZone: string, now: Date = new Date()): string {
  return shortDate(dayKey(iso, timeZone), now);
}

/** Whole days left until an instant, rounded up (a trial ending in 30 hours has 2 days left). */
export function daysUntil(iso: string, now: Date = new Date()): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now.getTime()) / DAY_MS));
}

/** The paid plan's price, from GET …/billing (F-15) or the public plan list. */
export function priceOf(
  plan: PlanName,
  billing: BillingState | undefined,
  plans?: PlanOffer[] | undefined,
): BillingPrice | null {
  return (
    billing?.prices.find((price) => price.plan === plan) ??
    plans?.find((offer) => offer.plan === plan)?.price ??
    null
  );
}

export function entitlementOf(entitlements: EntitlementValue[] | undefined, key: string): EntitlementValue["value"] | undefined {
  return entitlements?.find((item) => item.key === key)?.value;
}

/** Whether the workspace can start a checkout: it has no paid plan (409 otherwise, C-049). */
export function canCheckout(billing: BillingState | undefined): boolean {
  return !billing || billing.plan === "free" || billing.status === "free" || billing.status === "expired";
}

export type StatusTone = "neutral" | "brand" | "warning" | "danger";

export type PlanStatus = {
  plan: string;
  badge: { label: string; tone: StatusTone };
  /** One line under the plan name: renewal, trial end, grace end or when Pro stops. */
  line: string;
  /** Resume is offered (a cancellation is pending, FR-BIL-04). */
  resumable: boolean;
  /** Cancel is offered (a paid plan that renews). */
  cancellable: boolean;
};

/**
 * UX-SCR-07's plan card: name, status and the date that matters. Trial with days left, active
 * with its renewal, on hold with its grace end (FR-BIL-06), or "Pro until {date}" when cancelled.
 */
export function planStatus(billing: BillingState, timeZone: string, now: Date = new Date()): PlanStatus {
  const name = PLAN_NAME[billing.plan];
  const date = (iso: string | null | undefined) => (iso ? billingDate(iso, timeZone, now) : null);
  const price = priceOf(billing.plan, billing);
  const perMonth = price ? pricePerMonth(price) : null;

  switch (billing.status) {
    case "trialing": {
      const ends = date(billing.trial_ends_at ?? billing.current_period_end);
      const days = billing.trial_ends_at ? daysUntil(billing.trial_ends_at, now) : null;
      const left = days === null ? "" : days <= 1 ? " · last day" : ` · ${days} days left`;
      if (billing.cancel_at_period_end) {
        return {
          plan: name,
          badge: { label: "Trial", tone: "brand" },
          line: ends ? `Trial ends on ${ends}${left}. It won't renew.` : "Your trial won't renew.",
          resumable: true,
          cancellable: false,
        };
      }
      return {
        plan: name,
        badge: { label: "Trial", tone: "brand" },
        line: ends
          ? `Trial ends on ${ends}${left}.${perMonth ? ` Then ${perMonth}.` : ""}`
          : `Free trial${perMonth ? `, then ${perMonth}` : ""}.`,
        resumable: false,
        cancellable: true,
      };
    }
    case "active": {
      const ends = date(billing.current_period_end);
      if (billing.cancel_at_period_end) {
        return {
          plan: name,
          badge: { label: "Cancelled", tone: "warning" },
          line: ends
            ? `${billingCopy.cancelled(name, ends)}. Then the workspace moves to Free.`
            : `${name} ends at the end of this period.`,
          resumable: true,
          cancellable: false,
        };
      }
      return {
        plan: name,
        badge: { label: "Active", tone: "brand" },
        line: [ends ? `Renews on ${ends}` : null, perMonth].filter(Boolean).join(" · ") || "Active",
        resumable: false,
        cancellable: true,
      };
    }
    case "on_hold": {
      const grace = date(billing.grace_until);
      return {
        plan: name,
        badge: { label: "Payment failed", tone: "danger" },
        line: grace
          ? `Update your payment method by ${grace} to keep ${name}.`
          : `Update your payment method to keep ${name}.`,
        resumable: false,
        cancellable: false,
      };
    }
    case "expired":
      return {
        plan: PLAN_NAME.free,
        badge: { label: "Free", tone: "neutral" },
        line: "Your paid plan ended, so the workspace is on Free. Nothing was deleted.",
        resumable: false,
        cancellable: false,
      };
    case "free":
    default:
      return {
        plan: name,
        badge: { label: "Free", tone: "neutral" },
        line: "Upgrade for more accounts, automations, scheduled posts and AI credits.",
        resumable: false,
        cancellable: false,
      };
  }
}

// ---- usage meters (UX-SCR-07, FR-BIL-05)

const METERS: Record<string, { label: string; unit: string; periodic?: boolean }> = {
  ai_credits: { label: "AI credits", unit: "credits", periodic: true },
  scheduled_posts: { label: "Scheduled posts", unit: "posts", periodic: true },
  knowledge_characters: { label: "Knowledge", unit: "characters" },
  active_automations: { label: "Active automations", unit: "automations" },
  pending_scheduled_messages: { label: "Scheduled messages", unit: "waiting" },
  social_accounts: { label: "Connected accounts", unit: "accounts" },
  accounts_per_platform: { label: "Accounts per platform", unit: "accounts" },
  members: { label: "Members", unit: "members" },
};

function humanize(metric: string): string {
  const words = metric.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export type MeterView = {
  metric: string;
  label: string;
  unit: string;
  used: number;
  limit: number | null;
  /** "Resets on 1 Oct" for a monthly allowance. */
  note: string | null;
};

/** Every usage entry with a limit, in the API's order (a limit of null means none: no meter). */
export function meterViews(usage: UsageMeter[], timeZone: string, now: Date = new Date()): MeterView[] {
  return usage
    .filter((meter) => typeof meter.limit === "number" && meter.limit > 0)
    .map((meter) => {
      const known = METERS[meter.metric];
      const resets = known?.periodic && meter.period_end ? `Resets on ${resetDate(meter.period_end, timeZone, now)}` : null;
      return {
        metric: meter.metric,
        label: known?.label ?? humanize(meter.metric),
        unit: known?.unit ?? "",
        used: meter.used,
        limit: meter.limit ?? null,
        note: resets,
      };
    });
}

/** A period end is a date ("2026-10-01") or a timestamp; both read as a date. */
function resetDate(value: string, timeZone: string, now: Date): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? shortDate(value, now) : billingDate(value, timeZone, now);
}

/** The usage metric a §1.7 entitlement key is counted by, where the names differ. */
export const METRIC_FOR_ENTITLEMENT: Record<string, string> = {
  ai_credits_monthly: "ai_credits",
  scheduled_posts_monthly: "scheduled_posts",
};

// ---- the plan comparison (the public GET /v1/billing/plans)

const HIGHLIGHTS: { key: string; label: (value: EntitlementValue["value"]) => string | null }[] = [
  { key: "accounts_per_platform", label: (v) => (typeof v === "number" ? `${v} ${v === 1 ? "account" : "accounts"} per platform` : null) },
  { key: "active_automations", label: (v) => (v === null ? "Unlimited automations" : typeof v === "number" ? `${fmt(v)} active automations` : null) },
  { key: "ai_credits_monthly", label: (v) => (typeof v === "number" ? `${fmt(v)} AI credits a month` : null) },
  { key: "scheduled_posts_monthly", label: (v) => (v === null ? "Unlimited scheduled posts" : typeof v === "number" ? `${fmt(v)} scheduled posts a month` : null) },
  { key: "knowledge_characters", label: (v) => (typeof v === "number" ? `${compact(v)} characters of knowledge` : null) },
  { key: "ai_modes", label: (v) => (Array.isArray(v) ? (v.includes("auto") ? "AI Auto mode" : "AI suggestions") : null) },
  { key: "ai_reply_automations", label: (v) => (v === true ? "AI replies in automations" : null) },
  { key: "message_history_days", label: (v) => (v === null ? "Full message history" : typeof v === "number" ? `${v} days of message history` : null) },
];

const number = new Intl.NumberFormat("en-US");
const compactNumber = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const fmt = (n: number) => number.format(n);
const compact = (n: number) => compactNumber.format(n);

/** The lines a plan card lists, from the plan's entitlements. */
export function planHighlights(entitlements: EntitlementValue[]): string[] {
  return HIGHLIGHTS.flatMap(({ key, label }) => {
    const item = entitlements.find((e) => e.key === key);
    if (!item) return [];
    const text = label(item.value);
    return text ? [text] : [];
  });
}
