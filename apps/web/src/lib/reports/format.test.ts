import { describe, expect, it } from "vitest";

import type { ReportMetric } from "@/lib/api/types";

import { changeText, dayLabel, formatMetric, parseWeekParam, previousLine, reportTrend, weekLabel } from "./format";

function metric(values: Partial<ReportMetric> = {}): ReportMetric {
  return {
    key: "messages_received",
    label: "Messages received",
    unit: "count",
    value: 142,
    previous: 120,
    change_pct: 18.3,
    change_points: null,
    direction: "up",
    lower_is_better: false,
    series: [],
    ...values,
  };
}

describe("the week in the address", () => {
  it("accepts a plain date and nothing else", () => {
    expect(parseWeekParam("2026-09-21")).toBe("2026-09-21");
    expect(parseWeekParam("21 Sep")).toBeNull();
    expect(parseWeekParam("2026-09-21&x=1")).toBeNull();
    expect(parseWeekParam("")).toBeNull();
    expect(parseWeekParam(null)).toBeNull();
  });

  it("names a week by its Monday", () => {
    expect(dayLabel("2026-09-21")).toBe("21 Sep");
    expect(weekLabel("2026-09-21")).toBe("Week of 21 Sep");
  });
});

describe("formatMetric", () => {
  it("formats by unit and shows a dash where there is no figure", () => {
    expect(formatMetric("count", 1204)).toBe("1,204");
    expect(formatMetric("count", 0)).toBe("0");
    expect(formatMetric("percent", 62.5)).toBe("62.5%");
    expect(formatMetric("seconds", 754)).toBe("13 min");
    expect(formatMetric("count", null)).toBe("—");
    expect(formatMetric("percent", undefined)).toBe("—");
  });
});

describe("reportTrend", () => {
  it("shows the API's percent change and never works one out", () => {
    const trend = reportTrend(metric());
    expect(trend).toMatchObject({ direction: "up", good: true, text: "+18.3%" });
    expect(trend?.words).toBe("up 18.3% from the week before");
    expect(reportTrend(metric({ change_pct: -9, direction: "down" }))).toMatchObject({ direction: "down", good: false, text: "−9%" });
  });

  it("shows a share's change in points", () => {
    const trend = reportTrend(metric({ unit: "percent", change_pct: null, change_points: -2.6, direction: "down" }));
    expect(trend).toMatchObject({ direction: "down", good: false, text: "−2.6 pts" });
    expect(trend?.words).toBe("down 2.6 percentage points from the week before");
  });

  it("a faster first response is good news", () => {
    const trend = reportTrend(metric({ key: "median_first_response_s", unit: "seconds", change_pct: -50, direction: "down", lower_is_better: true }));
    expect(trend).toMatchObject({ direction: "down", good: true });
  });

  it("is New against a previous zero, No change when flat, and nothing when a side is unknown", () => {
    expect(reportTrend(metric({ previous: 0, change_pct: null, direction: "up" }))).toMatchObject({ text: "New", good: true });
    expect(reportTrend(metric({ change_pct: 0.2, direction: "flat" }))).toMatchObject({ text: "No change", good: null });
    expect(reportTrend(metric({ value: null, change_pct: null, direction: null }))).toBeNull();
  });
});

describe("previousLine", () => {
  it("says what the week before was, or that there is no data", () => {
    expect(previousLine(metric())).toBe("Week before: 120");
    expect(previousLine(metric({ previous: 0 }))).toBe("Week before: 0");
    expect(previousLine(metric({ previous: null }))).toBe("Week before: no data");
  });
});

describe("changeText", () => {
  it("is the tile's change as text, or null when a side is unknown", () => {
    expect(changeText({ change_pct: 12.5, direction: "up" })).toBe("+12.5%");
    expect(changeText({ change_pct: null, direction: "up" })).toBe("New");
    expect(changeText({ change_pct: null, direction: null })).toBeNull();
  });
});
