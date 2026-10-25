import { describe, expect, it } from "vitest";

import { nearestIndex, niceScale, runsOf, xPercent, yPercent } from "./scale";

describe("niceScale", () => {
  it("starts at zero with round ticks and a top at or above the data", () => {
    expect(niceScale(9)).toEqual({ top: 10, ticks: [0, 5, 10] });
    const { top, ticks } = niceScale(1204);
    expect(ticks[0]).toBe(0);
    expect(top).toBeGreaterThanOrEqual(1204);
    expect(ticks.at(-1)).toBe(top);
  });

  it("pins a share to 0-100", () => {
    expect(niceScale(37, 100)).toEqual({ top: 100, ticks: [0, 50, 100] });
  });

  it("has a scale for nothing at all", () => {
    expect(niceScale(0).top).toBeGreaterThan(0);
  });
});

describe("positions", () => {
  it("insets the ends and centres a single point", () => {
    expect(xPercent(0, 5)).toBe(3);
    expect(xPercent(4, 5)).toBe(97);
    expect(xPercent(0, 1)).toBe(50);
  });

  it("puts zero on the baseline and the top at the top", () => {
    expect(yPercent(0, 10)).toBe(100);
    expect(yPercent(10, 10)).toBe(0);
  });

  it("finds the point nearest to the pointer", () => {
    expect(nearestIndex(0, 8)).toBe(0);
    expect(nearestIndex(1, 8)).toBe(7);
    expect(nearestIndex(0.5, 5)).toBe(2);
  });
});

describe("runsOf", () => {
  it("breaks the line at a gap, so nothing is drawn through it", () => {
    const runs = runsOf([3, null, 4, 6], 10);
    expect(runs.map((run) => run.length)).toEqual([1, 2]);
  });

  it("has nothing for a series with no values", () => {
    expect(runsOf([null, undefined], 10)).toEqual([]);
  });
});
