/**
 * The landing page's pricing, from the public GET /v1/billing/plans (C-049): §1.7 entitlements
 * from billing/plans.py and paid prices from Dodo. Read on the server and revalidated hourly (the
 * API caches Dodo's prices for an hour too). A price is never written here: when the API can't be
 * reached, or Dodo gave it no price, the page lists the plan's features and says the price is
 * shown at sign-up.
 */
import { z } from "zod";

import type { EntitlementValue } from "@/lib/api/types";
import { PLAN_NAME, formatPrice } from "@/lib/copy";

export const PLANS_REVALIDATE_SECONDS = 3600;
const TIMEOUT_MS = 5000;

type PlanName = "free" | "pro" | "max";

const Entitlement = z.object({
  key: z.string(),
  value: z.union([z.number(), z.boolean(), z.array(z.string()), z.null()]),
});

const Offer = z.object({
  plan: z.enum(["free", "pro", "max"]),
  price: z
    .object({
      amount_minor: z.number().int().nonnegative(),
      currency: z.string().regex(/^[A-Z]{3}$/),
      interval: z.string(),
    })
    .nullish(),
  trial_days: z.number().int().nonnegative(),
  entitlements: z.array(Entitlement),
  available: z.boolean(),
});

const PlanListBody = z.object({ items: z.array(Offer) });

export type PlanOfferBody = z.infer<typeof Offer>;

/**
 * GET /v1/billing/plans on the server, cached for an hour. Null when the API is unset, down, slow
 * (5 s), answers with an error or with a body that isn't a plan list.
 */
export async function fetchPlans(
  baseUrl: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL,
  fetcher: typeof fetch = fetch,
): Promise<PlanOfferBody[] | null> {
  if (!baseUrl) return null;
  try {
    const response = await fetcher(`${baseUrl.replace(/\/+$/, "")}/v1/billing/plans`, {
      headers: { accept: "application/json" },
      next: { revalidate: PLANS_REVALIDATE_SECONDS },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const parsed = PlanListBody.safeParse(await response.json());
    return parsed.success ? parsed.data.items : null;
  } catch {
    return null;
  }
}

// ---- what a plan card shows

export type PlanCard = {
  plan: PlanName;
  name: string;
  tagline: string;
  /** "$10" or "₹999" from Dodo through the API; null when there is none to show. */
  price: string | null;
  /** The same price for structured data: a decimal amount and its ISO currency. */
  offer: { price: string; currency: string } | null;
  trialDays: number;
  features: string[];
  /** False for Max until R2: shown as "Coming soon". */
  available: boolean;
};

export type Pricing = {
  /** "api" when the plan list loaded; "fallback" when the page lists features only. */
  source: "api" | "fallback";
  plans: PlanCard[];
  /** Monthly AI credits per plan, for the credits explainer. */
  credits: { free: number | null; pro: number | null };
};

const TAGLINE: Record<PlanName, string> = {
  free: "To get started.",
  pro: "For a growing business.",
  max: "For teams with several members.",
};

const count = new Intl.NumberFormat("en-US");

function plural(n: number, one: string, many: string): string {
  return `${count.format(n)} ${n === 1 ? one : many}`;
}

type Line = (value: EntitlementValue["value"]) => string | null;

/** Each §1.7 entitlement as a line on the plan card, in the product guide's order. */
const LINES: { key: string; line: Line }[] = [
  {
    key: "accounts_per_platform",
    line: (v) => (typeof v === "number" ? `${count.format(v)} Instagram and ${plural(v, "WhatsApp account", "WhatsApp accounts")}` : null),
  },
  {
    key: "ai_modes",
    line: (v) => (Array.isArray(v) ? (v.includes("auto") ? "AI replies: Off, Suggest and Auto" : "AI replies: Off and Suggest") : null),
  },
  { key: "ai_reply_automations", line: (v) => (v === true ? "AI replies inside automations" : null) },
  { key: "ai_credits_monthly", line: (v) => (typeof v === "number" ? `${count.format(v)} AI credits a month` : null) },
  {
    key: "active_automations",
    line: (v) => (v === null ? "Unlimited active automations" : typeof v === "number" ? plural(v, "active automation", "active automations") : null),
  },
  {
    key: "knowledge_characters",
    line: (v) => (typeof v === "number" ? `${count.format(v)} characters of knowledge` : null),
  },
  {
    key: "scheduled_posts_monthly",
    line: (v) => (v === null ? "Unlimited scheduled posts" : typeof v === "number" ? `${plural(v, "scheduled post", "scheduled posts")} a month` : null),
  },
  {
    key: "pending_scheduled_messages",
    line: (v) =>
      v === null ? "Unlimited scheduled messages" : typeof v === "number" ? plural(v, "pending scheduled message", "pending scheduled messages") : null,
  },
  {
    key: "message_history_days",
    line: (v) => (v === null ? "Unlimited message history" : typeof v === "number" ? `${plural(v, "day", "days")} of message history` : null),
  },
  {
    key: "comment_intelligence_posts",
    line: (v) =>
      v === null
        ? "Comment analysis on all posts"
        : typeof v === "number"
          ? `Comment analysis on your ${plural(v, "latest post", "latest posts")} per account`
          : null,
  },
];

/** The plan card's feature lines from its entitlements; unknown keys are left out. */
export function planFeatures(entitlements: EntitlementValue[]): string[] {
  return LINES.flatMap(({ key, line }) => {
    const item = entitlements.find((entry) => entry.key === key);
    const text = item ? line(item.value) : null;
    return text ? [text] : [];
  });
}

function numberOf(entitlements: EntitlementValue[], key: string): number | null {
  const value = entitlements.find((entry) => entry.key === key)?.value;
  return typeof value === "number" ? value : null;
}

/**
 * The product guide's plan table (and billing/plans.py), used only when the API can't be reached,
 * so the page still lists what each plan includes. Never a price.
 */
export const FALLBACK_ENTITLEMENTS: Record<"free" | "pro", EntitlementValue[]> = {
  free: [
    { key: "accounts_per_platform", value: 1 },
    { key: "ai_modes", value: ["off", "suggest"] },
    { key: "ai_reply_automations", value: false },
    { key: "ai_credits_monthly", value: 200 },
    { key: "active_automations", value: 3 },
    { key: "knowledge_characters", value: 200_000 },
    { key: "scheduled_posts_monthly", value: 10 },
    { key: "pending_scheduled_messages", value: 20 },
    { key: "message_history_days", value: 90 },
    { key: "comment_intelligence_posts", value: 5 },
  ],
  pro: [
    { key: "accounts_per_platform", value: 3 },
    { key: "ai_modes", value: ["off", "suggest", "auto"] },
    { key: "ai_reply_automations", value: true },
    { key: "ai_credits_monthly", value: 5000 },
    { key: "active_automations", value: 50 },
    { key: "knowledge_characters", value: 5_000_000 },
    { key: "scheduled_posts_monthly", value: 300 },
    { key: "pending_scheduled_messages", value: 500 },
    { key: "message_history_days", value: null },
    { key: "comment_intelligence_posts", value: null },
  ],
};

/** FR-BIL-03: Pro's trial, once per workspace; used only in the fallback. */
const FALLBACK_TRIAL_DAYS = 7;

function fallbackCard(plan: PlanName): PlanCard {
  if (plan === "max") {
    return { plan, name: PLAN_NAME.max, tagline: TAGLINE.max, price: null, offer: null, trialDays: 0, features: [], available: false };
  }
  return {
    plan,
    name: PLAN_NAME[plan],
    tagline: TAGLINE[plan],
    price: null,
    offer: null,
    trialDays: plan === "pro" ? FALLBACK_TRIAL_DAYS : 0,
    features: planFeatures(FALLBACK_ENTITLEMENTS[plan]),
    available: true,
  };
}

/** Minor units as a decimal string in the currency's own precision: 99900 INR is "999.00". */
export function decimalAmount(amountMinor: number, currency: string): string {
  let digits = 2;
  try {
    digits = new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
  } catch {
    // an unknown code keeps two digits
  }
  return (amountMinor / 10 ** digits).toFixed(digits);
}

function cardFrom(offer: PlanOfferBody): PlanCard {
  const price = offer.plan !== "free" && offer.price ? offer.price : null;
  return {
    plan: offer.plan,
    name: PLAN_NAME[offer.plan],
    tagline: TAGLINE[offer.plan],
    price: price ? formatPrice(price) : null,
    offer: price ? { price: decimalAmount(price.amount_minor, price.currency), currency: price.currency } : null,
    trialDays: offer.trial_days,
    features: offer.available ? planFeatures(offer.entitlements) : [],
    available: offer.available,
  };
}

const ORDER: PlanName[] = ["free", "pro", "max"];

/** The three plan cards from the API's plan list, or from the fallback when there is none. */
export function buildPricing(offers: PlanOfferBody[] | null): Pricing {
  if (!offers) {
    return {
      source: "fallback",
      plans: ORDER.map(fallbackCard),
      credits: {
        free: numberOf(FALLBACK_ENTITLEMENTS.free, "ai_credits_monthly"),
        pro: numberOf(FALLBACK_ENTITLEMENTS.pro, "ai_credits_monthly"),
      },
    };
  }
  const byPlan = new Map(offers.map((offer) => [offer.plan, offer]));
  const free = byPlan.get("free");
  const pro = byPlan.get("pro");
  return {
    source: "api",
    plans: ORDER.map((plan) => {
      const offer = byPlan.get(plan);
      return offer ? cardFrom(offer) : fallbackCard(plan);
    }),
    credits: {
      free: numberOf(free?.entitlements ?? FALLBACK_ENTITLEMENTS.free, "ai_credits_monthly"),
      pro: numberOf(pro?.entitlements ?? FALLBACK_ENTITLEMENTS.pro, "ai_credits_monthly"),
    },
  };
}

/** The product guide's credit costs (billing/plans.py CREDIT_COSTS), for the explainer. */
export const CREDIT_COSTS: { action: string; credits: string }[] = [
  { action: "Analysing a message or a comment", credits: "1" },
  { action: "Suggesting a reply, or an Auto reply", credits: "2" },
  { action: "An AI reply inside an automation", credits: "2" },
  { action: "Summarising a conversation", credits: "1" },
  { action: "Summarising a post's comments", credits: "2" },
  { action: "Writing a caption or hashtags", credits: "1" },
  { action: "Testing a knowledge question", credits: "1" },
  { action: "Ask Social Hood (a typical question uses 2 to 4)", credits: "1 per step" },
];
