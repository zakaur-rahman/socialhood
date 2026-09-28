import { render, screen } from "@testing-library/react";
import type { Route } from "next";
import { describe, expect, it } from "vitest";

import type { ConversationListItem } from "@/lib/api/types";
import { listItem } from "@/test/api";

import { ConversationRow } from "./ConversationRow";

const now = new Date("2026-09-28T12:00:00Z");

function renderRow(overrides: Partial<ConversationListItem> = {}, selected = false) {
  render(<ConversationRow item={listItem(overrides)} href={"/w/maple/inbox/c1" as Route} selected={selected} now={now} />);
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

  it("selected: marked current with the accent bar", () => {
    const row = renderRow({}, true);
    expect(row).toHaveAttribute("aria-current", "page");
    expect(row.className).toContain("bg-raised");
  });

  it.each([
    ["needs_you", "Needs you"],
    ["complaint", "Complaint"],
    ["closing_soon", "Closing in 3h"],
    ["lead", "Lead"],
    ["negative", "Negative"],
  ] as const)("signal %s shows one chip: %s", (signal, label) => {
    renderRow({ signal, reply_window_closes_at: "2026-09-28T15:00:00Z" });
    expect(screen.getByText(label)).toBeInTheDocument();
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
