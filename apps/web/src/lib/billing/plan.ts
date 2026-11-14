/**
 * The billing state as the UI reads it (F-15, UX-SCR-07, FR-BIL-02…06). GET …/billing is the only
 * source (TR-BIL-04); these functions only phrase it. Nothing here grants a plan: that arrives
 * from Dodo's signed webhook as usage.updated (C-049).
 */
import type { BillingPrice, BillingState, EntitlementValue, PlanOffer, UsageMeter } from "@/lib/api/types";
import { PLAN_NAME, billingCopy, formatPrice, plannedPrice, pricePerPeriod, shortDate, type PlanName } from "@/lib/copy";
import table from "@/lib/marketing/plan-table.json";
import { dayKey } from "@/lib/tz";

const DAY_MS = 86_400_000;

/** FR-BIL-03: the Creator (pro) trial's length until the plan list says otherwise. */
export const TRIAL_DAYS = 7;

/** A timestamp as a date in the workspace timezone: "3 Oct", or "3 Oct 2027" in another year. */
export function billingDate(iso: string, timeZone: string, now: Date = new Date()): string {
  return shortDate(dayKey(iso, timeZone), now);
}

/** Whole days left until an instant, rounded up (a trial ending in 30 hours has 2 days left). */
export function daysUntil(iso: string, now: Date = new Date()): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now.getTime()) / DAY_MS));
}

/** The paid plan's monthly price, from GET …/billing (F-15) or the public plan list. */
export function priceOf(
  plan: PlanName,
  billing: BillingState | undefined,
  plans?: PlanOffer[] | undefined,
): BillingPrice | null {
  return (
    billing?.prices.find((price) => price.plan === plan && price.interval === "month") ??
    plans?.find((offer) => offer.plan === plan)?.price ??
    null
  );
}

type Money = { amount_minor: number; currency: string };

/** A six-month card's price: "$81" and "($13.50 a month), save 10%". */
export type SixMonthOffer = { total: string; note: string; planned: boolean };

/**
 * C-174: what a plan's six-month card shows: Dodo's price when it is on sale; the planned price while
 * the plan isn't on sale at all; null (keep the monthly price, no six-month button) when the plan is
 * on sale monthly with no six-month price.
 */
export function sixMonthOffer(offer: {
  plan: PlanName;
  available: boolean;
  price?: Money | null;
  six_month_price?: Money | null;
}): SixMonthOffer | null {
  if (offer.plan === "free") return null;
  const planned = !offer.six_month_price;
  if (planned && offer.available) return null;
  const six = offer.six_month_price ?? plannedPrice(offer.plan, "six_month");
  const month = planned ? plannedPrice(offer.plan, "month") : offer.price;
  const perMonth = formatPrice({ amount_minor: Math.round(six.amount_minor / 6), currency: six.currency });
  const save =
    month && month.currency === six.currency ? Math.round((1 - six.amount_minor / (6 * month.amount_minor)) * 100) : 0;
  return { total: formatPrice(six), note: `(${perMonth} a month)${save > 0 ? `, save ${save}%` : ""}`, planned };
}

export function entitlementOf(entitlements: EntitlementValue[] | undefined, key: string): EntitlementValue["value"] | undefined {
  return entitlements?.find((item) => item.key === key)?.value;
}

/** Whether the workspace can start a checkout: it has no paid plan (409 otherwise, C-049). */
export function canCheckout(billing: BillingState | undefined): boolean {
  return !billing || billing.plan === "free" || billing.status === "free" || billing.status === "expired";
}

/** C-149: whether paid plans are on sale on this server (false: billing isn't set up yet). */
export function billingOpen(billing: BillingState | undefined): boolean {
  return billing?.billing_available !== false;
}

/** A checkout or trial may be offered: no paid plan, and paid plans are on sale (C-149). */
export function canStartCheckout(billing: BillingState | undefined): boolean {
  return canCheckout(billing) && billingOpen(billing);
}

export type StatusTone = "neutral" | "brand" | "warning" | "danger";

export type PlanStatus = {
  plan: string;
  badge: { label: string; tone: StatusTone };
  /** One line under the plan name: renewal, trial end, grace end or when the paid plan stops. */
  line: string;
  /** Resume is offered (a cancellation is pending, FR-BIL-04). */
  resumable: boolean;
  /** Cancel is offered (a paid plan that renews). */
  cancellable: boolean;
};

/**
 * UX-SCR-07's plan card: name, status and the date that matters. Trial with days left, active
 * with its renewal, on hold with its grace end (FR-BIL-06), or "Creator until {date}" when cancelled.
 */
export function planStatus(billing: BillingState, timeZone: string, now: Date = new Date()): PlanStatus {
  const name = PLAN_NAME[billing.plan];
  const date = (iso: string | null | undefined) => (iso ? billingDate(iso, timeZone, now) : null);
  // What this workspace bought, not the plan's monthly price (C-174).
  const perMonth = billing.current_price ? pricePerPeriod(billing.current_price) : null;

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
          badge: { label: "Cancelling", tone: "warning" },
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
        badge: { label: "On hold", tone: "danger" },
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
        line: "Upgrade for WhatsApp, Auto replies and more automations, scheduled posts and AI credits.",
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
  channels: { label: "Channels", unit: "channels" },
  social_accounts: { label: "Connected accounts", unit: "accounts" },
  instagram_accounts: { label: "Instagram accounts", unit: "connected" },
  whatsapp_accounts: { label: "WhatsApp accounts", unit: "connected" },
  facebook_accounts: { label: "Facebook Pages", unit: "connected" },
  youtube_accounts: { label: "YouTube channels", unit: "connected" },
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

/**
 * C-173: the key lines of a plan card, the same on the dashboard and the marketing pages: channels,
 * members, automations, credits, posts, knowledge, then one more (API keys and Zapier where the plan
 * has them, else the AI mode). Six or seven lines, in this order; the full table has the rest.
 */
const HIGHLIGHTS: { key: string; label: (value: EntitlementValue["value"], all: EntitlementValue[]) => string | null }[] = [
  { key: "channels_total", label: (v) => (typeof v === "number" ? `Any ${v} of Instagram, Facebook or web chat` : null) },
  {
    key: "accounts_per_platform",
    label: (v, all) => {
      if (typeof v !== "number") return null;
      const instagram = all.find((e) => e.key === "instagram_accounts")?.value ?? v;
      if (instagram === v) {
        return v === 1 ? "1 each of Instagram, WhatsApp, Facebook and web chat" : `${v} each of Instagram, WhatsApp and Facebook; 1 web chat`;
      }
      return v === 1
        ? `${instagram} Instagram; 1 each of WhatsApp, Facebook and web chat`
        : `${instagram} Instagram; ${v} each of WhatsApp and Facebook; 1 web chat`;
    },
  },
  { key: "members", label: (v) => (typeof v === "number" ? `${v} ${v === 1 ? "team member" : "team members"}` : null) },
  { key: "active_automations", label: (v) => (v === null ? "Unlimited automations" : typeof v === "number" ? `${fmt(v)} active automations` : null) },
  {
    key: "ai_credits_monthly",
    label: (v) =>
      typeof v === "number" ? `${fmt(v)} AI credits a month, up to about ${fmt(Math.floor(v / table.credit_costs.auto_reply))} AI replies` : null,
  },
  { key: "scheduled_posts_monthly", label: (v) => (v === null ? "Unlimited scheduled posts" : typeof v === "number" ? `${fmt(v)} scheduled posts a month` : null) },
  { key: "knowledge_characters", label: (v) => (typeof v === "number" ? `${compact(v)} characters of knowledge` : null) },
];

const number = new Intl.NumberFormat("en-US");
const compactNumber = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const fmt = (n: number) => number.format(n);
const compact = (n: number) => compactNumber.format(n);

/** The lines a plan card lists, from the plan's entitlements (C-173: six, and a seventh below). */
export function planHighlights(entitlements: EntitlementValue[]): string[] {
  const lines = HIGHLIGHTS.flatMap(({ key, label }) => {
    if (key === "accounts_per_platform" && typeof entitlements.find((e) => e.key === "channels_total")?.value === "number") return [];
    const item = entitlements.find((e) => e.key === key);
    if (!item) return [];
    const text = label(item.value, entitlements);
    return text ? [text] : [];
  });
  const value = (key: string) => entitlements.find((e) => e.key === key)?.value;
  if (value("public_api") === true) lines.push("API keys and Zapier");
  else if (Array.isArray(value("ai_modes"))) lines.push((value("ai_modes") as string[]).includes("auto") ? "AI Auto mode and suggestions" : "AI suggestions only");
  return lines;
}
