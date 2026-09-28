import { describe, expect, it } from "vitest";

import { dayKey, formatDay, formatDayTime, formatTime, toZonedInputs, zonedToDate } from "./tz";

const kolkata = "Asia/Kolkata"; // UTC+5:30, no DST
const newYork = "America/New_York";

describe("workspace-timezone dates (UX-INB-06)", () => {
  const now = new Date("2026-09-28T12:00:00Z"); // 17:30 in Kolkata

  it("labels days: today, yesterday, this year, earlier years", () => {
    expect(formatDay("2026-09-28T04:00:00Z", kolkata, now)).toBe("Today");
    expect(formatDay("2026-09-27T10:00:00Z", kolkata, now)).toBe("Yesterday");
    expect(formatDay("2026-03-02T10:00:00Z", kolkata, now)).toBe("Mon 2 Mar");
    expect(formatDay("2025-03-03T10:00:00Z", kolkata, now)).toBe("3 Mar 2025");
  });

  it("uses the zone's calendar day, not UTC's", () => {
    // 20:00 UTC on the 27th is already the 28th in Kolkata.
    expect(dayKey("2026-09-27T20:00:00Z", kolkata)).toBe("2026-09-28");
    expect(formatDay("2026-09-27T20:00:00Z", kolkata, now)).toBe("Today");
  });

  it("formats times and day-times", () => {
    expect(formatTime("2026-09-28T13:00:00Z", kolkata)).toBe("18:30");
    expect(formatDayTime("2026-09-29T03:30:00Z", kolkata, now)).toBe("Tomorrow 09:00");
  });

  it("falls back to UTC for an unknown zone", () => {
    expect(formatTime("2026-09-28T13:00:00Z", "Not/AZone")).toBe("13:00");
  });
});

describe("zonedToDate (F-10 schedule inputs)", () => {
  it("reads wall-clock inputs in the zone", () => {
    expect(zonedToDate("2026-09-28", "18:30", kolkata)?.toISOString()).toBe("2026-09-28T13:00:00.000Z");
    expect(zonedToDate("2026-07-01", "09:00", newYork)?.toISOString()).toBe("2026-07-01T13:00:00.000Z"); // EDT
    expect(zonedToDate("2026-12-01", "09:00", newYork)?.toISOString()).toBe("2026-12-01T14:00:00.000Z"); // EST
  });

  it("round-trips with toZonedInputs", () => {
    const instant = new Date("2026-11-01T15:45:00Z");
    const inputs = toZonedInputs(instant, newYork);
    expect(zonedToDate(inputs.date, inputs.time, newYork)?.toISOString()).toBe(instant.toISOString());
  });

  it("rejects malformed input", () => {
    expect(zonedToDate("", "18:30", kolkata)).toBeNull();
    expect(zonedToDate("2026-09-28", "6pm", kolkata)).toBeNull();
  });
});
