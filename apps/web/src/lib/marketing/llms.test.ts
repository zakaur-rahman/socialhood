import { describe, expect, it } from "vitest";

import { plansFixture } from "@/test/plans";

import { llmsText } from "./llms";
import { buildPricing } from "./plans";

describe("llms.txt plans (SEO finding 25)", () => {
  it("names each plan with the price, trial and limits /pricing shows", () => {
    const text = llmsText("https://socialhood.example", buildPricing(plansFixture().items));
    expect(text).toContain("Plans: Free, Creator at ₹999 a month.");
    expect(text).toContain("## Plans");
    expect(text).toContain("- Free: free, no card needed");
    expect(text).toContain("- Creator: ₹999 a month, 7-day free trial. ");
    expect(text).toContain("- Business: not on sale yet");
    expect(text).toContain("- Agency: not on sale yet");
  });

  it("without the plan list: no price anywhere, a pointer to the pricing page", () => {
    const text = llmsText("https://socialhood.example", buildPricing(null));
    expect(text).toContain("There is a Free plan; prices for paid plans are on the pricing page.");
    expect(text).not.toContain("## Plans");
    expect(text).not.toContain("Creator at");
  });
});
