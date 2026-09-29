import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailsPanel } from "@/components/inbox/DetailsPanel";
import { ThreadView } from "@/components/inbox/ThreadView";
import type { Conversation, MessageAnalysis } from "@/lib/api/types";
import { resetInboxStore } from "@/lib/inbox/store";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import {
  accepted,
  account,
  analysis,
  billingState,
  conversation,
  json,
  listItem,
  message,
  noContent,
  renderWithApi,
  type Call,
} from "@/test/api";

vi.mock("next/navigation", () => ({ usePathname: () => "/w/maple/inbox/c1" }));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function handlers(state: { detail: Conversation }, extra: Record<string, (call: Call) => Response> = {}) {
  return {
    "GET /v1/w/:wid/conversations/:id": () => json(state.detail),
    "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
    "GET /v1/w/:wid/billing": () => json(billingState()),
    "PATCH /v1/w/:wid/message-analyses/:id": (call: Call) => {
      const corrected: MessageAnalysis = {
        ...(state.detail.latest_analysis as MessageAnalysis),
        ...(call.body as object),
        corrected: true,
      };
      return json(corrected);
    },
    ...extra,
  };
}

beforeEach(() => {
  resetInboxStore();
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Analysis (FR-AI-02, FR-AI-04)", () => {
  it("the thread shows intent, sentiment and priority under the analysed customer message", async () => {
    const state = { detail: conversation({ latest_analysis: analysis({ message_id: "m1" }) }) };
    renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers(state, {
        "GET /v1/w/:wid/conversations/:id/messages": () =>
          json({
            items: [
              message({ id: "m2", text: "Thanks!", occurred_at: "2026-09-28T11:56:00Z" }),
              message({ id: "m1", text: "Do you ship to Dubai?" }),
            ],
            next_cursor: null,
          }),
        "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
      }),
    });
    const chips = await screen.findByRole("group", { name: "AI analysis" });
    expect(chips.closest("[data-message-id]")).toHaveAttribute("data-message-id", "m1");
    expect(within(chips).getByText("Shipping")).toBeInTheDocument();
    expect(within(chips).getByText("Positive")).toBeInTheDocument();
    expect(within(chips).getByText("Medium priority")).toBeInTheDocument();
    expect(screen.getAllByRole("group", { name: "AI analysis" })).toHaveLength(1);
  });

  it("Correct changes the intent and sentiment; the chips follow", async () => {
    const user = userEvent.setup();
    const state = { detail: conversation({ latest_analysis: analysis() }) };
    const { calls } = renderWithApi(<DetailsPanel conversationId="c1" />, { handlers: handlers(state) });

    const section = await screen.findByRole("region", { name: "Latest message" });
    expect(within(section).getByText("Shipping")).toBeInTheDocument();
    expect(within(section).getByRole("meter", { name: "Lead score" })).toHaveAttribute("aria-valuenow", "72");
    expect(within(section).getByText("shipping to uae")).toBeInTheDocument();

    await user.click(within(section).getByRole("button", { name: "Correct" }));
    const popover = await screen.findByRole("group", { name: "Correct the analysis" });
    const save = within(popover).getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    await user.click(within(popover).getByRole("radio", { name: "Pricing" }));
    await user.click(within(popover).getByRole("radio", { name: "Negative" }));
    await user.click(save);

    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/v1/w/w1/message-analyses/an1");
    expect(patch?.body).toEqual({ intent: "pricing", sentiment: "negative" });
    await waitFor(() => expect(within(section).getByText("Pricing")).toBeInTheDocument());
    expect(within(section).getByText("Negative")).toBeInTheDocument();
    expect(within(section).getByText("Corrected by your team")).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Correction saved");
  });

  it("before any analysis, says so", async () => {
    const state = { detail: conversation() };
    renderWithApi(<DetailsPanel conversationId="c1" />, { handlers: handlers(state) });
    const section = await screen.findByRole("region", { name: "Latest message" });
    expect(within(section).getByText(/Not analysed yet/)).toBeInTheDocument();
  });
});

describe("Summary (FR-AI-03)", () => {
  it("shows the summary and next step; Refresh waits for conversation.updated and shows the new one", async () => {
    const user = userEvent.setup();
    const state = {
      detail: conversation({
        summary: {
          text: "Asked about the Aria dress in size S and got a yes.",
          next_step: "Confirm shipping and share the product link.",
          updated_at: "2026-09-28T11:00:00Z",
        },
      }),
    };
    const { calls, queryClient } = renderWithApi(<DetailsPanel conversationId="c1" />, {
      handlers: handlers(state, { "POST /v1/w/:wid/conversations/:id/summary": () => accepted() }),
    });
    const section = await screen.findByRole("region", { name: "Summary" });
    expect(within(section).getByText("Asked about the Aria dress in size S and got a yes.")).toBeInTheDocument();
    expect(within(section).getByText("Confirm shipping and share the product link.")).toBeInTheDocument();

    await user.click(within(section).getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/summary"))).toBe(true));
    expect(within(section).getByRole("status")).toHaveTextContent("Updating the summary…");

    // The job finishes: the detail now has a new summary, and conversation.updated says so.
    state.detail = {
      ...state.detail,
      summary: {
        text: "Now asking about shipping to Dubai.",
        next_step: "Answer the shipping question.",
        updated_at: "2026-09-28T12:05:00Z",
      },
    };
    act(() =>
      applyRealtimeEvent(queryClient, "w1", {
        id: "3-0",
        event: "conversation.updated",
        data: JSON.stringify({ conversation: listItem() }),
      }),
    );
    expect(await within(section).findByText("Now asking about shipping to Dubai.")).toBeInTheDocument();
    expect(within(section).queryByText("Updating the summary…")).not.toBeInTheDocument();
  });

  it("without a summary: Summarize asks for one", async () => {
    const user = userEvent.setup();
    const state = { detail: conversation() };
    const { calls } = renderWithApi(<DetailsPanel conversationId="c1" />, {
      handlers: handlers(state, { "POST /v1/w/:wid/conversations/:id/summary": () => accepted() }),
    });
    const section = await screen.findByRole("region", { name: "Summary" });
    expect(within(section).getByText(/No summary yet/)).toBeInTheDocument();
    await user.click(within(section).getByRole("button", { name: "Summarize" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/conversations/c1/summary")).toBe(true));
  });
});
