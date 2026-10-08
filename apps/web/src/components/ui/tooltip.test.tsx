import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FLOATING_SURFACE } from "@/components/ui/floating";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { colorTokens } from "@/styles/tokens";
import { classes, expectReducedMotionCancels } from "@/test/overlays";

const content = () => document.querySelector('[data-slot="tooltip-content"]') as HTMLElement;
const arrow = () => document.querySelector('[data-slot="tooltip-arrow"]') as Element;

async function open(className?: string) {
  const user = userEvent.setup();
  render(
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger>Inbox</TooltipTrigger>
        <TooltipContent side="right" className={className}>
          Inbox · 4 unread
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>,
  );
  await user.hover(screen.getByRole("button", { name: "Inbox" }));
  await screen.findByRole("tooltip");
  return user;
}

function hex(name: string): string {
  return colorTokens.find((t) => t.name === name)!.value;
}

function contrast(a: string, b: string): number {
  const luminance = (h: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(h.slice(i, i + 2), 16) / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("Tooltip (UI-017, D-03)", () => {
  it("is dark like the other floating surfaces: overlay, fg text, the line ring and the floating shadow", async () => {
    await open();
    expect(content()).toHaveClass("bg-overlay", "text-fg", "ring-1", "ring-line", "shadow-floating", "rounded-md", "text-xs");
    // The same edge and shadow as Popover, DropdownMenu and Select.
    for (const c of ["ring-1", "ring-line", "shadow-floating"]) expect(FLOATING_SURFACE.split(" ")).toContain(c);
    const list = classes(content());
    expect(list).not.toContain("bg-foreground");
    expect(list).not.toContain("text-background");
    expect(list.filter((c) => c.startsWith("shadow-"))).toEqual(["shadow-floating"]);
  });

  it("keeps fg text at 15:1 or more on the overlay surface", () => {
    expect(contrast(hex("fg"), hex("overlay"))).toBeGreaterThanOrEqual(15);
  });

  it("points at its trigger with an arrow that matches the surface and its edge", async () => {
    await open();
    expect(arrow()).toHaveClass("bg-overlay", "fill-overlay", "border-r", "border-b", "border-line", "bg-clip-padding", "rotate-45");
    expect(classes(arrow()).filter((c) => /foreground/.test(c))).toEqual([]);
  });

  it("fades in over 120 ms, rising 4 px, and not at all under reduced motion", async () => {
    await open();
    expect(content()).toHaveClass(
      "duration-fast",
      "data-[state=delayed-open]:animate-in",
      "data-[state=delayed-open]:fade-in-0",
      "data-[state=delayed-open]:ease-enter",
      "data-closed:animate-out",
      "data-closed:fade-out-0",
      "data-closed:ease-exit",
      "data-[side=right]:slide-in-from-left-1",
      "data-[side=top]:slide-in-from-bottom-1",
    );
    const list = classes(content());
    expect(list.filter((c) => /zoom|slide-in-from-\w+-2$/.test(c))).toEqual([]);
    expectReducedMotionCancels(content());
  });

  it("describes its trigger, and a call site's width still applies", async () => {
    await open("max-w-60");
    expect(screen.getByRole("button", { name: "Inbox" })).toHaveAccessibleDescription("Inbox · 4 unread");
    expect(classes(content()).filter((c) => c.startsWith("max-w-"))).toEqual(["max-w-60"]);
  });
});
