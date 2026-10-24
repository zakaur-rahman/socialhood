import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentApproval } from "@/lib/api/types";
import { json, problem, renderWithApi, type Call } from "@/test/api";
import { approval, flowProposalCard, segmentProposalCard } from "@/test/agent";

import { ActionCardView } from "./ActionCardView";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  usePathname: () => "/w/maple/ask",
}));

const now = new Date("2026-09-29T12:00:00Z");

type Decide = { approve?: (call: Call) => Response; approved?: AgentApproval };

/** A fake API holding one approval; approving and rejecting change what the next list returns. */
function server(initial: AgentApproval, decide?: Decide) {
  const state = { current: initial };
  const handlers = {
    "GET /v1/w/:wid/agent/approvals": () => json({ items: [state.current], next_cursor: null }),
    "POST /v1/w/:wid/agent/approvals/:approval_id/approve": (call: Call) => {
      if (decide?.approve) return decide.approve(call);
      if (decide?.approved) {
        state.current = decide.approved;
        return json(state.current);
      }
      state.current = approval({
        ...state.current,
        status: "approved",
        can_decide: false,
        decided_by: { id: "u1", name: "Zakaur Rahman" },
        decided_at: "2026-09-29T12:00:05Z",
        outcome: {
          ok: true,
          summary: "Saved the draft automation “Price list on PRICE”.",
          resource_kind: "automation",
          resource_id: "au1",
          route: "automations/au1",
          error_code: null,
        },
      });
      return json(state.current);
    },
    "POST /v1/w/:wid/agent/approvals/:approval_id/reject": () => {
      state.current = approval({
        ...state.current,
        status: "rejected",
        can_decide: false,
        decided_by: { id: "u1", name: "Zakaur Rahman" },
        decided_at: "2026-09-29T12:00:05Z",
      });
      return json(state.current);
    },
  };
  return { state, handlers };
}

function show(card: Parameters<typeof ActionCardView>[0]["card"], initial: AgentApproval, decide?: Decide) {
  const fake = server(initial, decide);
  renderWithApi(
    <ActionCardView card={card} wid="w1" runId="r1" slug="maple" timeZone="Asia/Kolkata" now={now} onOpen={vi.fn()} />,
    { handlers: fake.handlers },
  );
  return fake;
}

beforeEach(() => nav.push.mockReset());

describe("A proposed flow (GR-36): what will happen, then Approve or Reject", () => {
  it("says in plain words what will happen, that it is waiting, and that nothing is saved yet", async () => {
    show(flowProposalCard(), approval());
    const card = screen.getByRole("region", { name: "Automation proposal" });
    expect(within(card).getByRole("heading", { name: "New automation: Price list on PRICE" })).toBeInTheDocument();
    const lines = within(card).getByRole("list", { name: "What will happen" });
    expect(lines).toHaveTextContent("Starts on a comment with a keyword");
    expect(lines).toHaveTextContent("saved as a draft");
    expect(lines).toHaveTextContent("price list");
    expect(within(card).getByText("Nothing is saved until you approve it.")).toBeInTheDocument();
    expect(await within(card).findByTestId("approval-status")).toHaveTextContent("Waiting for approval");
    expect(within(card).getByRole("button", { name: /Approve/ })).toBeEnabled();
    expect(within(card).getByRole("button", { name: /Reject/ })).toBeEnabled();
  });

  it("Approve runs it and the card shows the result, with the way to open it", async () => {
    show(flowProposalCard(), approval());
    await userEvent.click(await screen.findByRole("button", { name: /Approve/ }));
    expect(await screen.findByTestId("approval-result")).toHaveTextContent(
      "Saved the draft automation “Price list on PRICE”.",
    );
    expect(screen.getByTestId("approval-status")).toHaveTextContent("Approved");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open the automation" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/au1");
  });

  it("Reject says nothing was saved", async () => {
    show(flowProposalCard(), approval());
    await userEvent.click(await screen.findByRole("button", { name: /Reject/ }));
    expect(await screen.findByTestId("approval-result")).toHaveTextContent("Rejected by Zakaur Rahman");
    expect(screen.getByTestId("approval-result")).toHaveTextContent("Nothing was saved");
  });

  it("Approve is disabled, with the reason, for a role that can't do it; Reject still works", async () => {
    show(flowProposalCard(), approval({ can_decide: false }));
    const approve = await screen.findByRole("button", { name: /Approve/ });
    expect(approve).toBeDisabled();
    expect(
      screen.getByText("Only owners and admins can approve this, as in the app.", { selector: ".sr-only" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reject/ })).toBeEnabled();
  });

  it("when the app refused it on approval, says why and keeps the controls", async () => {
    show(
      flowProposalCard(),
      approval({
        outcome: {
          ok: false,
          summary: "Nothing was saved. A segment with that name already exists.",
          resource_kind: null,
          resource_id: null,
          route: null,
          error_code: "conflict",
        },
      }),
    );
    expect(await screen.findByTestId("approval-refused")).toHaveTextContent("A segment with that name already exists.");
    expect(screen.getByRole("button", { name: /Approve/ })).toBeEnabled();
  });

  it("an approval decided or expired in the meantime shows the API's words", async () => {
    show(flowProposalCard(), approval(), {
      approve: () => problem(409, "conflict", "This expired before anyone approved it. Ask again to get it back."),
    });
    await userEvent.click(await screen.findByRole("button", { name: /Approve/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This expired before anyone approved it");
  });

  it("an expired proposal says nothing was saved and has no controls", async () => {
    show(flowProposalCard(), approval({ status: "expired", can_decide: false }));
    expect(await screen.findByTestId("approval-result")).toHaveTextContent("expired");
    expect(screen.getByTestId("approval-result")).toHaveTextContent("Nothing was saved");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
  });
});

describe("A proposed segment", () => {
  it("shows the filters and how many people match, and approving offers the segment", async () => {
    const pending = approval({ id: "ap2", tool: "propose_segment", summary: "New segment: VIPs with email", match_count: 12 });
    show(segmentProposalCard(), pending, {
      approved: {
        ...pending,
        status: "approved",
        can_decide: false,
        outcome: {
          ok: true,
          summary: "Saved the segment “VIPs with email”. It matches 12 people right now.",
          resource_kind: "segment",
          resource_id: "sg1",
          route: "contacts?segment=sg1",
          error_code: null,
        },
      },
    });
    const card = screen.getByRole("region", { name: "Segment proposal" });
    expect(within(card).getByRole("list", { name: "What will happen" })).toHaveTextContent("Has the tag vip");
    expect(within(card).getByTestId("proposal-count")).toHaveTextContent("12 people match");
    await userEvent.click(await within(card).findByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(within(card).getByTestId("approval-result")).toHaveTextContent("12 people"));
    await userEvent.click(within(card).getByRole("button", { name: "Open the segment" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/contacts?segment=sg1");
  });

  it("one person is not 'people'", () => {
    show(segmentProposalCard({ match_count: 1 }), approval({ id: "ap2" }));
    expect(screen.getByTestId("proposal-count")).toHaveTextContent("1 person matches");
  });
});
