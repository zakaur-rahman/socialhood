import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { MODAL_MOTION_CLASSES, classes, expectModalScrim, expectReducedMotionCancels } from "@/test/overlays";

function Example({
  side,
  size,
  className,
  close = true,
}: {
  side?: "top" | "right" | "bottom" | "left";
  size?: "default" | "panel";
  className?: string;
  close?: boolean;
}) {
  return (
    <Sheet defaultOpen>
      <SheetContent side={side} size={size} className={className} showCloseButton={close}>
        <SheetHeader>
          <SheetTitle>Posting times</SheetTitle>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  );
}

describe("Sheet (UI-012)", () => {
  it("dims the page with the 60% scrim, without blur, fading over the panel's time", () => {
    render(<Example />);
    expectModalScrim(document.querySelector('[data-slot="sheet-overlay"]')!);
  });

  it("slides 40 px from its side and fades: 200 ms in, 120 ms out; still under reduced motion", () => {
    for (const side of ["top", "right", "bottom", "left"] as const) {
      const { unmount } = render(<Example side={side} />);
      const content = screen.getByRole("dialog");
      expect(content).toHaveAttribute("data-side", side);
      expect(content).toHaveClass(
        ...MODAL_MOTION_CLASSES,
        `data-[side=${side}]:data-open:slide-in-from-${side}-10`,
        `data-[side=${side}]:data-closed:slide-out-to-${side}-10`,
        "motion-reduce:transition-none",
      );
      // No transition shorthand (it would include outline-color) and no literal timing.
      expect(classes(content).filter((c) => ["transition", "duration-200", "ease-in-out"].includes(c))).toEqual([]);
      expectReducedMotionCancels(content);
      unmount();
    }
  });

  it("floats with the spec's shadow", () => {
    render(<Example />);
    expect(screen.getByRole("dialog")).toHaveClass("shadow-xl");
    expect(screen.getByRole("dialog")).not.toHaveClass("shadow-lg");
  });

  it("default size: three quarters wide, at most 24 rem from 640 px (unchanged)", () => {
    render(<Example />);
    const content = screen.getByRole("dialog");
    expect(content).toHaveAttribute("data-size", "default");
    expect(content).toHaveClass("data-[side=right]:w-3/4", "data-[side=right]:sm:max-w-sm", "data-[side=right]:border-l");
  });

  it('size="panel": the full screen below 768 px, 420 px beside the page from there', () => {
    render(<Example size="panel" />);
    const content = screen.getByRole("dialog");
    expect(content).toHaveAttribute("data-size", "panel");
    expect(content).toHaveClass("inset-0", "w-full", "md:w-105", "md:data-[side=right]:left-auto", "md:data-[side=right]:border-l");
    expect(classes(content).filter((c) => c.includes("w-3/4") || c.includes("max-w-sm"))).toEqual([]);
    // Below md the panel is the screen: no side border.
    expect(content).not.toHaveClass("data-[side=right]:border-l");
  });

  it("existing call-site widths still replace the default (the phone drawer)", () => {
    render(
      <Example
        side="left"
        close={false}
        className="w-[256px] gap-0 border-line bg-canvas p-3 data-[side=left]:w-[256px] sm:max-w-[256px] data-[side=left]:sm:max-w-[256px]"
      />,
    );
    const list = classes(screen.getByRole("dialog"));
    expect(list.filter((c) => c.startsWith("data-[side=left]:w-"))).toEqual(["data-[side=left]:w-[256px]"]);
    expect(list.filter((c) => c.startsWith("data-[side=left]:sm:max-w-"))).toEqual(["data-[side=left]:sm:max-w-[256px]"]);
    expect(list).toContain("bg-canvas");
    expect(list).not.toContain("bg-popover");
  });

  it("the close button is 40 px on coarse pointers and the title leaves room for it", async () => {
    const user = userEvent.setup();
    render(
      <Sheet>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>
          <SheetTitle>Drafts and queue</SheetTitle>
        </SheetContent>
      </Sheet>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    const close = screen.getByRole("button", { name: "Close" });
    expect(close).toHaveAttribute("data-slot", "sheet-close");
    expect(close).toHaveClass("size-7", "pointer-coarse:size-10", "pointer-coarse:top-2", "pointer-coarse:right-2");
    const title = screen.getByRole("heading", { name: "Drafts and queue" });
    expect(title).toHaveClass(
      "text-base",
      "font-semibold",
      "group-has-data-[slot=sheet-close]/sheet-content:pe-8",
      "pointer-coarse:group-has-data-[slot=sheet-close]/sheet-content:pe-10",
    );
    expect(title).not.toHaveClass("font-medium");
    await user.click(close);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open" })).toHaveFocus();
  });
});
