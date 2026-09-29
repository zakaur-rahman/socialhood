import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { billingState } from "@/test/api";

import { creditBanners } from "./AppShell";
import { BannerSlot } from "./BannerSlot";

vi.mock("@clerk/nextjs", () => ({ UserButton: () => null }));

const now = new Date("2026-09-28T12:00:00Z");

describe("AI credits banner (FR-AI-05, UX-SH-04)", () => {
  it("when the credits are used up: the limit, the reset date and Upgrade", () => {
    const banners = creditBanners(
      billingState({ usage: [{ metric: "ai_credits", used: 200, limit: 200, period_end: "2026-10-01" }] }),
      "maple",
      "owner",
      now,
    );
    render(<BannerSlot banners={banners} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "You've used all 200 AI credits for this month. They reset on 1 Oct.",
    );
    expect(screen.getByRole("link", { name: "Upgrade" })).toHaveAttribute("href", "/w/maple/settings/billing");
  });

  it("agents see the banner without the upgrade link", () => {
    const banners = creditBanners(
      billingState({ usage: [{ metric: "ai_credits", used: 5000, limit: 5000, period_end: "2027-01-01" }] }),
      "maple",
      "agent",
      now,
    );
    render(<BannerSlot banners={banners} />);
    expect(screen.getByRole("status")).toHaveTextContent("You've used all 5,000 AI credits for this month. They reset on 1 Jan 2027.");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("no banner while credits remain, for unlimited plans, or before billing loads", () => {
    expect(creditBanners(billingState(), "maple", "owner")).toEqual([]);
    expect(
      creditBanners(billingState({ usage: [{ metric: "ai_credits", used: 9, limit: null }] }), "maple", "owner"),
    ).toEqual([]);
    expect(creditBanners(undefined, "maple", "owner")).toEqual([]);
  });
});
