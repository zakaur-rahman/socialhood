/**
 * The landing page's pricing, from the public GET /v1/billing/plans (C-049): §1.7 entitlements
 * from billing/plans.py and paid prices from Dodo. Read on the server and revalidated every five minutes (the
 * API caches Dodo's prices for an hour). A price is never written here: when the API can't be
 * reached, or Dodo gave it no price, the page lists the plan's features and says the price is
 * shown at sign-up. While billing is off (C-172) a paid plan shows its planned price from one
 * constant (copy.ts PLANNED_PRICE_USD), labelled "when we launch"; that figure is never an offer
 * in structured data.
 */
import { z } from "zod";

import type { EntitlementValue } from "@/lib/api/types";
import { planHighlights } from "@/lib/billing/plan";
import { PLAN_NAME, formatPrice, plannedAmount, plannedPriceLabel } from "@/lib/copy";

import table from "./plan-table.json";

/**
 * C-173: five minutes, not an hour. The site builds before a release's API goes live, so a release
 * that changed the plans showed the old limits beside the new prices for up to an hour. The segment
 * `revalidate` on /pricing and the landing equals this (it must stay a literal there).
 */
export const PLANS_REVALIDATE_SECONDS = 300;
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
 * GET /v1/billing/plans on the server, cached for five minutes. Null when the API is unset, down, slow
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
  /** "$15" or "₹999" from Dodo through the API; null when there is none to show. */
  price: string | null;
  /** C-172: "$15 a month when we launch", for a paid plan that isn't on sale and has no real price. */
  planned: { amount: string; label: string } | null;
  /** The same price for structured data: a decimal amount and its ISO currency. */
  offer: { price: string; currency: string } | null;
  trialDays: number;
  features: string[];
  /** False while the plan can't be bought (billing off, or Business without its product): "Coming soon". */
  available: boolean;
};

export type Pricing = {
  /** "api" when the plan list loaded; "fallback" when the page lists features only. */
  source: "api" | "fallback";
  plans: PlanCard[];
  /** Monthly AI credits per plan, for the credits explainer. */
  credits: { free: number | null; pro: number | null; max: number | null };
};

const TAGLINE: Record<PlanName, string> = {
  free: "To get started.",
  pro: "For creators and small businesses.",
  max: "For growing businesses with a team.",
};

/** C-172: the planned price shown while a paid plan isn't on sale. */
function planned(plan: PlanName): PlanCard["planned"] {
  if (plan === "free") return null;
  return { amount: plannedAmount(plan), label: plannedPriceLabel(plan) };
}

function numberOf(entitlements: EntitlementValue[], key: string): number | null {
  const value = entitlements.find((entry) => entry.key === key)?.value;
  return typeof value === "number" ? value : null;
}

/**
 * billing/plans.py as exported to plan-table.json (checked by tests/unit/test_marketing_plan_table.py),
 * used only when the API can't be reached, so the page still lists what each plan includes. Never
 * a price.
 */
function fromTable(plan: "free" | "pro" | "max"): EntitlementValue[] {
  return Object.entries(table.entitlements).map(([key, byPlan]) => ({
    key,
    value: (byPlan as Record<string, EntitlementValue["value"]>)[plan],
  }));
}

export const FALLBACK_ENTITLEMENTS: Record<PlanName, EntitlementValue[]> = {
  free: fromTable("free"),
  pro: fromTable("pro"),
  max: fromTable("max"),
};

/** FR-BIL-03: Creator's (pro) trial, once per workspace; used only in the fallback. */
const FALLBACK_TRIAL_DAYS = 7;

function fallbackCard(plan: PlanName): PlanCard {
  // The fallback has no price and no word on availability: Free is open, the paid plans read as
  // not on sale (their planned price shows, never an offer).
  return {
    plan,
    name: PLAN_NAME[plan],
    tagline: TAGLINE[plan],
    price: null,
    planned: planned(plan),
    offer: null,
    trialDays: plan === "pro" ? FALLBACK_TRIAL_DAYS : 0,
    features: planHighlights(FALLBACK_ENTITLEMENTS[plan]),
    available: plan === "free",
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
    planned: !price && !offer.available ? planned(offer.plan) : null,
    offer: price ? { price: decimalAmount(price.amount_minor, price.currency), currency: price.currency } : null,
    trialDays: offer.trial_days,
    // A paid plan lists what it will include even while it isn't on sale (C-149: no billing yet).
    features: planHighlights(offer.entitlements),
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
        max: numberOf(FALLBACK_ENTITLEMENTS.max, "ai_credits_monthly"),
      },
    };
  }
  const byPlan = new Map(offers.map((offer) => [offer.plan, offer]));
  const free = byPlan.get("free");
  const pro = byPlan.get("pro");
  const max = byPlan.get("max");
  return {
    source: "api",
    plans: ORDER.map((plan) => {
      const offer = byPlan.get(plan);
      return offer ? cardFrom(offer) : fallbackCard(plan);
    }),
    credits: {
      free: numberOf(free?.entitlements ?? FALLBACK_ENTITLEMENTS.free, "ai_credits_monthly"),
      pro: numberOf(pro?.entitlements ?? FALLBACK_ENTITLEMENTS.pro, "ai_credits_monthly"),
      max: numberOf(max?.entitlements ?? FALLBACK_ENTITLEMENTS.max, "ai_credits_monthly"),
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
  { action: "Ask Amplychat (a typical question uses 2 to 4)", credits: "1 per step" },
];
