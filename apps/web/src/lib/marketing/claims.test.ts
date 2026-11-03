import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { render } from "@testing-library/react";
import { createElement } from "react";

import { Pricing } from "@/components/marketing/Pricing";
import { AGENCY, PLAN_NAME, PLANNED_PRICE_USD, plannedPriceLabel } from "@/lib/copy";
import { plansFixture } from "@/test/plans";

import { CONNECT_AI_FAQ, PLAN_ROWS } from "./connect-ai";
import { FAQ_ALL } from "./faq";
import { GTM_PAGES } from "./gtm-pages";
import { MATRIX } from "./plan-matrix";
import { buildPricing } from "./plans";
import { FOR_BUSINESSES, FOR_CREATORS } from "./solutions";

/**
 * Content rules for the plan names and prices (C-172): the marketing copy never ranks us. "Cheapest",
 * "best" and "#1" are claims we can't back, so none may appear in the pricing, plan, solution, FAQ
 * or comparison copy, including the Creator, Business and Agency strings.
 */
const CLAIMS = /\bcheapest\b|\bbest\b|#\s?1\b|\bnumber one\b/i;
/** Feature names and plain verbs that use the word without ranking anything. */
const ALLOWED = /best posting times|best times|did best/gi;

function claims(text: string): string[] {
  return (text.replace(ALLOWED, "").match(new RegExp(CLAIMS, "gi")) ?? []).map((word) => word.toLowerCase());
}

function pricingText(): string {
  const billingOff = plansFixture().items.map((offer) => (offer.plan === "pro" ? { ...offer, available: false, price: null } : offer));
  const { container } = render(createElement(Pricing, { pricing: buildPricing(billingOff) }));
  return container.textContent ?? "";
}

describe("the claim words stay out of the marketing copy (C-172)", () => {
  it("the checker finds the words, and lets the feature name through", () => {
    expect(claims("The cheapest plan")).toEqual(["cheapest"]);
    expect(claims("Our best plan, the #1 choice")).toEqual(["best", "#1"]);
    expect(claims("Best posting times, and which posts did best")).toEqual([]);
  });

  it("the plan names, planned prices and the Agency card make no claim", () => {
    const strings = [
      ...Object.values(PLAN_NAME),
      plannedPriceLabel("pro"),
      plannedPriceLabel("max"),
      ...Object.values(AGENCY).flat(),
    ];
    expect(PLANNED_PRICE_USD).toEqual({
      pro: { month: 15, six_month: 81 },
      max: { month: 30, six_month: 153 },
      agency: { month: 70, six_month: 315 },
    });
    expect(claims(strings.join("\n"))).toEqual([]);
  });

  it("the pricing section (cards, credits, notes) makes no claim", () => {
    expect(claims(pricingText())).toEqual([]);
  });

  it("the pricing page and section sources make no claim", () => {
    for (const file of ["src/components/marketing/Pricing.tsx", "src/app/(marketing)/pricing/page.tsx", "src/lib/marketing/plans.ts"]) {
      expect(claims(readFileSync(join(process.cwd(), file), "utf8")), file).toEqual([]);
    }
  });

  it("the plan table's labels and notes make no claim", () => {
    const text = MATRIX.flatMap((group) => [group.title, ...group.rows.flatMap((row) => [row.label, row.note ?? ""])]).join("\n");
    expect(claims(text)).toEqual([]);
  });

  it("the landing and /pricing FAQ, the solution pages and the Connect AI plan rows make no claim", () => {
    expect(claims(JSON.stringify(FAQ_ALL))).toEqual([]);
    expect(claims(JSON.stringify([FOR_CREATORS, FOR_BUSINESSES]))).toEqual([]);
    expect(claims(JSON.stringify([PLAN_ROWS, CONNECT_AI_FAQ]))).toEqual([]);
  });

  it("every feature, comparison and switching page (gtm-pages) makes no claim", () => {
    for (const page of GTM_PAGES) expect(claims(JSON.stringify(page)), page.path).toEqual([]);
  });
});
