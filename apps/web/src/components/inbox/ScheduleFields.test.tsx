import { render, screen } from "@testing-library/react";
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
  return (time: string) => screen.findByRole("option", { name: time });
}

describe("the time list's first allowed time (C-181)", () => {
  it("starts a minute past the limit, in the workspace's zone", async () => {
    // 09:14:10 UTC is 14:44:10 in Kolkata, so the first listed time is 14:46: 14:45 is off, 15:00 is on.
    const option = await openList("2026-09-28T09:14:10Z", "Asia/Kolkata", "2026-09-28");
    expect(await option("14:45")).toHaveAttribute("aria-disabled", "true");
    expect(await option("15:00")).not.toHaveAttribute("aria-disabled");
  });

  it("disables all of the day when the first allowed minute is tomorrow", async () => {
    const option = await openList("2026-09-28T23:59:30Z", "UTC", "2026-09-28");
    expect(await option("23:45")).toHaveAttribute("aria-disabled", "true");
    expect(await option("00:00")).toHaveAttribute("aria-disabled", "true");
  });

  it("disables times on a date already past", async () => {
    const past = await openList("2026-09-28T09:14:10Z", "UTC", "2026-09-27");
    expect(await past("09:00")).toHaveAttribute("aria-disabled", "true");
  });
});
