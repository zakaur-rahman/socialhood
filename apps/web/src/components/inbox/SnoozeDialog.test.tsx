import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { SnoozeDialog } from "./SnoozeDialog";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

// Wednesday 10:00 in Kolkata.
const now = new Date("2026-11-18T04:30:00Z");

function setup() {
  const onSnooze = vi.fn();
  const onOpenChange = vi.fn();
  render(<SnoozeDialog open onOpenChange={onOpenChange} now={now} timeZone="Asia/Kolkata" onSnooze={onSnooze} />, {
    wrapper: TooltipProvider,
  });
  return { onSnooze, onOpenChange };
}

describe("SnoozeDialog (GR-45)", () => {
  it("offers the three presets with their times", () => {
    setup();
    const list = screen.getByRole("list", { name: "Snooze until" });
    const items = within(list).getAllByRole("button");
    expect(items.map((b) => b.textContent)).toEqual([
      "Later todayToday 13:00",
      "TomorrowTomorrow 09:00",
      "Next weekMon 23 Nov 09:00",
    ]);
  });

  it("snoozes until a preset and closes", async () => {
    const { onSnooze, onOpenChange } = setup();
    await userEvent.click(screen.getByRole("button", { name: /^Tomorrow/ }));
    expect(onSnooze).toHaveBeenCalledWith(new Date("2026-11-19T03:30:00Z"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("opens a date and time form for a custom time", async () => {
    const { onSnooze } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Pick a date and time" }));
    const form = screen.getByRole("form", { name: "Snooze until a chosen time" });
    expect(within(form).getByText(/Times are in Asia\/Kolkata/)).toBeInTheDocument();
    expect(onSnooze).not.toHaveBeenCalled();
  });
});
