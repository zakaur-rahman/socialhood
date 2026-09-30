import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { suggestion } from "@/test/api";

import { EditingSuggestionChip, EscalationBanner, SuggestionCard, type SuggestionActions } from "./SuggestionCard";

function actions(): SuggestionActions & Record<string, ReturnType<typeof vi.fn>> {
  return {
    onSend: vi.fn(),
    onEdit: vi.fn(),
    onRegenerate: vi.fn(),
    onDismiss: vi.fn(),
    onWriteReply: vi.fn(),
    onAddToKnowledge: vi.fn(),
  };
}

function card(props: Partial<Parameters<typeof SuggestionCard>[0]> = {}) {
  const handlers = actions();
  render(
    <SuggestionCard
      suggestion={suggestion()}
      generating={false}
      customerName="Priya"
      canSend
      actions={handlers}
      {...props}
    />,
  );
  return handlers;
}

describe("the AI draft bar (UX-INB-08, C-063)", () => {
  it("generating: two shimmer lines and Drafting a reply…", () => {
    card({ generating: true });
    const region = screen.getByRole("region", { name: "Suggested reply" });
    expect(region).toHaveAttribute("data-state", "generating");
    expect(within(region).getByRole("status")).toHaveTextContent("Drafting a reply…");
    expect(within(region).queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });

  it("ready: AI draft, source chip and every action: Insert, Send, Draft again, Dismiss", async () => {
    const user = userEvent.setup();
    const handlers = card();
    const region = screen.getByRole("region", { name: "Suggested reply" });
    expect(region).toHaveAttribute("data-state", "ready");
    expect(within(region).getByText(/Delivery to Dubai takes 5–7 business days/)).toHaveTextContent(/^AI draft: Yes, we ship/);
    expect(within(region).getByText("From: Shipping policy")).toBeInTheDocument();
    expect(within(region).queryByText("Check this")).not.toBeInTheDocument();
    expect(within(region).getByText("5 drafts left")).toBeInTheDocument();

    await user.click(within(region).getByRole("button", { name: "Send" }));
    await user.click(within(region).getByRole("button", { name: "Insert" }));
    await user.click(within(region).getByRole("button", { name: "Draft again" }));
    await user.click(within(region).getByRole("button", { name: "Dismiss suggestion" }));
    expect(handlers.onSend).toHaveBeenCalledOnce();
    expect(handlers.onEdit).toHaveBeenCalledOnce();
    expect(handlers.onRegenerate).toHaveBeenCalledOnce();
    expect(handlers.onDismiss).toHaveBeenCalledOnce();
  });

  it("shows at most two sources, then +n", () => {
    card({
      suggestion: suggestion({
        sources: [
          { id: "k1", title: "Shipping policy" },
          { id: "k2", title: "Returns" },
          { id: "k3", title: "Sizes" },
        ],
      }),
    });
    expect(screen.getByText("From: Shipping policy")).toBeInTheDocument();
    expect(screen.getByText("From: Returns")).toBeInTheDocument();
    expect(screen.queryByText("From: Sizes")).not.toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("low confidence: a Check this chip", () => {
    card({ suggestion: suggestion({ low_confidence: true }) });
    expect(screen.getByText("Check this")).toBeInTheDocument();
  });

  it("no drafts left: Draft again is off", () => {
    card({ suggestion: suggestion({ regenerations_left: 0 }) });
    expect(screen.getByRole("button", { name: "Draft again" })).toBeDisabled();
    expect(screen.getByText("No drafts left")).toBeInTheDocument();
  });

  it("cannot send while the window is closed", () => {
    card({ canSend: false });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("long replies start clamped with More", async () => {
    const user = userEvent.setup();
    card({ suggestion: suggestion({ reply_text: "A long answer. ".repeat(30) }) });
    const more = screen.getByRole("button", { name: "More" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await user.click(more);
    expect(screen.getByRole("button", { name: "Less" })).toHaveAttribute("aria-expanded", "true");
  });

  it("one draft only: no quick-reply chips", () => {
    card();
    expect(screen.getAllByText(/AI draft:/)).toHaveLength(1);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("not in knowledge: the missing fact, Add to knowledge and Write reply", async () => {
    const user = userEvent.setup();
    const handlers = card({
      suggestion: suggestion({ can_answer: false, reply_text: null, missing_info: "shipping to Dubai", sources: [] }),
    });
    const region = screen.getByRole("region", { name: "Not in your knowledge" });
    expect(region).toHaveAttribute("data-state", "not_in_knowledge");
    expect(within(region).getByText("Priya asked about shipping to Dubai.").parentElement).toHaveTextContent(
      "Not in your knowledge: Priya asked about shipping to Dubai.",
    );
    expect(within(region).queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
    await user.click(within(region).getByRole("button", { name: "Add to knowledge" }));
    await user.click(within(region).getByRole("button", { name: "Write reply" }));
    expect(handlers.onAddToKnowledge).toHaveBeenCalledOnce();
    expect(handlers.onWriteReply).toHaveBeenCalledOnce();
  });

  it("Add to knowledge waits while the question's gap is looked up", () => {
    card({
      suggestion: suggestion({ can_answer: false, reply_text: null, missing_info: "shipping to Dubai", sources: [] }),
      addingToKnowledge: true,
    });
    expect(screen.getByRole("button", { name: "Add to knowledge" })).toBeDisabled();
  });

  it("not in knowledge without the right to add knowledge (agents): only Write reply", () => {
    const handlers = actions();
    render(
      <SuggestionCard
        suggestion={suggestion({ can_answer: false, reply_text: null, missing_info: "gift wrapping" })}
        generating={false}
        customerName="Priya"
        canSend
        actions={{ ...handlers, onAddToKnowledge: undefined }}
      />,
    );
    expect(screen.queryByRole("button", { name: "Add to knowledge" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Write reply" })).toBeInTheDocument();
  });

  it("editing chip and escalation banner", async () => {
    const onStop = vi.fn();
    render(
      <>
        <EscalationBanner message="AI didn't reply: customer is asking for a refund" />
        <EditingSuggestionChip onStop={onStop} />
      </>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("AI didn't reply: customer is asking for a refund");
    expect(screen.getByText("Editing suggestion")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop editing the suggestion" }));
    expect(onStop).toHaveBeenCalledOnce();
  });
});
