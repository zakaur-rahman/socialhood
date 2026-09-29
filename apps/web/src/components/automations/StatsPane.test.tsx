import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AutomationStats } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { StatsPane, StatsView } from "./StatsPane";

function stats(overrides: Partial<AutomationStats> = {}): AutomationStats {
  return {
    days: 7,
    runs: 1240,
    dms_sent: 1180,
    replied_24h: 472,
    failures: 12,
    public_replies: 900,
    queued_now: 0,
    skipped: { cooldown: 30, expired: 2, outside_window: 0 },
    daily: [
      { date: "2026-09-27", runs: 600, failures: 5 },
      { date: "2026-09-28", runs: 640, failures: 7 },
    ],
    tapped: 0,
    awaiting_now: 0,
    nudged: 0,
    ...overrides,
  };
}

/** The figures strip as label → value. */
function figures(): Record<string, string> {
  return Object.fromEntries(
    Array.from(document.querySelectorAll("dl > div")).map((figure) => [
      figure.querySelector("dt")?.textContent ?? "",
      figure.querySelector("dd")?.textContent ?? "",
    ]),
  );
}

describe("StatsView (UX-SCR-12) with tap first and the follow nudge", () => {
  it("shows the four figures when neither is on", () => {
    render(<StatsView stats={stats()} />);
    expect(figures()).toEqual({
      Runs: "1,240",
      "DMs sent": "1,180",
      "Replied within 24 h": "40%",
      Failures: "12",
    });
  });

  it("adds Tapped and Waiting now with tap first, and Nudged with the nudge", () => {
    render(<StatsView stats={stats({ tapped: 1034, awaiting_now: 57, nudged: 318 })} tapFirst followNudge />);
    expect(figures()).toMatchObject({ Tapped: "1,034", "Waiting now": "57", Nudged: "318" });
    expect(screen.getAllByRole("definition")).toHaveLength(7);
  });

  it("keeps a figure the period still has after its feature was turned off", () => {
    render(<StatsView stats={stats({ nudged: 4 })} />);
    expect(figures()).toMatchObject({ Nudged: "4" });
    expect(figures()).not.toHaveProperty("Tapped");
  });

  it("loads the stats and shows the figures for the features in use", async () => {
    renderWithApi(<StatsPane wid="w1" automationId="au1" tapFirst />, {
      handlers: { "GET /v1/w/:wid/automations/:id/stats": () => json(stats({ tapped: 9, awaiting_now: 3 })) },
    });
    expect(await screen.findByText("Tapped")).toBeInTheDocument();
    expect(figures()).toMatchObject({ Tapped: "9", "Waiting now": "3" });
    expect(figures()).not.toHaveProperty("Nudged");
  });
});
