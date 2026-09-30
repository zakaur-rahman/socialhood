import { describe, expect, it, vi } from "vitest";

import { plansFetch, plansFixture } from "@/test/plans";

import { FALLBACK_ENTITLEMENTS, buildPricing, decimalAmount, fetchPlans, planFeatures } from "./plans";

const API = "https://api.socialhood.test";

describe("fetchPlans (GET /v1/billing/plans, server-side, hourly)", () => {
  it("reads the plan list and caches it for an hour", async () => {
    const fetcher = vi.fn(plansFetch(plansFixture()));
    const plans = await fetchPlans(`${API}/`, fetcher as unknown as typeof fetch);
    expect(plans?.map((p) => p.plan)).toEqual(["free", "pro", "max"]);
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit & { next?: { revalidate?: number } }];
    expect(url).toBe(`${API}/v1/billing/plans`);
    expect(init.next?.revalidate).toBe(3600);
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
    expect(max).toMatchObject({ plan: "max", available: false, features: [] });
    expect(pricing.credits).toEqual({ free: 200, pro: 5000 });
  });

  it("a Pro plan Dodo couldn't price has no price, never a made-up one", () => {
    const pro = buildPricing(plansFixture({ proPrice: null }).items).plans[1];
    expect(pro.price).toBeNull();
    expect(pro.offer).toBeNull();
    expect(pro.features.length).toBeGreaterThan(5);
  });

  it("without the API: the features from the product guide and no prices at all", () => {
    const pricing = buildPricing(null);
    expect(pricing.source).toBe("fallback");
    expect(pricing.plans.map((card) => card.price)).toEqual([null, null, null]);
    expect(pricing.plans.map((card) => card.offer)).toEqual([null, null, null]);
    expect(pricing.plans[1].trialDays).toBe(7);
    expect(pricing.plans[2].available).toBe(false);
  });

  it("the fallback lists exactly what the API's plans list", () => {
    const fromApi = buildPricing(plansFixture().items).plans;
    const fallback = buildPricing(null).plans;
    expect(fallback[0].features).toEqual(fromApi[0].features);
    expect(fallback[1].features).toEqual(fromApi[1].features);
  });
});

describe("planFeatures", () => {
  it("phrases the entitlements as the product guide does", () => {
    expect(planFeatures(FALLBACK_ENTITLEMENTS.free)).toEqual([
      "1 Instagram and 1 WhatsApp account",
      "AI replies: Off and Suggest",
      "200 AI credits a month",
      "3 active automations",
      "200,000 characters of knowledge",
      "10 scheduled posts a month",
      "20 pending scheduled messages",
      "90 days of message history",
      "Comment analysis on your 5 latest posts per account",
    ]);
    expect(planFeatures(FALLBACK_ENTITLEMENTS.pro)).toEqual([
      "3 Instagram and 3 WhatsApp accounts",
      "AI replies: Off, Suggest and Auto",
      "AI replies inside automations",
      "5,000 AI credits a month",
      "50 active automations",
      "5,000,000 characters of knowledge",
      "300 scheduled posts a month",
      "500 pending scheduled messages",
      "Unlimited message history",
      "Comment analysis on all posts",
    ]);
  });

  it("leaves out keys it doesn't know", () => {
    expect(planFeatures([{ key: "video_minutes", value: 5 }])).toEqual([]);
  });
});

it("decimalAmount follows the currency's precision", () => {
  expect(decimalAmount(1000, "USD")).toBe("10.00");
  expect(decimalAmount(1200, "JPY")).toBe("1200");
});
