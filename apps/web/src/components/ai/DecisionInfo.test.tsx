import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThreadView } from "@/components/inbox/ThreadView";
import type { AiDecision } from "@/lib/api/types";
import { resetInboxStore } from "@/lib/inbox/store";
import { account, billingState, conversation, json, message, noContent, renderWithApi, type Call } from "@/test/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/w/maple/inbox/c1",
  useRouter: () => ({ replace: () => undefined, push: () => undefined }),
  useSearchParams: () => new URLSearchParams(),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function decision(overrides: Partial<AiDecision> = {}): AiDecision {
  return {
    id: "d1",
    conversation_id: "c1",
    message_id: "m1",
    suggestion_id: "s1",
    sent_message_id: "m2",
    outcome: "auto_sent",
    reason: null,
    checks: [
      { n: 10, name: "confidence", passed: true, value: 0.82 },
      { n: 1, name: "mode_is_auto", passed: true, value: null },
      { n: 9, name: "can_answer", passed: true, value: true },
    ],
    user_feedback: null,
    created_at: "2026-09-28T11:55:20Z",
    ...overrides,
  };
}

function setup() {
  let current = decision();
  const view = renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
      "GET /v1/w/:wid/billing": () => json(billingState()),
      "GET /v1/w/:wid/conversations/:id": () =>
        json(conversation({ ai: { effective_mode: "auto", override: null, paused_until: null } })),
      "GET /v1/w/:wid/conversations/:id/messages": () =>
        json({
          items: [
            message({
              id: "m2",
              direction: "outbound",
              source: "ai_auto",
              text: "Yes, we ship to Dubai in 5–7 days.",
              status: "delivered",
              suggestion_id: "s1",
              occurred_at: "2026-09-28T11:55:30Z",
            }),
            message({ id: "m1", text: "Do you ship to Dubai?" }),
          ],
          next_cursor: null,
        }),
      "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
      "GET /v1/w/:wid/messages/:id/ai-decision": () => json(current),
      "POST /v1/w/:wid/ai-decisions/:id/feedback": (call: Call) => {
        current = { ...current, user_feedback: (call.body as { feedback: "bad" | null }).feedback };
        return json(current);
      },
    },
  });
  return view;
}

beforeEach(() => {
  resetInboxStore();
  toast.success.mockReset();
});

describe("Sent by AI (F-09, FR-SUG-04)", () => {
  it("the bubble says AI Assisted; its info button shows the decision's checks", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const bubble = (await screen.findByText("Yes, we ship to Dubai in 5–7 days.")).closest("[data-message-id]") as HTMLElement;
    expect(within(bubble).getByText("AI Assisted").closest("[title]")).toHaveAttribute("title", "Sent by AI: an auto reply");
    // Loaded only when asked for.
    expect(calls.some((c) => c.path.endsWith("/ai-decision"))).toBe(false);

    await user.click(within(bubble).getByRole("button", { name: "Why the AI sent this" }));
    expect(await screen.findByText("Why the AI sent this", { selector: "p" })).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/ai-decision"))?.path).toBe("/v1/w/w1/messages/m2/ai-decision");

    const checks = screen.getByRole("list", { name: "Checks" });
    const items = within(checks).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(["AI mode is Auto", "Answer is in your knowledge", "AI is confident82%"]);
    expect(within(items[2]).getByLabelText("Passed")).toBeInTheDocument();
  });

  it("Should not have sent records bad feedback, and Undo clears it", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const bubble = (await screen.findByText("Yes, we ship to Dubai in 5–7 days.")).closest("[data-message-id]") as HTMLElement;
    await user.click(within(bubble).getByRole("button", { name: "Why the AI sent this" }));
    await user.click(await screen.findByRole("button", { name: "Should not have sent" }));

    await waitFor(() => expect(calls.filter((c) => c.path === "/v1/w/w1/ai-decisions/d1/feedback")).toHaveLength(1));
    expect(calls.find((c) => c.path.endsWith("/feedback"))?.body).toEqual({ feedback: "bad" });
    expect(await screen.findByText("You marked this as a reply the AI shouldn't have sent.")).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Thanks. Auto learns from this.");

    await user.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(calls.filter((c) => c.path.endsWith("/feedback"))).toHaveLength(2));
    expect(calls.filter((c) => c.path.endsWith("/feedback"))[1].body).toEqual({ feedback: null });
    expect(await screen.findByRole("button", { name: "Should not have sent" })).toBeInTheDocument();
  });
});
