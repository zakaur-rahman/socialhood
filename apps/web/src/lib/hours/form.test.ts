import { describe, expect, it } from "vitest";

import type { BusinessHours } from "@/lib/api/types";

import { displayEnd, localProblem, parseEnd, summary, toBody, toForm } from "./form";

const saved: BusinessHours = {
  social_account_id: null,
  configured: true,
  enabled: true,
  days: [0, 1, 2, 3, 4, 5, 6].map((day) => ({ day, ranges: day === 2 ? [{ start: "10:00", end: "24:00" }] : [] })),
  away_enabled: true,
  away_message: "Back at 9.",
  auto_mode: "out_of_hours",
  open_now: false,
};

describe("toForm and toBody (GR-22)", () => {
  it("never-saved hours are off, with a working week ready to switch on", () => {
    const form = toForm(null);
    expect(form.enabled).toBe(false);
    expect(form.days.map((d) => d.ranges.length)).toEqual([1, 1, 1, 1, 1, 0, 0]);
    expect(form.days[0].ranges[0]).toEqual({ start: "09:00", end: "17:00" });
    expect(toForm({ ...saved, configured: false, enabled: false }).enabled).toBe(false);
  });

  it("saved hours come back as they were saved", () => {
    const form = toForm(saved);
    expect(form).toMatchObject({ enabled: true, away_enabled: true, away_message: "Back at 9.", auto_mode: "out_of_hours" });
    expect(form.days.map((d) => d.ranges.length)).toEqual([0, 0, 1, 0, 0, 0, 0]);
  });

  it("the request has all seven days in order and no empty message", () => {
    const body = toBody({ ...toForm(saved), away_message: "   " });
    expect(body.days.map((d) => d.day)).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(body.away_message).toBeNull();
    expect(body.days[2].ranges).toEqual([{ start: "10:00", end: "24:00" }]);
  });
});

describe("midnight (GR-22)", () => {
  it("a closing time of 24:00 is shown and typed as 00:00", () => {
    expect(displayEnd("24:00")).toBe("00:00");
    expect(displayEnd("17:00")).toBe("17:00");
    expect(parseEnd("00:00")).toBe("24:00");
    expect(parseEnd("23:59")).toBe("23:59");
  });
});

describe("localProblem", () => {
  it("asks for an opening time when the hours are on with none", () => {
    const form = toForm(saved);
    expect(localProblem(form)).toBeNull();
    expect(localProblem({ ...form, days: form.days.map((d) => ({ ...d, ranges: [] })) })).toMatch(/at least one opening time/);
    expect(localProblem({ ...form, enabled: false, days: form.days.map((d) => ({ ...d, ranges: [] })) })).toBeNull();
  });

  it("asks for the away message's words", () => {
    expect(localProblem({ ...toForm(saved), away_message: " " })).toMatch(/Write the message/);
  });
});

describe("summary", () => {
  it("groups days with the same hours", () => {
    expect(summary(toForm(null).days)).toBe("Mon to Fri 09:00 to 17:00");
    expect(summary(toForm(saved).days)).toBe("Wed 10:00 to midnight");
    expect(summary([])).toBe("Closed all week");
  });

  it("does not group days that are apart or differ", () => {
    const days = toForm(null).days.map((d) => (d.day === 2 ? { ...d, ranges: [{ start: "10:00", end: "12:00" }] } : d));
    expect(summary(days)).toBe("Mon to Tue 09:00 to 17:00; Wed 10:00 to 12:00; Thu to Fri 09:00 to 17:00");
  });
});
