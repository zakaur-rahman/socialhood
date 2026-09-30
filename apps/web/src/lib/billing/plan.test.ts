import { describe, expect, it } from "vitest";

import { formatPrice, inferEntitlement, planIncludes, planOffers, upgradeCopy } from "@/lib/copy";
import { billingState } from "@/test/api";

import { canCheckout, daysUntil, meterViews, planHighlights, planStatus, priceOf } from "./plan";

const now = new Date("2026-09-30T06:00:00Z");
const tz = "Asia/Kolkata";
const inr = { plan: "pro" as const, amount_minor: 99_900, currency: "INR", interval: "month" as const };

describe("the plan card's status (UX-SCR-07, F-15, FR-BIL-06)", () => {
  it("trial: days left and what follows", () => {
    const status = planStatus(
      billingState({ status: "trialing", trial_ends_at: "2026-10-03T06:00:00Z", prices: [inr] }),
      tz,
      now,
    );
    expect(status.badge).toEqual({ label: "Trial", tone: "brand" });
    expect(status.line).toBe("Trial ends on 3 Oct · 3 days left. Then ₹999 a month.");
    expect(status.cancellable).toBe(true);
  });

  it("the trial's last day, and a cancelled trial", () => {
    expect(planStatus(billingState({ status: "trialing", trial_ends_at: "2026-10-01T02:00:00Z" }), tz, now).line).toBe(
      "Trial ends on 1 Oct · last day.",
    );
    const cancelled = planStatus(
      billingState({ status: "trialing", trial_ends_at: "2026-10-03T06:00:00Z", cancel_at_period_end: true }),
      tz,
      now,
    );
    expect(cancelled.line).toBe("Trial ends on 3 Oct · 3 days left. It won't renew.");
    expect(cancelled.resumable).toBe(true);
  });

  it("active: renewal date and price", () => {
    const status = planStatus(billingState({ current_period_end: "2026-10-31T18:30:00Z", prices: [inr] }), tz, now);
    expect(status.line).toBe("Renews on 1 Nov · ₹999 a month"); // midnight in Kolkata
    expect(status.cancellable).toBe(true);
    expect(status.resumable).toBe(false);
  });

  it("cancelling at period end: Pro until the date, with Resume", () => {
    const status = planStatus(billingState({ cancel_at_period_end: true, current_period_end: "2026-10-20T06:00:00Z" }), tz, now);
    expect(status.badge.label).toBe("Cancelling");
    expect(status.line).toBe("Pro until 20 Oct. Then the workspace moves to Free.");
    expect(status.resumable).toBe(true);
    expect(status.cancellable).toBe(false);
  });

  it("on hold: the grace end", () => {
    const status = planStatus(billingState({ status: "on_hold", grace_until: "2026-10-02T06:00:00Z" }), tz, now);
    expect(status.badge).toEqual({ label: "On hold", tone: "danger" });
    expect(status.line).toBe("Update your payment method by 2 Oct to keep Pro.");
  });

  it("free and expired", () => {
    expect(planStatus(billingState({ plan: "free", status: "free" }), tz, now).plan).toBe("Free");
    expect(planStatus(billingState({ plan: "free", status: "expired" }), tz, now).line).toMatch(/Nothing was deleted/);
  });

  it("checkout only without a paid plan (409 otherwise)", () => {
    expect(canCheckout(billingState({ plan: "free", status: "free" }))).toBe(true);
    expect(canCheckout(billingState({ plan: "free", status: "expired" }))).toBe(true);
    expect(canCheckout(billingState({ status: "trialing" }))).toBe(false);
    expect(canCheckout(billingState({ status: "on_hold" }))).toBe(false);
  });

  it("days left round up", () => {
    expect(daysUntil("2026-10-01T12:00:00Z", now)).toBe(2);
    expect(daysUntil("2026-09-29T12:00:00Z", now)).toBe(0);
  });
});

describe("usage meters (FR-BIL-05)", () => {
  it("one per limited metric, labelled, with the monthly reset", () => {
    const views = meterViews(
      [
        { metric: "ai_credits", used: 120, limit: 200, period_end: "2026-10-01" },
        { metric: "scheduled_posts", used: 3, limit: 10, period_end: "2026-10-01T00:00:00Z" },
        { metric: "knowledge_characters", used: 1240, limit: 200_000 },
        { metric: "active_automations", used: 2, limit: null },
        { metric: "pending_scheduled_messages", used: 4, limit: 20 },
      ],
      tz,
      now,
    );
    expect(views.map((v) => [v.label, v.unit, v.note])).toEqual([
      ["AI credits", "credits", "Resets on 1 Oct"],
      ["Scheduled posts", "posts", "Resets on 1 Oct"],
      ["Knowledge", "characters", null],
      ["Scheduled messages", "waiting", null],
    ]);
  });

  it("an unknown metric still gets a readable label", () => {
    expect(meterViews([{ metric: "video_minutes", used: 1, limit: 5 }], tz, now)[0].label).toBe("Video minutes");
  });
});

describe("prices and plans", () => {
  it("formats minor units in the plan's currency", () => {
    expect(formatPrice(inr)).toBe("₹999");
    expect(formatPrice({ amount_minor: 1050, currency: "USD" })).toBe("$10.50");
    expect(formatPrice({ amount_minor: 1200, currency: "JPY" })).toBe("¥1,200");
  });

  it("the Pro price comes from the billing state, else the plan list", () => {
    expect(priceOf("pro", billingState({ prices: [inr] }))).toEqual(inr);
    expect(priceOf("pro", billingState({ prices: [] }), [{ plan: "pro", available: true, entitlements: [], price: inr, trial_days: 7 }])).toEqual(inr);
    expect(priceOf("pro", billingState({ prices: [] }))).toBeNull();
  });

  it("plan highlights read the entitlements", () => {
    expect(
      planHighlights([
        { key: "accounts_per_platform", value: 3 },
        { key: "active_automations", value: null },
        { key: "ai_credits_monthly", value: 5000 },
        { key: "knowledge_characters", value: 5_000_000 },
        { key: "ai_modes", value: ["off", "suggest", "auto"] },
        { key: "ai_reply_automations", value: false },
      ]),
    ).toEqual([
      "3 accounts per platform",
      "Unlimited automations",
      "5,000 AI credits a month",
      "5M characters of knowledge",
      "AI Auto mode",
    ]);
  });
});

describe("upgrade dialog copy (§4.7, F-15)", () => {
  it("entitlement_required: {Feature} is part of Pro", () => {
    expect(upgradeCopy({ code: "entitlement_required", entitlement: "ai_modes" }).title).toBe("Auto mode is part of Pro");
    expect(upgradeCopy({ code: "entitlement_required", entitlement: "ai_reply_automations" }).title).toBe(
      "AI replies in automations is part of Pro",
    );
    expect(upgradeCopy({ code: "entitlement_required", detail: "Comment insights is part of Pro." }).title).toBe(
      "Comment insights is part of Pro",
    );
  });

  it("quota_exceeded names the plan and the limit", () => {
    const copy = upgradeCopy({ code: "quota_exceeded", entitlement: "active_automations", limit: 3 }, { plan: "free" });
    expect(copy).toEqual({ title: "Automation limit reached", body: "Free includes 3 active automations." });
    expect(upgradeCopy({ code: "quota_exceeded", entitlement: "scheduled_posts_monthly", limit: 10 }, { plan: "free" }).body).toBe(
      "Free includes 10 scheduled posts a month.",
    );
    expect(upgradeCopy({ code: "quota_exceeded", entitlement: "accounts_per_platform", limit: 1 }).body).toBe(
      "Your plan includes 1 account per platform.",
    );
    expect(upgradeCopy({ code: "quota_exceeded", entitlement: "knowledge_characters", limit: 200_000 }, { plan: "free" }).body).toBe(
      "Free includes 200,000 characters of knowledge.",
    );
  });

  it("AI credits say when they reset", () => {
    expect(
      upgradeCopy({ code: "quota_exceeded", entitlement: "ai_credits_monthly", limit: 200 }, { resetsOn: "2026-10-01", now }).body,
    ).toBe("You've used all 200 AI credits for this month. They reset on 1 Oct.");
  });

  it("falls back to the API's detail", () => {
    expect(upgradeCopy({ code: "quota_exceeded", detail: "Your plan includes 20 widgets." })).toEqual({
      title: "Plan limit reached",
      body: "Your plan includes 20 widgets.",
    });
  });

  it("what Pro offers instead", () => {
    expect(planOffers("active_automations", 50, "pro")).toBe("Pro includes 50 active automations.");
    expect(planOffers("scheduled_posts_monthly", null, "max")).toBe("Max has no limit on scheduled posts.");
    expect(planIncludes("unknown_key", 3, "free")).toBeNull();
  });

  it("older 402s without a key are recognised by their detail", () => {
    expect(inferEntitlement("Auto mode is part of Pro.")).toBe("ai_modes");
    expect(inferEntitlement("Your plan includes 3 active automations.")).toBe("active_automations");
    expect(inferEntitlement("You've used all 5,000 AI credits for this month.")).toBe("ai_credits_monthly");
    expect(inferEntitlement("Something else")).toBeNull();
  });
});
