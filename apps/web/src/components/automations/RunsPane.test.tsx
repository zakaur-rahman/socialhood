import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AutomationRun } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { RunsPane } from "./RunsPane";

function run(overrides: Partial<AutomationRun> = {}): AutomationRun {
  return {
    id: "r1",
    created_at: "2026-09-28T08:30:00Z",
    result: "sent",
    trigger_kind: "comment",
    trigger_text: "LINK please",
    matched_keyword: "link",
    contact: { id: "p1", display_name: "Priya Nair", username: "priya.styles" },
    conversation_id: "c1",
    ...overrides,
  };
}

function renderRuns(items: AutomationRun[]) {
  return renderWithApi(<RunsPane wid="w1" slug="maple" automationId="au1" timeZone="Asia/Kolkata" />, {
    handlers: { "GET /v1/w/:wid/automations/:id/runs": () => json({ items, next_cursor: null }) },
  });
}

const rowOf = (name: string) => screen.getByText(name).closest("a, div.block") as HTMLElement;

describe("RunsPane (UX-SCR-12) with tap first and the follow nudge", () => {
  it("shows Waiting for tap, the tap time and the follow markers", async () => {
    renderRuns([
      run({ id: "r1", result: "awaiting_reply", contact: { id: "p1", display_name: "Priya Nair" } }),
      run({
        id: "r2",
        contact: { id: "p2", display_name: "Arjun Mehta" },
        confirmed_at: "2026-09-28T08:35:00Z",
        follows_business: false,
        nudge_message_id: "m9",
      }),
      run({ id: "r3", contact: { id: "p3", display_name: "Sara Khan" }, follows_business: true }),
    ]);

    await screen.findByText("Priya Nair");
    const waiting = rowOf("Priya Nair");
    expect(within(waiting).getByText("Waiting for tap")).toBeInTheDocument();
    expect(within(waiting).queryByTestId("run-markers")).toBeNull();

    const nudged = within(rowOf("Arjun Mehta")).getByTestId("run-markers");
    expect(within(nudged).getByText(/^Tapped .* 14:05$/)).toBeInTheDocument();
    expect(within(nudged).getByText("Not following")).toBeInTheDocument();
    expect(within(nudged).getByText("Nudged")).toBeInTheDocument();

    const follower = within(rowOf("Sara Khan")).getByTestId("run-markers");
    expect(follower).toHaveTextContent(/^Follower$/);
  });

  it("a run opens its conversation, markers and all", async () => {
    renderRuns([run({ confirmed_at: "2026-09-28T08:35:00Z", follows_business: true })]);
    const link = (await screen.findByText("Priya Nair")).closest("a") as HTMLAnchorElement;
    expect(link).toHaveAttribute("href", "/w/maple/inbox/c1");
    expect(within(link).getByTestId("run-markers")).toHaveTextContent(/Tapped .* 14:05\s*Follower/);
  });
});
