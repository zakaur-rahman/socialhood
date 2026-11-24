import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { ScheduleFields } from "./ScheduleFields";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

async function openList(min: string, timeZone: string, date: string) {
  render(
    <ScheduleFields idPrefix="s" value={{ date, time: "" }} onChange={vi.fn()} timeZone={timeZone} limits={{ min: new Date(min), max: null }} />,
    { wrapper: TooltipProvider },
  );
  await userEvent.click(screen.getByRole("button", { name: "Choose a time" }));
  const column = async (name: "Hours" | "Minutes", item: string) =>
    within(await screen.findByRole("listbox", { name })).getByRole("option", { name: item });
  return { hour: (h: string) => column("Hours", h), minute: (m: string) => column("Minutes", m) };
}

describe("the time columns' first allowed time (C-181)", () => {
  it("starts a minute past the limit, in the workspace's zone", async () => {
    // 09:14:10 UTC is 14:44:10 in Kolkata, so the first allowed time is 14:46.
    const pick = await openList("2026-09-28T09:14:10Z", "Asia/Kolkata", "2026-09-28");
    expect(await pick.hour("13")).toHaveAttribute("aria-disabled", "true");
    expect(await pick.hour("14")).not.toHaveAttribute("aria-disabled");
    expect(await pick.minute("45")).toHaveAttribute("aria-disabled", "true");
    expect(await pick.minute("46")).not.toHaveAttribute("aria-disabled");
  });

  it("disables all of the day when the first allowed minute is tomorrow", async () => {
    const pick = await openList("2026-09-28T23:59:30Z", "UTC", "2026-09-28");
    expect(await pick.hour("23")).toHaveAttribute("aria-disabled", "true");
    expect(await pick.hour("00")).toHaveAttribute("aria-disabled", "true");
  });

  it("disables times on a date already past", async () => {
    const pick = await openList("2026-09-28T09:14:10Z", "UTC", "2026-09-27");
    expect(await pick.hour("09")).toHaveAttribute("aria-disabled", "true");
  });
});
