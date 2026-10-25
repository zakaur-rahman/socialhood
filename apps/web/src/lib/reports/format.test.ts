import { describe, expect, it } from "vitest";

import type { ReportMetric } from "@/lib/api/types";

import { changeText, dayLabel, formatAxis, formatMetric, gapNote, insightLine, isIdle, parseWeekParam, previousLine, reportTrend, weekLabel } from "./format";

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
    expect(reportTrend(metric({ value: 120, previous: 120, change_pct: 0, direction: "flat" }))).toMatchObject({ text: "No change", good: null });
    expect(reportTrend(metric({ value: null, change_pct: null, direction: null }))).toBeNull();
  });
});

describe("a change that is small but not zero (never No change)", () => {
  it("writes the absolute change and a percentage with enough precision", () => {
    const followers = metric({ value: 1054, previous: 1056, change_pct: -0.2, direction: "flat" });
    expect(reportTrend(followers)).toMatchObject({ direction: "down", text: "−2 (−0.2%)", good: null });
    expect(reportTrend(metric({ value: 100000, previous: 99999, change_pct: 0, direction: "flat" }))?.text).toBe("+1 (<0.1%)");
  });

  it("writes a share in points and a time in its own unit", () => {
    expect(reportTrend(metric({ unit: "percent", value: 88.7, previous: 88.4, change_pct: null, change_points: 0.3, direction: "flat" }))?.text).toBe("+0.3 pts");
    expect(reportTrend(metric({ unit: "seconds", value: 3590, previous: 3600, change_pct: -0.3, direction: "flat" }))?.text).toBe("−10 s (−0.3%)");
  });

  it("is No change only for values that are exactly equal", () => {
    expect(reportTrend(metric({ value: 5, previous: 5, change_pct: 0, direction: "flat" }))?.text).toBe("No change");
  });

  it("is the same in the tooltip", () => {
    expect(changeText({ value: 1054, previous: 1056, change_pct: -0.2, direction: "flat" })).toBe("−2 (−0.2%)");
  });
});

describe("axes, idle metrics and gaps", () => {
  it("keeps duration axis labels short enough for one line", () => {
    expect(formatAxis("seconds", 45)).toBe("45s");
    expect(formatAxis("seconds", 28 * 3600)).toBe("1d 4h");
    expect(formatAxis("seconds", 5 * 3600)).toBe("5h");
    expect(formatAxis("count", 1500)).toBe("1,500");
  });

  it("calls a count idle when every week is zero or empty, and a rate only when every week is empty", () => {
    expect(isIdle("count", [{ value: 0 }, { value: null }])).toBe(true);
    expect(isIdle("count", [{ value: 0 }, { value: 3 }])).toBe(false);
    expect(isIdle("percent", [{ value: 0 }])).toBe(false);
    expect(isIdle("percent", [{ value: null }])).toBe(true);
  });

  it("says where a line starts, or how many weeks are missing", () => {
    const weeks = (values: (number | null)[]) => values.map((value, i) => ({ week_start: `2026-08-${String(3 + i * 7).padStart(2, "0")}`, value }));
    expect(gapNote(weeks([null, null, 4, 5]))).toBe("No data before 17 Aug");
    expect(gapNote(weeks([1, null, 4, 5]))).toBe("1 week without data");
    expect(gapNote(weeks([null, null]))).toBe("2 weeks without data");
    expect(gapNote(weeks([1, 2]))).toBeNull();
  });

  it("writes an insight's week before and the days behind it as one line", () => {
    const base = { unit: "count" as const, previous: 1056, daysTotal: 7 };
    expect(insightLine({ ...base, daysNow: 2, daysBefore: 2 })).toBe("Week before: 1,056 · readings on 2 of 7 days (both weeks)");
    expect(insightLine({ ...base, daysNow: 5, daysBefore: 7 })).toBe("Week before: 1,056 · readings on 5 of 7 days, 7 of 7 days the week before");
    expect(insightLine({ ...base, daysNow: 7, daysBefore: 7 })).toBe("Week before: 1,056");
    expect(insightLine({ ...base, previous: null, daysNow: 7, daysBefore: null })).toBe("Week before: no data");
    expect(insightLine({ ...base, unavailable: "insights_not_granted" })).toBe("Not available: this account gives no insights");
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
