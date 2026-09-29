import { describe, expect, it } from "vitest";

import { billingState } from "@/test/api";

import { creditsUsage, usageView } from "./usage";

describe("creditsUsage", () => {
  it("reads the AI credits meter; loading, unlimited or missing billing show nothing", () => {
    expect(creditsUsage(undefined, true)).toBe("loading");
    expect(creditsUsage(billingState(), false)).toEqual({ used: 120, limit: 5000, plan: "pro" });
    expect(creditsUsage(billingState({ usage: [{ metric: "ai_credits", used: 9, limit: null }] }), false)).toBeNull();
    expect(creditsUsage(billingState({ usage: [] }), false)).toBeNull();
    expect(creditsUsage(undefined, false)).toBeNull();
  });
});

describe("usageView: who sees the meter, and when it offers Upgrade", () => {
  const cases = [
    // plan, used of 100, role → tone, upgrade
    ["free", 10, "owner", "normal", true],
    ["free", 10, "admin", "normal", true],
    ["pro", 79, "owner", "normal", false],
    ["pro", 80, "owner", "warning", true],
    ["pro", 100, "admin", "danger", true],
    ["max", 95, "owner", "warning", false],
  ] as const;

  it.each(cases)("%s at %i%% for an %s: %s, upgrade %s", (plan, used, role, tone, upgrade) => {
    expect(usageView({ used, limit: 100, plan }, role)).toMatchObject({ kind: "meter", tone, upgrade });
  });

  it("is hidden for agents and when there is nothing to show", () => {
    expect(usageView({ used: 99, limit: 100, plan: "free" }, "agent")).toEqual({ kind: "hidden" });
    expect(usageView("loading", "agent")).toEqual({ kind: "hidden" });
    expect(usageView(null, "owner")).toEqual({ kind: "hidden" });
    expect(usageView(undefined, "owner")).toEqual({ kind: "hidden" });
    expect(usageView("loading", "owner")).toEqual({ kind: "loading" });
  });

  it("rounds the share down and caps it at 100 %", () => {
    expect(usageView({ used: 499, limit: 500, plan: "pro" }, "owner")).toMatchObject({ percent: 99, tone: "warning" });
    expect(usageView({ used: 700, limit: 500, plan: "pro" }, "owner")).toMatchObject({ percent: 100, tone: "danger" });
  });
});
