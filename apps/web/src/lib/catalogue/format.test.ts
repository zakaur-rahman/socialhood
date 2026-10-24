import { describe, expect, it } from "vitest";

import {
  CSV_COLUMNS,
  CSV_TEMPLATE,
  formatPrice,
  linkProblem,
  parsePrice,
  priceLabel,
  priceProblem,
  productStock,
  stockLabel,
} from "./format";

describe("prices", () => {
  it("shows minor units with Intl, whatever the currency's decimals", () => {
    expect(formatPrice(79900, "INR", "en-IN")).toBe("₹799.00");
    expect(formatPrice(1500, "JPY", "en-US")).toBe("¥1,500");
    expect(formatPrice(1250, "KWD", "en-US")).toContain("1.250");
    expect(formatPrice(1999, "USD", "en-US")).toBe("$19.99");
  });

  it("gives a list one price, a range across variants, or says there is none", () => {
    const base = { currency: "INR" as const };
    expect(priceLabel({ ...base, price_minor: 49900, variants: [] }, "en-IN")).toBe("₹499.00");
    expect(priceLabel({ ...base, price_minor: null, variants: [] }, "en-IN")).toBe("No price");
    const variant = (price_minor: number) => ({ price_minor }) as never;
    expect(priceLabel({ ...base, price_minor: null, variants: [variant(79900), variant(79900)] }, "en-IN")).toBe("₹799.00");
    expect(priceLabel({ ...base, price_minor: null, variants: [variant(84900), variant(79900)] }, "en-IN")).toBe(
      "₹799.00 to ₹849.00",
    );
  });

  it("reads a typed price the way the API does", () => {
    expect(parsePrice("799", "INR")).toBe("799");
    expect(parsePrice("1,299.50", "INR")).toBe("1299.50");
    expect(parsePrice("12.345", "INR")).toBeNull();
    expect(parsePrice("1.5", "JPY")).toBeNull();
    expect(parsePrice("abc", "INR")).toBeNull();
    expect(priceProblem("", "INR")).toBe("Enter a price.");
    expect(priceProblem("1.5", "JPY")).toBe("JPY prices have no decimal places.");
    expect(priceProblem("12.345", "INR")).toMatch(/up to 2 decimal places/);
    expect(priceProblem("799.50", "INR")).toBeNull();
  });
});

describe("stock", () => {
  it("tells never recorded from out of stock", () => {
    expect(stockLabel(null)).toBe("Not tracked");
    expect(stockLabel(0)).toBe("Out of stock");
    expect(stockLabel(12)).toBe("12 in stock");
  });

  it("totals the variants only when they all record stock", () => {
    const variants = (...stock: (number | null)[]) => stock.map((s) => ({ stock: s }) as never);
    expect(productStock({ stock: 3, variants: [] })).toBe("3 in stock");
    expect(productStock({ stock: null, variants: variants(4, 0, 8) })).toBe("12 in stock");
    expect(productStock({ stock: null, variants: variants(null, null) })).toBe("Not tracked");
    expect(productStock({ stock: null, variants: variants(4, null) })).toBe("1 of 2 variants tracked");
  });
});

describe("links and the CSV starter file", () => {
  it("accepts only https, or nothing", () => {
    expect(linkProblem("")).toBeNull();
    expect(linkProblem("https://shop.example/kurta")).toBeNull();
    expect(linkProblem("http://shop.example")).toBe("Enter a link that starts with https://.");
    expect(linkProblem("shop.example")).toBe("Enter a link that starts with https://.");
  });

  it("starts with the header row the API reads", () => {
    const [header, ...lines] = CSV_TEMPLATE.split("\n");
    expect(header.split(",")).toEqual([...CSV_COLUMNS]);
    expect(lines).toHaveLength(3);
    for (const line of lines) expect(line.split(",")).toHaveLength(CSV_COLUMNS.length);
  });
});
