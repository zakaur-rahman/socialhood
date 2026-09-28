import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { Conversation } from "@/lib/api/types";
import { conversation } from "@/test/api";

import { ReplyWindowChip } from "./ReplyWindowChip";
import { ThreadHeader } from "./ThreadHeader";

const now = new Date("2026-09-28T12:00:00Z");
const inHours = (h: number) => new Date(now.getTime() + h * 3_600_000).toISOString();

function renderHeader(overrides: Partial<Conversation> = {}, props: Partial<Parameters<typeof ThreadHeader>[0]> = {}) {
  const handlers = { onToggleDetails: vi.fn(), onSchedule: vi.fn(), onArchive: vi.fn(), onMarkUnread: vi.fn() };
  render(
    <TooltipProvider>
      <ThreadHeader
        conversation={conversation(overrides)}
        now={now}
        detailsOpen={false}
        canSchedule
        {...handlers}
        {...props}
      />
    </TooltipProvider>,
  );
  return handlers;
}

describe("ReplyWindowChip (UX-INB-05)", () => {
  it.each([
    [{ state: "open", closes_at: inHours(18) }, "Window: 18h left", "neutral"],
    [{ state: "open", closes_at: inHours(1) }, "Window: 1h left", "warning"],
    [{ state: "human_agent", closes_at: inHours(120) }, "Human Agent: 5d left", "warning"],
    [{ state: "closed" }, "Window closed", "danger"],
    [{ state: "template_only" }, "Template only", "warning"],
  ] as const)("%o → %s", (window, label, tone) => {
    render(<ReplyWindowChip window={window} now={now} />);
    const chip = screen.getByText(label);
    expect(chip).toHaveAttribute("data-tone", tone);
  });
});

describe("ThreadHeader (UX-INB-05)", () => {
  it("shows the contact, platform and AI mode", () => {
    renderHeader();
    expect(screen.getByRole("heading", { name: "Priya Nair" })).toBeInTheDocument();
    expect(screen.getByText("@priya.styles · Instagram")).toBeInTheDocument();
    expect(screen.getByText("AI: Suggest")).toBeInTheDocument();
  });

  it("AI auto, paused and needs you", () => {
    const { unmount } = render(
      <TooltipProvider>
        <ThreadHeader
          conversation={conversation({ ai: { effective_mode: "auto", override: null, paused_until: null } })}
          now={now}
          detailsOpen={false}
          canSchedule
          onToggleDetails={() => {}}
          onSchedule={() => {}}
          onArchive={() => {}}
          onMarkUnread={() => {}}
        />
      </TooltipProvider>,
    );
    expect(screen.getByText("AI: Auto")).toBeInTheDocument();
    unmount();
    renderHeader({ ai: { effective_mode: "auto", override: null, paused_until: inHours(1) } });
    expect(screen.getByText("AI paused")).toBeInTheDocument();
  });

  it("shows why the conversation needs a person", () => {
    renderHeader({ needs_human: true, needs_human_reason: "refund" });
    expect(screen.getByText("Needs you: refund")).toBeInTheDocument();
  });

  it("names the account when several are connected, and offers Back on phones", () => {
    renderHeader({}, { showAccount: true, backHref: "/w/maple/inbox" as Route });
    expect(screen.getByText("@priya.styles · Instagram · @maple.bakery")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to conversations" })).toHaveAttribute("href", "/w/maple/inbox");
  });

  it("toggles details and schedules", async () => {
    const handlers = renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Details" }));
    await userEvent.click(screen.getByRole("button", { name: "Schedule a message" }));
    expect(handlers.onToggleDetails).toHaveBeenCalledOnce();
    expect(handlers.onSchedule).toHaveBeenCalledOnce();
  });

  it("archives and marks unread from the menu", async () => {
    const handlers = renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "More actions" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Archive" }));
    expect(handlers.onArchive).toHaveBeenCalledWith(true);
    await userEvent.click(screen.getByRole("button", { name: "More actions" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Mark unread" }));
    expect(handlers.onMarkUnread).toHaveBeenCalledOnce();
  });

  it("offers Unarchive for an archived conversation", async () => {
    const handlers = renderHeader({ status: "archived" });
    await userEvent.click(screen.getByRole("button", { name: "More actions" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Unarchive" }));
    expect(handlers.onArchive).toHaveBeenCalledWith(false);
  });
});
