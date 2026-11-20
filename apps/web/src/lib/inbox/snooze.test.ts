import { describe, expect, it } from "vitest";

import { snoozeLimits, snoozePresets } from "./snooze";

const at = (presets: ReturnType<typeof snoozePresets>, key: string) => presets.find((p) => p.key === key)?.at.toISOString();

describe("snoozePresets (GR-45)", () => {
  it("offers later today, tomorrow 9:00 and next Monday 9:00 in the workspace's zone", () => {
    // Wednesday 2026-11-18 10:00 in Kolkata (UTC+5:30) is 04:30 UTC.
    const presets = snoozePresets(new Date("2026-11-18T04:30:00Z"), "Asia/Kolkata");
    expect(presets.map((p) => p.key)).toEqual(["later", "tomorrow", "next_week"]);
    expect(at(presets, "later")).toBe("2026-11-18T07:30:00.000Z"); // 13:00
    expect(at(presets, "tomorrow")).toBe("2026-11-19T03:30:00.000Z"); // Thu 09:00
    expect(at(presets, "next_week")).toBe("2026-11-23T03:30:00.000Z"); // Mon 09:00
  });

  it("drops later today once three hours on is tomorrow", () => {
    // 22:00 in Kolkata.
    const presets = snoozePresets(new Date("2026-11-18T16:30:00Z"), "Asia/Kolkata");
    expect(presets.map((p) => p.key)).toEqual(["tomorrow", "next_week"]);
  });

  it("next week is seven days on from a Monday and tomorrow from a Sunday", () => {
    expect(at(snoozePresets(new Date("2026-11-16T04:30:00Z"), "Asia/Kolkata"), "next_week")).toBe("2026-11-23T03:30:00.000Z");
    expect(at(snoozePresets(new Date("2026-11-22T04:30:00Z"), "Asia/Kolkata"), "next_week")).toBe("2026-11-23T03:30:00.000Z");
  });

  it("holds the API's limits", () => {
    const now = new Date("2026-11-18T04:30:00Z");
    const { min, max } = snoozeLimits(now);
    expect(min.getTime() - now.getTime()).toBe(60_000);
    expect(max.getTime() - now.getTime()).toBeLessThan(90 * 86_400_000);
  });
});
