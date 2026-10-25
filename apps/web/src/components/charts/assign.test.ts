import { describe, expect, it } from "vitest";

import { assignColours } from "./palette";

const ORDER = ["pricing", "product_inquiry", "purchase", "shipping"];

describe("assignColours", () => {
  it("gives a topic the hue of its place in the fixed order, whatever else is shown", () => {
    expect(assignColours(["shipping", "pricing"], ORDER).get("shipping")).toBe(3);
    expect(assignColours(["pricing"], ORDER).get("pricing")).toBe(0);
  });

  it("never gives two shown topics the same hue", () => {
    const colours = assignColours(["pricing", "unknown_a", "unknown_b"], ORDER);
    expect(new Set(colours.values()).size).toBe(3);
  });

  it("falls back to the neutral past the sixth hue", () => {
    const keys = Array.from({ length: 8 }, (_, i) => `k${i}`);
    const colours = assignColours(keys, []);
    expect([...colours.values()].filter((index) => index >= 6)).toHaveLength(2);
  });
});
