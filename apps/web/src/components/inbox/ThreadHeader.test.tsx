import { render, screen, within } from "@testing-library/react";
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

describe("ReplyWindowChip (UX-INB-05, C-063)", () => {
  it.each([
    [{ state: "open", closes_at: inHours(23) }, "Window: 23h left", "neutral"],
    [{ state: "open", closes_at: inHours(2) }, "Window: 2h left", "neutral"],
    [{ state: "open", closes_at: inHours(1.99) }, "Window: 1h left", "warning"],
    [{ state: "open", closes_at: inHours(0.25) }, "Window: 15m left", "warning"],
    [{ state: "human_agent", closes_at: inHours(120) }, "Human Agent: 5d left", "warning"],
    [{ state: "closed" }, "Window closed", "danger"],
    [{ state: "template_only" }, "Template only", "warning"],
  ] as const)("%o → %s", (window, label, tone) => {
    render(<ReplyWindowChip window={window} now={now} />);
    const chip = screen.getByText(label);
    expect(chip).toHaveAttribute("data-tone", tone);
  });

  it("neutral is outlined, amber under 2 h, red once closed", () => {
    const { rerender } = render(<ReplyWindowChip window={{ state: "open", closes_at: inHours(23) }} now={now} />);
    expect(screen.getByText("Window: 23h left")).toHaveClass("border-line", "text-fg-secondary");
    rerender(<ReplyWindowChip window={{ state: "open", closes_at: inHours(1) }} now={now} />);
    expect(screen.getByText("Window: 1h left")).toHaveClass("bg-warning-soft", "text-warning");
    rerender(<ReplyWindowChip window={{ state: "closed" }} now={now} />);
    expect(screen.getByText("Window closed")).toHaveClass("bg-danger-soft", "text-danger-fg");
  });
});

describe("ThreadHeader (UX-INB-05)", () => {
  it("shows the contact, handle, platform, our linked account and AI mode", () => {
    renderHeader();
    const heading = screen.getByRole("heading", { name: "Priya Nair" });
    expect(screen.getByTestId("thread-identity")).toHaveTextContent("@priya.styles · Instagram · @maple.bakery");
    expect(screen.getByText("AI: Suggest")).toBeInTheDocument();
    // The window chip sits beside the name.
    expect(heading.parentElement).toContainElement(screen.getByText("Window: 23h left"));
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

  it("with the AI control (P5): the control replaces the chip, beside Needs you", () => {
    renderHeader(
      { needs_human: true, needs_human_reason: "refund" },
      { aiControl: <button type="button">AI control</button> },
    );
    expect(screen.getByText("Needs you: refund")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI control" })).toBeInTheDocument();
    expect(screen.queryByText("AI: Suggest")).not.toBeInTheDocument();
  });

  it("narrow headers: Needs you and the window chip join the handle line, compact; screen readers hear them whole (UI-004)", () => {
    renderHeader({ needs_human: true, needs_human_reason: "refund" });
    const heading = screen.getByRole("heading", { name: "Priya Nair" });
    // The container query shows one of each pair: beside the name when the header is wide…
    const nameLine = heading.parentElement as HTMLElement;
    expect(within(nameLine).getByText("Window: 23h left")).toBeInTheDocument();
    expect(within(nameLine).getByText("Needs you: refund")).toBeInTheDocument();
    // …on the handle line when it is narrow, without "Window:" and the reason, which stay for screen readers.
    const handleLine = screen.getByTestId("thread-identity").parentElement as HTMLElement;
    expect(within(handleLine).getByText("23h left")).toHaveTextContent("Window: 23h left");
    expect(within(handleLine).getByText("Needs you")).toHaveTextContent("Needs you: refund");
    // The name keeps 80 px; the other items move first (UI-ISS-019).
    expect(heading).toHaveClass("min-w-20");
  });

  it("the platform name is secondary text beside its glyph, which carries the colour (UI-ISS-006)", () => {
    renderHeader();
    const platform = within(screen.getByTestId("thread-identity")).getByText("Instagram");
    expect(platform).not.toHaveClass("text-instagram");
    expect(platform.querySelector("svg")).toHaveClass("text-instagram");
  });

  it("on the narrowest phones the panel toggle is in More", async () => {
    const handlers = renderHeader();
    // CSS hides the toggle below 352 px (a container query jsdom doesn't run), so hide it here.
    screen.getByRole("button", { name: "Details" }).style.display = "none";
    await userEvent.click(screen.getByRole("button", { name: "More actions" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Customer details" }));
    expect(handlers.onToggleDetails).toHaveBeenCalledOnce();
  });

  it("with the toggle showing, More doesn't repeat it", async () => {
    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "More actions" }));
    expect(await screen.findByRole("menuitem", { name: "Archive" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Customer details" })).not.toBeInTheDocument();
  });

  it("offers Back on phones", () => {
    renderHeader({}, { backHref: "/w/maple/inbox" as Route });
    expect(screen.getByRole("link", { name: "Back to conversations" })).toHaveAttribute("href", "/w/maple/inbox");
  });

  it("the panel toggle shows whether the panel is open", () => {
    renderHeader({}, { detailsOpen: true });
    expect(screen.getByRole("button", { name: "Details" })).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles details and schedules", async () => {
    const handlers = renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Details" }));
    await userEvent.click(screen.getByRole("button", { name: "Schedule a message" }));
    expect(handlers.onToggleDetails).toHaveBeenCalledOnce();
    expect(handlers.onSchedule).toHaveBeenCalledOnce();
  });

  // UI-030: a disabled control says why (DisabledReason), not only in a title nobody can reach.
  it("with the reply window closed, Schedule is off and says why", () => {
    renderHeader({}, { canSchedule: false });
    const schedule = screen.getByRole("button", { name: "Schedule a message" });
    expect(schedule).toBeDisabled();
    expect(schedule).not.toHaveAttribute("title");
    const reason = schedule.closest('[data-slot="disabled-reason"]') as HTMLElement;
    expect(reason).toHaveAttribute("tabindex", "0");
    expect(reason).toHaveAccessibleDescription("Scheduling needs an open reply window");
    // Hidden below md, as the button was: the composer's clock schedules there.
    expect(reason).toHaveClass("hidden", "md:inline-flex");
  });

  it("the header's icon buttons are the Button's icon-lg size, with no touch patches", () => {
    renderHeader({}, { backHref: "/w/maple/inbox" as Route });
    for (const control of [
      screen.getByRole("link", { name: "Back to conversations" }),
      screen.getByRole("button", { name: "Schedule a message" }),
      screen.getByRole("button", { name: "Details" }),
      screen.getByRole("button", { name: "More actions" }),
    ]) {
      expect(control).toHaveAttribute("data-size", "icon-lg");
      expect(control.className).not.toMatch(/md:size-|(^| )size-10/);
    }
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
