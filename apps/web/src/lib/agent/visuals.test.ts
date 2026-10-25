import { describe, expect, it } from "vitest";

import { metricDelta } from "@/test/agent";

import { deltaHints, deltaTrend, formatValue, httpsOnly, totalsNote } from "./visuals";

describe("visual figures (GR-38): formatting only, the API works every number out", () => {
  it("formats counts and percentages, and a missing value as a dash", () => {
    expect(formatValue("count", 11800)).toBe("11,800");
    expect(formatValue("count", 0)).toBe("0");
    expect(formatValue("percent", 6.14)).toBe("6.1%");
    expect(formatValue("count", null)).toBe("—");
    expect(formatValue("count", undefined)).toBe("—");
  });

  it("the change chip shows the API's percentage, direction and tone", () => {
    const up = deltaTrend({ change_pct: 18.4, direction: "up", tone: "good" }, "1-22 Sep 2026");
    expect(up).toEqual({ direction: "up", good: true, text: "+18.4%", words: "up 18.4% from 1-22 Sep 2026" });
    const down = deltaTrend({ change_pct: -9, direction: "down", tone: "bad" }, "last month");
    expect(down).toMatchObject({ direction: "down", good: false, text: "−9%" });
    // More unfollows is bad news even though the number went up: the API's tone decides.
    expect(deltaTrend({ change_pct: 50, direction: "up", tone: "bad" }, "p")).toMatchObject({ good: false, text: "+50%" });
  });

  it("flat, new and neutral changes", () => {
    expect(deltaTrend({ change_pct: 0.2, direction: "flat", tone: "neutral" }, "p")).toMatchObject({
      direction: "flat",
      good: null,
      text: "No change",
    });
    // Against a previous zero there is no percentage, only the direction.
    expect(deltaTrend({ change_pct: null, direction: "up", tone: "good" }, "p")).toMatchObject({ text: "New", good: true });
    expect(deltaTrend({ change_pct: 12, direction: "up", tone: "neutral" }, "p")).toMatchObject({ good: null });
  });

  it("no direction, no chip: an unknown side, or periods of different length", () => {
    expect(deltaTrend({ change_pct: null, direction: null, tone: "neutral" }, "p")).toBeNull();
  });

  it("lines under a card: the previous figure, the days behind a gap, and why a figure is missing", () => {
    expect(deltaHints(metricDelta(), "1-22 Sep 2026")).toEqual(["1-22 Sep 2026: 10,000"]);
    expect(deltaHints(metricDelta({ current_coverage: "21 of 22 days", previous_coverage: "19 of 22 days" }), "Sep")).toEqual([
      "Sep: 10,000",
      "This period: 21 of 22 days",
      "Sep: 19 of 22 days",
    ]);
    const reason = "Insights aren't granted for @maple.bakery, so this isn't available.";
    expect(deltaHints(metricDelta({ current: null, previous: null, unavailable: reason }), "Sep")).toEqual([reason]);
    expect(deltaHints(metricDelta({ current: null, previous: 5, unavailable: null }), "Sep")).toEqual(["Not available.", "Sep: 5"]);
    expect(deltaHints(metricDelta({ previous: null }), "Sep")).toEqual(["Sep: not available"]);
  });

  it("explains how daily figures are added up, only when they are shown", () => {
    expect(totalsNote([{ key: "reach" }, { key: "followers" }])).toMatch(/add up each day's figure\. Followers is the latest count/);
    expect(totalsNote([{ key: "views" }])).toMatch(/counts twice/);
    expect(totalsNote([{ key: "comments" }, { key: "followers" }])).toBeNull();
  });

  it("lets only plain https pictures through", () => {
    expect(httpsOnly("https://cdn.example/a.jpg")).toBe("https://cdn.example/a.jpg");
    expect(httpsOnly("http://cdn.example/a.jpg")).toBeNull();
    expect(httpsOnly("javascript:alert(1)")).toBeNull();
    expect(httpsOnly("data:image/png;base64,AAAA")).toBeNull();
    expect(httpsOnly("not a url")).toBeNull();
    expect(httpsOnly(null)).toBeNull();
  });
});

describe("a small change is never No change", () => {
  it("writes the difference when the API calls it flat but the figures differ", () => {
    const small = deltaTrend({ change_pct: -0.2, direction: "flat", tone: "neutral", current: 1054, previous: 1056, format: "count" }, "last week");
    expect(small).toMatchObject({ direction: "down", text: "−2 (−0.2%)" });
    expect(deltaTrend({ change_pct: 0, direction: "flat", tone: "neutral", current: 5, previous: 5, format: "count" }, "last week")?.text).toBe("No change");
  });
});
