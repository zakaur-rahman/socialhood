import { describe, expect, it } from "vitest";

import { addDays, checkCustom, choiceOf, daysBetween, parseStoredRange, storedRange } from "./range";

const today = "2026-10-01";

describe("Home's period (C-065)", () => {
  it("counts local days, both ends included", () => {
    expect(daysBetween("2026-09-19", "2026-09-30")).toBe(12);
    expect(daysBetween("2026-10-01", "2026-10-01")).toBe(1);
    expect(addDays("2026-10-01", -6)).toBe("2026-09-25");
    expect(addDays("2026-02-28", 1)).toBe("2026-03-01");
  });

  it("takes a custom range the API will take", () => {
    expect(checkCustom("2026-09-19", "2026-09-30", today)).toBeNull();
    expect(checkCustom("2026-10-01", "2026-10-01", today)).toBeNull();
    expect(checkCustom("2026-07-04", "2026-10-01", today)).toBeNull(); // 90 days
  });

  it("says which date is wrong", () => {
    expect(checkCustom("2026-09-30", "2026-09-19", today)).toEqual({
      from: "Pick a start date on or before the end date.",
    });
    expect(checkCustom("2026-09-19", "2026-10-02", today)).toEqual({ to: "Pick a date up to today." });
    expect(checkCustom("2026-07-03", "2026-10-01", today)).toEqual({ from: "Pick at most 90 days." }); // 91
    expect(checkCustom("", "", today)).toEqual({ from: "Pick a start date.", to: "Pick an end date." });
    expect(checkCustom("2026-02-30", "2026-03-01", today)).toEqual({ from: "Pick a start date." });
  });

  it("remembers the choice, and falls back to 7 days when a stored one no longer holds", () => {
    expect(storedRange({ range: "30d" })).toBe("30d");
    expect(storedRange({ from: "2026-09-19", to: "2026-09-30" })).toBe("custom:2026-09-19:2026-09-30");
    expect(parseStoredRange("30d", today)).toEqual({ range: "30d" });
    expect(parseStoredRange("custom:2026-09-19:2026-09-30", today)).toEqual({ from: "2026-09-19", to: "2026-09-30" });
    expect(parseStoredRange("custom:2026-09-30:2026-09-19", today)).toEqual({ range: "7d" });
    expect(parseStoredRange("90d", today)).toEqual({ range: "7d" });
    expect(choiceOf({ range: "7d" })).toBe("7d");
    expect(choiceOf({ from: "2026-09-19", to: "2026-09-30" })).toBe("custom");
  });
});
