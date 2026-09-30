import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { describe, expect, it, vi } from "vitest";

import { billingState } from "@/test/api";

import { BannerSlot, billingBanners } from "./BannerSlot";

const now = new Date("2026-09-30T06:00:00Z");
const base = { timeZone: "Asia/Kolkata", billingHref: "/w/maple/settings/billing" as Route, now };

describe("payment problem banner (FR-BIL-06, F-15, UX-SH-04)", () => {
  it("on hold: the owner sees the grace end and Manage billing opens the portal; no dismiss", async () => {
    const onManageBilling = vi.fn();
    const banners = billingBanners(billingState({ status: "on_hold", grace_until: "2026-10-03T06:00:00Z" }), {
      ...base,
      role: "owner",
      onManageBilling,
    });
    render(<BannerSlot banners={banners} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Payment failed. Update your payment method by 3 Oct to keep Pro",
    );
    await userEvent.click(screen.getByRole("button", { name: "Manage billing" }));
    expect(onManageBilling).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
  });

  it("admins and agents can't fix billing, so they don't see it", () => {
    const onHold = billingState({ status: "on_hold", grace_until: "2026-10-03T06:00:00Z" });
    expect(billingBanners(onHold, { ...base, role: "admin", onManageBilling: vi.fn() })).toEqual([]);
    expect(billingBanners(onHold, { ...base, role: "agent", onManageBilling: vi.fn() })).toEqual([]);
  });

  it("nothing while active, on Free or before billing loads", () => {
    expect(billingBanners(billingState(), { ...base, role: "owner", onManageBilling: vi.fn() })).toEqual([]);
    expect(billingBanners(billingState({ plan: "free", status: "free" }), { ...base, role: "owner", onManageBilling: vi.fn() })).toEqual([]);
    expect(billingBanners(undefined, { ...base, role: "owner", onManageBilling: vi.fn() })).toEqual([]);
  });
});

describe("trial ending reminder", () => {
  const trial = (ends: string, extra = {}) =>
    billingState({
      status: "trialing",
      trial_ends_at: ends,
      prices: [{ plan: "pro", amount_minor: 99_900, currency: "INR", interval: "month" }],
      ...extra,
    });

  it("in the last 3 days: when it ends and what follows, dismissible", async () => {
    const onDismissTrial = vi.fn();
    const banners = billingBanners(trial("2026-10-02T06:00:00Z"), {
      ...base,
      role: "owner",
      onManageBilling: vi.fn(),
      onDismissTrial,
    });
    render(<BannerSlot banners={banners} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Your Pro trial ends in 2 days, on 2 Oct. Pro then continues at ₹999 a month",
    );
    expect(screen.getByRole("link", { name: "View billing" })).toHaveAttribute("href", "/w/maple/settings/billing");
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismissTrial).toHaveBeenCalledWith("2026-10-02T06:00:00Z");
  });

  it("a cancelled trial says the workspace moves to Free, with Keep Pro", () => {
    const [banner] = billingBanners(trial("2026-10-01T03:00:00Z", { cancel_at_period_end: true }), {
      ...base,
      role: "owner",
      onManageBilling: vi.fn(),
    });
    expect(banner.message).toBe("Your Pro trial ends tomorrow, on 1 Oct. The workspace moves to Free then");
    expect(banner.action?.label).toBe("Keep Pro");
  });

  it("not earlier, and not once dismissed for this trial", () => {
    const options = { ...base, role: "owner" as const, onManageBilling: vi.fn() };
    expect(billingBanners(trial("2026-10-06T06:00:00Z"), options)).toEqual([]);
    expect(billingBanners(trial("2026-10-02T06:00:00Z"), { ...options, dismissedTrial: "2026-10-02T06:00:00Z" })).toEqual([]);
  });
});
