import { describe, expect, it } from "vitest";

import { describeVariable, fillTemplate, formatMoney, percent, reached } from "./format";

describe("broadcast formatting (GR-23)", () => {
  it("formats money in the estimate's own currency", () => {
    expect(formatMoney("2.35", "INR")).toBe("₹2.35");
    expect(formatMoney(1234.5, "INR")).toBe("₹1,234.50");
    expect(formatMoney("not a number", "INR")).toBe("not a number");
  });

  it("gives a share of a whole, and 0% of nothing", () => {
    expect(percent(1, 3)).toBe("33%");
    expect(percent(3, 3)).toBe("100%");
    expect(percent(5, 0)).toBe("0%");
  });

  it("fills the template's numbered placeholders", () => {
    expect(fillTemplate("Hi {{1}}, sale until {{2}}.", ["Asha", "Friday"])).toBe("Hi Asha, sale until Friday.");
    expect(fillTemplate("Hi {{ 1 }}, {{3}}", ["Asha"])).toBe("Hi Asha, {{3}}");
    expect(fillTemplate("No variables", [])).toBe("No variables");
  });

  it("describes how a variable is mapped", () => {
    expect(describeVariable({ source: "field", field: "first_name", fallback: "there" })).toBe('First name (or "there")');
    expect(describeVariable({ source: "field", field: "city" }, { city: "City" })).toBe("City");
    expect(describeVariable({ source: "fixed", value: "31 October" })).toBe("31 October");
  });

  it("counts everyone who reached WhatsApp as sent", () => {
    expect(reached({ sent: 1, delivered: 2, read: 3 })).toBe(6);
  });
});
