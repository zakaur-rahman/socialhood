import { describe, expect, it } from "vitest";

import {
  addDays,
  agendaDayLabel,
  instantAt,
  minutesOfDay,
  rangeFor,
  rangeLabel,
  shiftAnchor,
  snapMinutes,
  startOfWeek,
  todayKey,
  tooSoon,
  weekdayIndex,
  withTimeOf,
} from "./dates";

const TZ = "Asia/Kolkata";

describe("calendar dates (UX-SCR-04)", () => {
  it("numbers weekdays from Monday, as posting slots do", () => {
    expect(weekdayIndex("2026-09-28")).toBe(0); // Monday
    expect(weekdayIndex("2026-10-04")).toBe(6); // Sunday
    expect(startOfWeek("2026-10-04")).toBe("2026-09-28");
    expect(addDays("2026-09-30", 3)).toBe("2026-10-03");
  });

  it("shows Monday to Sunday for a week", () => {
    const range = rangeFor("week", "2026-09-30");
    expect(range.from).toBe("2026-09-28");
    expect(range.to).toBe("2026-10-04");
    expect(range.days).toHaveLength(7);
  });

  it("shows six whole weeks for a month, the API's 42-day limit", () => {
    const range = rangeFor("month", "2026-09-29");
    expect(range.from).toBe("2026-08-31");
    expect(range.to).toBe("2026-10-11");
    expect(range.days).toHaveLength(42);
  });

  it("moves by a week or a month", () => {
    expect(shiftAnchor("week", "2026-09-29", 1)).toBe("2026-10-06");
    expect(shiftAnchor("month", "2026-01-31", 1)).toBe("2026-02-01");
    expect(shiftAnchor("month", "2026-01-15", -1)).toBe("2025-12-01");
  });

  it("labels ranges", () => {
    expect(rangeLabel("week", "2026-09-29", "2026-09-29")).toBe("28 Sep – 4 Oct");
    expect(rangeLabel("week", "2026-10-14", "2026-09-29")).toBe("12 – 18 Oct");
    expect(rangeLabel("week", "2026-12-31", "2026-09-29")).toBe("28 Dec 2026 – 3 Jan 2027");
    expect(rangeLabel("month", "2026-09-29", "2026-09-29")).toBe("September 2026");
    expect(agendaDayLabel("2026-09-29", "2026-09-29")).toBe("Today · Tue 29 Sep");
    expect(agendaDayLabel("2026-09-30", "2026-09-29")).toBe("Tomorrow · Wed 30 Sep");
    expect(agendaDayLabel("2026-10-02", "2026-09-29")).toBe("Fri 2 Oct");
  });

  it("converts between wall-clock times in the workspace zone and instants", () => {
    expect(instantAt("2026-09-30", 18 * 60, TZ).toISOString()).toBe("2026-09-30T12:30:00.000Z");
    expect(minutesOfDay("2026-09-30T12:30:00Z", TZ)).toBe(18 * 60);
    expect(todayKey(new Date("2026-09-29T20:00:00Z"), TZ)).toBe("2026-09-30"); // 01:30 the next day
    // A Month move keeps the time of day.
    expect(withTimeOf("2026-10-02", "2026-09-29T06:30:00Z", TZ).toISOString()).toBe("2026-10-02T06:30:00.000Z");
  });

  it("snaps a drag to 15 minutes, inside the day", () => {
    expect(snapMinutes(18 * 60 + 14)).toBe(18 * 60);
    expect(snapMinutes(18 * 60 + 15)).toBe(18 * 60 + 15);
    expect(snapMinutes(-20)).toBe(0);
    expect(snapMinutes(24 * 60 + 5)).toBe(23 * 60 + 45);
  });

  it("refuses times less than 5 minutes away (FR-PUB-08)", () => {
    const now = new Date("2026-09-29T04:30:00Z");
    expect(tooSoon(new Date("2026-09-29T04:34:00Z"), now)).toBe(true);
    expect(tooSoon(new Date("2026-09-29T04:35:00Z"), now)).toBe(false);
  });
});
