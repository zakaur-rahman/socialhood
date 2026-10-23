import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AutomationFunnel, FunnelStep } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { FunnelPanel, FunnelView, stepFigures } from "./FunnelPanel";
import { StatsPane } from "./StatsPane";

function step(overrides: Partial<FunnelStep> = {}): FunnelStep {
  return {
    step_id: "hello",
    kind: "send",
    title: "Message",
    text: "Here it is.",
    link_buttons: 0,
    quick_replies: 0,
    reached: 10,
    sent: 10,
    delivered: 9,
    read: 0,
    failed: 0,
    taps: 0,
    link_clicks: 0,
    link_clickers: 0,
    captures: 0,
    skipped: 0,
    consents: 0,
    ...overrides,
  };
}

function funnel(overrides: Partial<AutomationFunnel> = {}): AutomationFunnel {
  return { days: 7, runs: 10, links_tracked: true, steps: [step()], splits: [], ...overrides };
}

describe("a step's figures (GR-15)", () => {
  it("shows only what can happen at that kind of step", () => {
    expect(stepFigures(step()).map((f) => f.label)).toEqual(["Reached", "Sent", "Delivered"]);
    expect(stepFigures(step({ kind: "branch" })).map((f) => f.label)).toEqual(["Reached"]);
    expect(stepFigures(step({ read: 4 })).map((f) => f.label)).toContain("Read");
  });

  it("adds taps for quick replies, link clicks with their people, and a question's answers", () => {
    const send = stepFigures(step({ quick_replies: 2, taps: 3, link_buttons: 1, link_clicks: 5, link_clickers: 2 }));
    expect(send).toContainEqual({ label: "Taps", value: "3" });
    expect(send).toContainEqual({ label: "Link clicks", value: "5 (2 people)" });
    const ask = stepFigures(step({ kind: "ask", captures: 7, skipped: 2, consents: 4 }));
    expect(ask).toContainEqual({ label: "Answers", value: "7" });
    expect(ask).toContainEqual({ label: "Skipped", value: "2" });
    expect(ask).toContainEqual({ label: "Said yes to marketing", value: "4" });
  });

  it("says one person, and shows 0 clicks for a step with a link nobody has opened", () => {
    expect(stepFigures(step({ link_buttons: 1, link_clicks: 1, link_clickers: 1 }))).toContainEqual({
      label: "Link clicks",
      value: "1 (1 person)",
    });
    expect(stepFigures(step({ link_buttons: 1 }))).toContainEqual({ label: "Link clicks", value: "0" });
  });
});

describe("FunnelView", () => {
  it("lists the steps in order with their figures", () => {
    render(
      <FunnelView
        funnel={funnel({
          steps: [step(), step({ step_id: "q", kind: "ask", title: "Ask for an email", text: "Your email?", captures: 6 })],
        })}
      />,
    );
    const items = screen.getAllByTestId("funnel-step");
    expect(items.map((li) => li.getAttribute("data-step"))).toEqual(["hello", "q"]);
    expect(within(items[1]).getByText("Ask for an email")).toBeInTheDocument();
    expect(within(items[1]).getByText("Answers").nextElementSibling?.textContent).toBe("6");
  });

  it("tells you when link tracking is off and a step has a link", () => {
    render(<FunnelView funnel={funnel({ links_tracked: false, steps: [step({ link_buttons: 1 })] })} />);
    expect(screen.getByTestId("links-untracked")).toHaveTextContent("Link tracking is off");
  });

  it("stays quiet about tracking when no step has a link", () => {
    render(<FunnelView funnel={funnel({ links_tracked: false })} />);
    expect(screen.queryByTestId("links-untracked")).toBeNull();
  });

  it("compares a split's paths, with columns only where something happened", () => {
    render(
      <FunnelView
        funnel={funnel({
          steps: [step({ step_id: "split", kind: "randomize", title: "Split", text: null })],
          splits: [
            {
              step_id: "split",
              branches: [
                { path: 0, label: "Path A", weight: 1, runs: 12, delivered: 11, read: 0, taps: 0, link_clicks: 5, captures: 0 },
                { path: 1, label: "Path B", weight: 1, runs: 9, delivered: 9, read: 0, taps: 0, link_clicks: 2, captures: 0 },
              ],
            },
          ],
        })}
      />,
    );
    const table = within(screen.getByTestId("split-results")).getByRole("table");
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["Path", "Runs", "Delivered", "Link clicks"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell").map((c) => c.textContent))).toEqual([
      ["12", "11", "5"],
      ["9", "9", "2"],
    ]);
  });
});

describe("the Stats tab loads the funnel", () => {
  it("shows a step's link clicks from the API", async () => {
    renderWithApi(<FunnelPanel wid="w1" automationId="au1" days={7} />, {
      handlers: {
        "GET /v1/w/:wid/automations/:id/funnel": () =>
          json(funnel({ steps: [step({ link_buttons: 1, link_clicks: 3, link_clickers: 2 })] })),
      },
    });
    expect(await screen.findByText("3 (2 people)")).toBeInTheDocument();
  });

  it("sits under the stats and doesn't break them when it fails", async () => {
    renderWithApi(<StatsPane wid="w1" automationId="au1" />, {
      handlers: {
        "GET /v1/w/:wid/automations/:id/stats": () =>
          json({
            days: 7,
            runs: 3,
            dms_sent: 3,
            replied_24h: 1,
            failures: 0,
            public_replies: 0,
            queued_now: 0,
            skipped: { cooldown: 0, expired: 0, outside_window: 0 },
            daily: [{ date: "2026-09-27", runs: 3, failures: 0 }],
            tapped: 0,
            awaiting_now: 0,
            nudged: 0,
          }),
      },
    });
    expect(await screen.findByText("DMs sent")).toBeInTheDocument();
    expect(await screen.findByText("Step results didn't load.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry step results" })).toBeInTheDocument();
  });
});
