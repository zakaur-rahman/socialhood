import { describe, expect, it, vi } from "vitest";

import { plansFetch, plansFixture } from "@/test/plans";

import { PLANS_REVALIDATE_SECONDS, buildPricing, decimalAmount, fetchPlans } from "./plans";

const API = "https://api.socialhood.test";

describe("fetchPlans (GET /v1/billing/plans, server-side, every five minutes)", () => {
  it("reads the plan list and caches it for an hour", async () => {
    const fetcher = vi.fn(plansFetch(plansFixture()));
    const plans = await fetchPlans(`${API}/`, fetcher as unknown as typeof fetch);
    expect(plans?.map((p) => p.plan)).toEqual(["free", "pro", "max", "agency"]);
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit & { next?: { revalidate?: number } }];
    expect(url).toBe(`${API}/v1/billing/plans`);
    expect(init.next?.revalidate).toBe(300);
    expect(PLANS_REVALIDATE_SECONDS).toBe(300);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("is null when the API is unset, down, erroring or answers something else", async () => {
    expect(await fetchPlans(undefined, vi.fn() as unknown as typeof fetch)).toBeNull();
    const down = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await fetchPlans(API, down as unknown as typeof fetch)).toBeNull();
    expect(await fetchPlans(API, plansFetch({ detail: "boom" }, 503) as unknown as typeof fetch)).toBeNull();
    expect(await fetchPlans(API, plansFetch({ plans: [] }) as unknown as typeof fetch)).toBeNull();
    const notJson = async () => new Response("<html>", { status: 200 });
    expect(await fetchPlans(API, notJson as unknown as typeof fetch)).toBeNull();
  });
});

describe("buildPricing", () => {
  it("from the API: Dodo's price and currency, the trial, and Max coming soon", () => {
    const pricing = buildPricing(plansFixture().items);
    expect(pricing.source).toBe("api");
    const [free, pro, max] = pricing.plans;
    expect(free).toMatchObject({ plan: "free", price: null, available: true });
    expect(pro).toMatchObject({ plan: "pro", price: "₹999", offer: { price: "999.00", currency: "INR" }, trialDays: 7 });
    expect(max).toMatchObject({ plan: "max", name: "Business", available: false });
    expect(max.features).toContain("5,000 AI credits a month, up to about 2,500 AI replies");
    expect(max.features).toContain("API keys and Zapier");
    expect(pro.name).toBe("Creator");
    expect(pricing.credits).toEqual({ free: 200, pro: 1500, max: 5000, agency: 12_000 });
  });

  it("a Pro plan Dodo couldn't price has no price, never a made-up one", () => {
    const pro = buildPricing(plansFixture({ proPrice: null }).items).plans[1];
    expect(pro.price).toBeNull();
    expect(pro.offer).toBeNull();
    expect(pro.features.length).toBeGreaterThanOrEqual(6);
  });

  it("without the API: the features from the product guide and no prices at all", () => {
    const pricing = buildPricing(null);
    expect(pricing.source).toBe("fallback");
    expect(pricing.plans.map((card) => card.price)).toEqual([null, null, null, null]);
    expect(pricing.plans.map((card) => card.offer)).toEqual([null, null, null, null]);
    expect(pricing.plans[1].trialDays).toBe(7);
    expect(pricing.plans[2].available).toBe(false);
  });

  it("C-174: Agency's card lines come from its entitlements", () => {
    const agency = buildPricing(null).plans[3];
    expect(agency).toMatchObject({ plan: "agency", name: "Agency", available: false, trialDays: 0 });
    expect(agency.features).toEqual([
      "10 each of Instagram, WhatsApp and Facebook; 1 web chat",
      "10 team members",
      "Unlimited automations",
      "12,000 AI credits a month, up to about 6,000 AI replies",
      "Unlimited scheduled posts",
      "50M characters of knowledge",
      "API keys and Zapier",
    ]);
  });

  it("the fallback lists exactly what the API's plans list", () => {
    const fromApi = buildPricing(plansFixture().items).plans;
    const fallback = buildPricing(null).plans;
    expect(fallback[0].features).toEqual(fromApi[0].features);
    expect(fallback[1].features).toEqual(fromApi[1].features);
  });
});

describe("the card lines (C-173)", () => {
  it("each plan lists six or seven key lines, in the dashboard's wording", () => {
    const [free, pro, max] = buildPricing(null).plans;
    expect(free.features).toEqual([
      "Any 2 of Instagram, Facebook or web chat",
      "1 team member",
      "3 active automations",
      "200 AI credits a month, up to about 100 AI replies",
      "10 scheduled posts a month",
      "200K characters of knowledge",
      "AI suggestions only",
    ]);
    expect(pro.features).toEqual([
      "1 each of Instagram, WhatsApp, Facebook and web chat",
      "2 team members",
      "25 active automations",
      "1,500 AI credits a month, up to about 750 AI replies",
      "100 scheduled posts a month",
      "1M characters of knowledge",
      "AI Auto mode and suggestions",
    ]);
    expect(max.features).toEqual([
      "3 each of Instagram, WhatsApp and Facebook; 1 web chat",
      "3 team members",
      "50 active automations",
      "5,000 AI credits a month, up to about 2,500 AI replies",
      "300 scheduled posts a month",
      "5M characters of knowledge",
      "API keys and Zapier",
    ]);
  });
});

it("decimalAmount follows the currency's precision", () => {
  expect(decimalAmount(1000, "USD")).toBe("10.00");
  expect(decimalAmount(1200, "JPY")).toBe("1200");
});
