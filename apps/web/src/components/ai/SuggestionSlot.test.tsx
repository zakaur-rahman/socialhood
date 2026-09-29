import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThreadView } from "@/components/inbox/ThreadView";
import type { Conversation, KnowledgeSourceCreate, SendMessage } from "@/lib/api/types";
import { resetInboxStore } from "@/lib/inbox/store";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import {
  accepted,
  account,
  analysis,
  billingState,
  conversation,
  json,
  knowledgeSource,
  message,
  noContent,
  problem,
  renderWithApi,
  suggestion,
  type Call,
} from "@/test/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/w/maple/inbox/c1",
  useRouter: () => ({ replace: () => undefined, push: () => undefined }),
  useSearchParams: () => new URLSearchParams(),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const question = message({ id: "m1", conversation_id: "c1", text: "Do you ship to Dubai?", occurred_at: "2026-09-28T11:55:00Z" });

function stored(call: Call) {
  const body = call.body as SendMessage;
  return message({
    id: "m-out",
    conversation_id: "c1",
    client_id: body.client_id,
    direction: "outbound",
    source: "human",
    text: body.text ?? null,
    status: "queued",
    suggestion_id: body.suggestion_id ?? null,
    occurred_at: "2026-09-28T12:00:00Z",
  });
}

function setup(detail: Partial<Conversation> = {}, overrides: Record<string, (call: Call) => Response> = {}) {
  const conv = conversation({ pending_suggestion: suggestion(), ...detail });
  const view = renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
      "GET /v1/w/:wid/conversations/:id": () => json(conv),
      "GET /v1/w/:wid/conversations/:id/messages": () => json({ items: [question], next_cursor: null }),
      "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
      "GET /v1/w/:wid/billing": () => json(billingState()),
      "POST /v1/w/:wid/conversations/:id/messages": (call) => json(stored(call), 202),
      "POST /v1/w/:wid/conversations/:id/suggestions": () => accepted(),
      "POST /v1/w/:wid/suggestions/:id/dismiss": () => json(suggestion({ status: "dismissed" })),
      "GET /v1/w/:wid/knowledge-sources": () => json({ items: [], usage: { characters_used: 0, characters_limit: 200000 } }),
      "POST /v1/w/:wid/knowledge-sources": (call) => json(knowledgeSource({ ...(call.body as object) }), 201),
      ...overrides,
    },
  });
  return view;
}

function sends(calls: Call[]) {
  return calls.filter((c) => c.method === "POST" && c.path === "/v1/w/w1/conversations/c1/messages");
}

beforeEach(() => {
  resetInboxStore();
  toast.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Suggested reply in the thread (F-08)", () => {
  it("Send posts the suggestion's text with suggestion_id, and the card closes", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Send" }));

    await waitFor(() => expect(sends(calls)).toHaveLength(1));
    expect(sends(calls)[0].body).toMatchObject({
      text: "Yes, we ship to the UAE! Delivery to Dubai takes 5–7 business days.",
      suggestion_id: "s1",
    });
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();
  });

  it("Edit moves the text into the composer; the edited reply carries suggestion_id", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Edit" }));

    const box = screen.getByRole("textbox", { name: "Reply to Priya Nair" });
    expect(box).toHaveValue("Yes, we ship to the UAE! Delivery to Dubai takes 5–7 business days.");
    expect(screen.getByText("Editing suggestion")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();

    await user.type(box, " Free over ₹3,000.{Enter}");
    await waitFor(() => expect(sends(calls)).toHaveLength(1));
    expect(sends(calls)[0].body).toMatchObject({
      text: "Yes, we ship to the UAE! Delivery to Dubai takes 5–7 business days. Free over ₹3,000.",
      suggestion_id: "s1",
    });
    expect(screen.queryByText("Editing suggestion")).not.toBeInTheDocument();
  });

  it("stopping the edit keeps the text, drops the link and brings the card back", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(within(await screen.findByRole("region", { name: "Suggested reply" })).getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Stop editing the suggestion" }));
    expect(screen.getByRole("region", { name: "Suggested reply" })).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Reply to Priya Nair" }), "{Enter}");
    await waitFor(() => expect(sends(calls)).toHaveLength(1));
    expect((sends(calls)[0].body as SendMessage).suggestion_id).toBeNull();
  });

  it("Regenerate shimmers until suggestion.created brings the new draft", async () => {
    const user = userEvent.setup();
    const { calls, queryClient } = setup();
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Regenerate" }));

    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/conversations/c1/suggestions")).toBe(true),
    );
    expect(await screen.findByText("Drafting a reply…")).toBeInTheDocument();

    act(() =>
      applyRealtimeEvent(queryClient, "w1", {
        id: "2-0",
        event: "suggestion.created",
        data: JSON.stringify({
          conversation_id: "c1",
          suggestion: suggestion({ id: "s2", reply_text: "We do! Dubai in 5–7 days.", regenerations_left: 4 }),
        }),
      }),
    );
    expect(await screen.findByText("We do! Dubai in 5–7 days.")).toBeInTheDocument();
    expect(screen.queryByText("Drafting a reply…")).not.toBeInTheDocument();
    expect(screen.getByText("4 drafts left")).toBeInTheDocument();
  });

  it("a refused regenerate says why and keeps the draft", async () => {
    const user = userEvent.setup();
    setup({}, { "POST /v1/w/:wid/conversations/:id/suggestions": () => problem(429, "rate_limited", "No more drafts for this message.") });
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("No more drafts for this message."));
    expect(screen.queryByText("Drafting a reply…")).not.toBeInTheDocument();
    expect(screen.getByText(/Delivery to Dubai takes 5–7 business days/)).toBeInTheDocument();
  });

  it("Dismiss closes the card", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Dismiss suggestion" }));
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/suggestions/s1/dismiss")).toBe(true));
  });

  it("a failed dismiss brings the card back", async () => {
    const user = userEvent.setup();
    setup({}, { "POST /v1/w/:wid/suggestions/:id/dismiss": () => problem(500, "internal") });
    const card = await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(within(card).getByRole("button", { name: "Dismiss suggestion" }));
    expect(await screen.findByRole("region", { name: "Suggested reply" })).toBeInTheDocument();
  });

  it("from an empty composer, Ctrl+Enter sends the suggestion and Esc dismisses it", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(screen.getByRole("textbox", { name: "Reply to Priya Nair" }));
    await user.keyboard("{Control>}{Enter}{/Control}");
    await waitFor(() => expect(sends(calls)).toHaveLength(1));
    expect((sends(calls)[0].body as SendMessage).suggestion_id).toBe("s1");
  });

  it("Esc in an empty composer dismisses the suggestion", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("region", { name: "Suggested reply" });
    await user.click(screen.getByRole("textbox", { name: "Reply to Priya Nair" }));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/suggestions/s1/dismiss")).toBe(true));
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();
  });

  it("a typed reply retires the suggestion", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("region", { name: "Suggested reply" });
    await user.type(screen.getByRole("textbox", { name: "Reply to Priya Nair" }), "Let me check{Enter}");
    await waitFor(() => expect(sends(calls)).toHaveLength(1));
    expect((sends(calls)[0].body as SendMessage).suggestion_id).toBeNull();
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();
  });

  it("shows Drafting a reply… while the first draft for a just-analysed message is on its way", async () => {
    setup({
      pending_suggestion: null,
      latest_analysis: analysis({ message_id: "m1", needs_reply: true, created_at: new Date().toISOString() }),
    });
    expect(await screen.findByText("Drafting a reply…")).toBeInTheDocument();
  });

  it("no drafting shimmer for an analysis long past", async () => {
    setup({
      pending_suggestion: null,
      latest_analysis: analysis({ message_id: "m1", needs_reply: true, created_at: "2026-09-28T11:55:05Z" }),
    });
    await screen.findByText("Do you ship to Dubai?");
    expect(screen.queryByText("Drafting a reply…")).not.toBeInTheDocument();
  });

  it("no card when the reply window is closed", async () => {
    setup({ reply_window: { state: "closed", closes_at: null } });
    await screen.findByText("Do you ship to Dubai?");
    expect(screen.queryByRole("region", { name: "Suggested reply" })).not.toBeInTheDocument();
  });
});

describe("Not in your knowledge (FR-SUG-03, F-08)", () => {
  const gap = suggestion({ can_answer: false, reply_text: null, missing_info: "shipping to Dubai", sources: [] });

  it("Add to knowledge opens the FAQ form with the customer's question and saves it", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ pending_suggestion: gap });
    const card = await screen.findByRole("region", { name: "Not in your knowledge" });
    expect(within(card).getByText("Priya asked about shipping to Dubai.")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Add to knowledge" }));

    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    expect(within(form).getByLabelText("Question")).toHaveValue("Do you ship to Dubai?");
    await user.type(within(form).getByLabelText("Answer"), "Yes, 5–7 business days, free over ₹3,000.");
    await user.click(within(form).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources")).toBe(true));
    const body = calls.find((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources")?.body as KnowledgeSourceCreate;
    expect(body).toMatchObject({ type: "faq", question: "Do you ship to Dubai?", body: "Yes, 5–7 business days, free over ₹3,000." });
    await waitFor(() => expect(screen.queryByRole("form", { name: "Add an FAQ" })).not.toBeInTheDocument());
  });

  it("agents only get Write reply, which focuses the composer", async () => {
    const user = userEvent.setup();
    const conv = conversation({ pending_suggestion: gap });
    renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      ws: { id: "w1", name: "Maple Bakery", slug: "maple", plan: "pro", role: "agent", timezone: "Asia/Kolkata" },
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
        "GET /v1/w/:wid/conversations/:id": () => json(conv),
        "GET /v1/w/:wid/conversations/:id/messages": () => json({ items: [question], next_cursor: null }),
        "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
      },
    });
    const card = await screen.findByRole("region", { name: "Not in your knowledge" });
    expect(within(card).queryByRole("button", { name: "Add to knowledge" })).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Write reply" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Reply to Priya Nair" })).toHaveFocus());
  });
});

describe("Escalation banner (F-09)", () => {
  it("in Auto, a conversation that needs a person says why the AI didn't reply", async () => {
    setup({
      needs_human: true,
      needs_human_reason: "refund",
      ai: { effective_mode: "auto", override: null, paused_until: null },
    });
    expect(await screen.findByText("AI didn't reply: customer is asking for a refund")).toBeInTheDocument();
  });

  it("not in Suggest, where the AI never replies on its own", async () => {
    setup({ needs_human: true, needs_human_reason: "refund" });
    await screen.findByRole("region", { name: "Suggested reply" });
    expect(screen.queryByText(/AI didn't reply/)).not.toBeInTheDocument();
  });
});
