import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailsPanel } from "@/components/inbox/DetailsPanel";
import { ThreadView } from "@/components/inbox/ThreadView";
import type { Conversation, KnowledgeGap, KnowledgeSourceCreate, MessageAnalysis } from "@/lib/api/types";
import { resetInboxStore } from "@/lib/inbox/store";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import {
  accepted,
  account,
  analysis,
  billingState,
  conversation,
  json,
  knowledgeGap,
  knowledgeSource,
  listItem,
  message,
  noContent,
  renderWithApi,
  workspace,
  type Call,
} from "@/test/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/w/maple/inbox/c1",
  useRouter: () => ({ replace: () => undefined, push: () => undefined }),
  useSearchParams: () => new URLSearchParams(),
}));
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
    const state = { detail: conversation({ latest_analysis: analysis(), lead_score: 72 }) };
    const { calls } = renderWithApi(<DetailsPanel conversationId="c1" />, { handlers: handlers(state) });

    const section = await screen.findByRole("region", { name: "Latest message" });
    expect(within(section).getByText("Shipping")).toBeInTheDocument();
    // Topics come from the analysis as they are.
    expect(within(within(section).getByRole("list", { name: "Topics" })).getByText("shipping to uae")).toBeInTheDocument();
    // The lead score is on the customer card.
    const customer = screen.getByRole("region", { name: "Customer" });
    expect(within(customer).getByRole("meter", { name: "Lead score" })).toHaveAttribute("aria-valuenow", "72");
    expect(within(customer).getByText("72 / 100")).toBeInTheDocument();

    await user.click(within(section).getByRole("button", { name: "Correct the AI" }));
    const popover = await screen.findByRole("group", { name: "Correct the analysis" });
    const save = within(popover).getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    // UI-030: the intents are the ToggleGroup's chips; sentiment its small segmented control.
    expect(within(popover).getByRole("radiogroup", { name: "Intent" })).toHaveAttribute("data-variant", "chips");
    expect(within(popover).getByRole("radiogroup", { name: "Sentiment" })).toHaveAttribute("data-size", "sm");
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
    // The next step is a callout of its own (summary.v2, C-063).
    expect(within(section).getByRole("note", { name: "Next step" })).toHaveTextContent(
      "Next stepConfirm shipping and share the product link.",
    );

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

describe("Summary next step (C-063)", () => {
  it("an older summary without a next step shows no callout", async () => {
    const state = {
      detail: conversation({
        summary: { text: "Asked about sizes.", next_step: null, updated_at: "2026-09-28T11:00:00Z" },
      }),
    };
    renderWithApi(<DetailsPanel conversationId="c1" />, { handlers: handlers(state) });
    const section = await screen.findByRole("region", { name: "Summary" });
    expect(within(section).getByText("Asked about sizes.")).toBeInTheDocument();
    expect(within(section).queryByRole("note", { name: "Next step" })).not.toBeInTheDocument();
  });
});

describe("The context panel's customer card (C-063)", () => {
  it("customer since, linked account, Open in Instagram, and the escalation and pause as notes", async () => {
    const state = {
      detail: conversation({
        needs_human: true,
        needs_human_reason: "refund",
        ai: { effective_mode: "auto", override: "auto", paused_until: "2099-01-01T00:00:00Z" },
      }),
    };
    renderWithApi(<DetailsPanel conversationId="c1" />, { handlers: handlers(state) });
    const customer = await screen.findByRole("region", { name: "Customer" });
    expect(within(customer).getByText("Customer since").nextSibling).toHaveTextContent("27 Sep");
    expect(within(customer).getByText("Linked account").nextSibling).toHaveTextContent("@maple.bakery");
    expect(within(customer).getByRole("link", { name: /Open in Instagram/ })).toHaveAttribute(
      "href",
      "https://www.instagram.com/priya.styles/",
    );
    const notes = within(customer).getByRole("list", { name: "Attention" });
    expect(notes).toHaveTextContent("Needs you: refund");
    expect(notes).toHaveTextContent("AI paused until you resume it");
  });
});

describe("Teach AI (C-063)", () => {
  function teachSetup(gaps: KnowledgeGap[]) {
    const state = { detail: conversation({ latest_analysis: analysis({ message_id: "m1" }) }) };
    const view = renderWithApi(<DetailsPanel conversationId="c1" />, {
      handlers: handlers(state, {
        "GET /v1/w/:wid/knowledge-gaps": () => json({ items: gaps }),
        "POST /v1/w/:wid/knowledge-sources": (call: Call) => json(knowledgeSource({ ...(call.body as object) }), 201),
        "GET /v1/w/:wid/knowledge-sources": () => json({ items: [], usage: { characters_used: 0, characters_limit: 200000 } }),
      }),
    });
    // The thread has loaded the customer's message.
    view.queryClient.setQueryData(["w", "w1", "messages", "c1"], {
      pages: [{ items: [message({ id: "m1", text: "Do you deliver to Pune on Sundays?" })], next_cursor: null }],
      pageParams: [null],
    });
    return view;
  }

  async function teach(calls: Call[]) {
    const user = userEvent.setup();
    const section = await screen.findByRole("region", { name: "Latest message" });
    await user.click(within(section).getByRole("button", { name: "Teach AI" }));
    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    expect(within(form).getByLabelText("Question")).toHaveValue("Do you deliver to Pune on Sundays?");
    expect(within(form).getByLabelText("Answer")).toHaveValue("");
    await user.type(within(form).getByLabelText("Answer"), "Yes, until 2 pm.");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources")).toBe(true));
    return calls.find((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources")?.body as KnowledgeSourceCreate;
  }

  it("prefills the latest customer message as an FAQ question; the member types the answer", async () => {
    const { calls } = teachSetup([]);
    const body = await teach(calls);
    expect(body).toMatchObject({ type: "faq", question: "Do you deliver to Pune on Sundays?", body: "Yes, until 2 pm." });
    expect(body.gap_id ?? null).toBeNull();
  });

  it("links the knowledge gap the message was counted in, so answering resolves it", async () => {
    const { calls } = teachSetup([knowledgeGap({ id: "g2", examples: [] }), knowledgeGap({ id: "g1" })]);
    const body = await teach(calls);
    expect(body).toMatchObject({ question: "Do you deliver to Pune on Sundays?", gap_id: "g1" });
  });

  it("agents can't teach (knowledge is for owners and admins)", async () => {
    const state = { detail: conversation({ latest_analysis: analysis() }) };
    renderWithApi(<DetailsPanel conversationId="c1" />, {
      ws: { ...workspace, role: "agent" },
      handlers: handlers(state),
    });
    const section = await screen.findByRole("region", { name: "Latest message" });
    expect(within(section).queryByRole("button", { name: "Teach AI" })).not.toBeInTheDocument();
  });
});

describe("One AI mode control (C-063)", () => {
  it("the thread header has it; the context panel doesn't repeat it", async () => {
    const state = { detail: conversation({ latest_analysis: analysis({ message_id: "m1" }) }) };
    renderWithApi(
      <>
        <ThreadView key="c1" conversationId="c1" />
        <DetailsPanel conversationId="c1" />
      </>,
      {
        handlers: handlers(state, {
          "GET /v1/w/:wid/conversations/:id/messages": () => json({ items: [message({ id: "m1" })], next_cursor: null }),
          "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
        }),
      },
    );
    await screen.findByRole("region", { name: "Summary" });
    const controls = await screen.findAllByRole("button", { name: /^AI mode: / });
    expect(controls).toHaveLength(1);
    expect(controls[0].closest("header")).not.toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "AI in this conversation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "AI in this conversation" })).not.toBeInTheDocument();
  });
});
