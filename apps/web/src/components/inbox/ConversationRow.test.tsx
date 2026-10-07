import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { ConversationListItem } from "@/lib/api/types";
import { listItem } from "@/test/api";

import { ConversationRow } from "./ConversationRow";

const now = new Date("2026-09-28T12:00:00Z");

// The app renders every page inside a TooltipProvider (app/layout.tsx); the badges' hints need one.
const wrapper = TooltipProvider;

function renderRow(overrides: Partial<ConversationListItem> = {}, selected = false) {
  render(<ConversationRow item={listItem(overrides)} href={"/w/maple/inbox/c1" as Route} selected={selected} now={now} />, {
    wrapper,
  });
  return screen.getByRole("link");
}

describe("ConversationRow (UX-INB-04)", () => {
  it("is a link to the conversation with name, time and preview", () => {
    const row = renderRow();
    expect(row).toHaveAttribute("href", "/w/maple/inbox/c1");
    expect(row).toHaveTextContent("Priya Nair");
    expect(row).toHaveTextContent("5m");
    expect(row).toHaveTextContent("Do you ship to Dubai?");
    expect(row).not.toHaveAttribute("aria-current");
  });

  it("read: secondary name, no unread dot", () => {
    renderRow({ unread_count: 0 });
    expect(screen.getByText("Priya Nair")).toHaveClass("text-fg-secondary");
    expect(screen.queryByLabelText("unread")).not.toBeInTheDocument();
  });

  it("unread: bright name, bold preview and an announced dot", () => {
    renderRow({ unread_count: 2 });
    expect(screen.getByText("Priya Nair")).toHaveClass("text-fg");
    expect(screen.getByText("Do you ship to Dubai?").parentElement).toHaveClass("font-medium");
    expect(screen.getByLabelText("unread")).toBeInTheDocument();
  });

  // UI-030: the one selection bar (DESIGN_SYSTEM §5, UI-ISS-053): 2 px, inset 8 px, rounded; was a
  // 3 px full-height bar.
  it("selected: marked current with the selection bar", () => {
    const row = renderRow({}, true);
    expect(row).toHaveAttribute("aria-current", "page");
    expect(row.className).toContain("bg-raised");
    expect(screen.getByTestId("row-accent")).toHaveClass("bg-brand", "w-0.5", "inset-y-2", "left-0", "rounded-full");
  });

  it("not selected: no selection bar; hover and inset focus from the tokens", () => {
    const row = renderRow();
    expect(screen.queryByTestId("row-accent")).not.toBeInTheDocument();
    expect(row).toHaveClass("hover:bg-hover", "focus-visible:-outline-offset-2");
  });

  it("without badges the row is two lines", () => {
    const row = renderRow();
    expect(row).toHaveClass("h-[68px]");
    expect(row.querySelector("[data-badge]")).toBeNull();
  });

  it.each([
    ["complaint", "Complaint"],
    ["closing_soon", "Closing in 3h"],
    ["negative", "Negative"],
  ] as const)("signal %s shows its badge: %s", (signal, label) => {
    const row = renderRow({ signal, reply_window_closes_at: "2026-09-28T15:00:00Z" });
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(row).toHaveClass("h-[90px]");
  });

  // UI-031: the hint is the Tooltip primitive, not a native title (UI-ISS-042); screen readers hear
  // the reason in the row's name, which is the link's.
  it("Needs you when escalated, Lead with the score at the threshold (60)", async () => {
    const row = renderRow({ needs_human: true, needs_human_reason: "refund", signal: "needs_you", lead_score: 72 });
    const needsYou = screen.getByText("Needs you");
    expect(needsYou).not.toHaveAttribute("title");
    expect(row).toHaveAccessibleName(expect.stringContaining("Needs you: refund"));
    await userEvent.hover(needsYou);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("The AI handed this over: refund");
    expect(screen.getByText("Lead 72/100")).toBeInTheDocument();
  });

  // UI-031: the row's badges are the Badge primitive: 11 px, 20 px tall, pills in their tone.
  it("badges are status Badges in their tone", () => {
    renderRow({ needs_human: true, needs_human_reason: "refund", lead_score: 72 });
    for (const [key, tone] of [
      ["needs_you", "danger"],
      ["lead", "brand"],
    ] as const) {
      const badge = document.querySelector(`[data-badge="${key}"]`) as HTMLElement;
      // A badge with a hint is a tooltip trigger, whose data-slot wins; the tone and size are Badge's.
      expect(badge).toHaveAttribute("data-shape", "pill");
      expect(badge).toHaveAttribute("data-tone", tone);
      expect(badge).toHaveClass("h-5", "text-2xs", "rounded-full");
    }
  });

  it("no Lead badge below the threshold", () => {
    renderRow({ lead_score: 59, signal: null });
    expect(screen.queryByText(/Lead/)).not.toBeInTheDocument();
  });

  it("AI Auto when the AI replies on its own", async () => {
    const { rerender } = render(
      <ConversationRow item={listItem()} href={"/w/maple/inbox/c1" as Route} selected={false} now={now} aiMode="auto" />,
      { wrapper },
    );
    const auto = screen.getByText("AI Auto");
    expect(auto).not.toHaveAttribute("title");
    await userEvent.hover(auto);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("The AI replies on its own in this conversation");
    rerender(<ConversationRow item={listItem()} href={"/w/maple/inbox/c1" as Route} selected={false} now={now} aiMode="suggest" />);
    expect(screen.queryByText("AI Auto")).not.toBeInTheDocument();
  });

  it("prefixes outbound previews", () => {
    renderRow({ last_message_direction: "outbound", last_message_source: "human", last_message_preview: "Sent the size chart!" });
    expect(screen.getByText("You: Sent the size chart!")).toBeInTheDocument();
  });

  it("prefixes AI and automation previews", () => {
    const { rerender } = render(
      <ConversationRow
        item={listItem({ last_message_direction: "outbound", last_message_source: "ai_auto", last_message_preview: "Yes, COD is available." })}
        href={"/w/maple/inbox/c1" as Route}
        selected={false}
        now={now}
      />,
      { wrapper },
    );
    expect(screen.getByText("AI: Yes, COD is available.")).toBeInTheDocument();
    rerender(
      <ConversationRow
        item={listItem({ last_message_direction: "outbound", last_message_source: "automation", last_message_preview: "Here's the link" })}
        href={"/w/maple/inbox/c1" as Route}
        selected={false}
        now={now}
      />,
    );
    expect(screen.getByText("Auto: Here's the link")).toBeInTheDocument();
  });

  it("labels attachments with an icon and a word", () => {
    const row = renderRow({ last_message_kind: "image", last_message_preview: null });
    expect(row).toHaveTextContent("Photo");
    expect(row.querySelector("svg.lucide-image")).not.toBeNull();
  });

  it("labels a story reply", () => {
    renderRow({ last_message_kind: "story_reply", last_message_preview: null });
    expect(screen.getByText("Story reply")).toBeInTheDocument();
  });

  it("without a picture: the initial on a gradient, with the platform badge", () => {
    const row = renderRow({ platform: "whatsapp", contact: { id: "p9", display_name: "kabir shah", username: null, profile_picture_url: null } });
    const fallback = screen.getByText("K");
    expect(fallback.className).toMatch(/from-/);
    expect(row.querySelector('[data-platform="whatsapp"]')).not.toBeNull();
  });
});
