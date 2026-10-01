import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { MODAL_MOTION_CLASSES, classes, expectModalScrim, expectReducedMotionCancels } from "@/test/overlays";

const slot = (name: string) => document.querySelector(`[data-slot="${name}"]`) as HTMLElement;

function Example({ size, className, close = true }: { size?: "sm" | "md" | "lg" | "xl"; className?: string; close?: boolean }) {
  return (
    <Dialog defaultOpen>
      <DialogContent size={size} className={className} showCloseButton={close}>
        <DialogHeader>
          <DialogTitle>Delete the summer sale automation and everything it sent?</DialogTitle>
          <DialogDescription>It stops at once.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button type="button">Keep</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

describe("Dialog (UI-012)", () => {
  it("dims the page with the 60% scrim, without blur, fading with the panel", () => {
    render(<Example />);
    expectModalScrim(slot("dialog-overlay"));
  });

  it("enters in 200 ms and leaves in 120 ms with a 95% zoom, and stops under reduced motion", () => {
    render(<Example />);
    const content = screen.getByRole("dialog");
    expect(content).toHaveAttribute("data-slot", "dialog-content");
    expect(content).toHaveClass(...MODAL_MOTION_CLASSES, "data-open:zoom-in-95", "data-closed:zoom-out-95");
    expect(content).not.toHaveClass("duration-100");
    expectReducedMotionCancels(content);
  });

  it("floats with the spec's shadow and scrolls within the viewport", () => {
    render(<Example />);
    expect(screen.getByRole("dialog")).toHaveClass("shadow-xl", "max-h-[calc(100dvh-2rem)]", "overflow-y-auto");
  });

  it("sizes: today's four widths, sm by default; a call-site width still replaces it", () => {
    const widths = { sm: "sm:max-w-sm", md: "sm:max-w-md", lg: "sm:max-w-lg", xl: "sm:max-w-3xl" } as const;
    for (const [size, width] of Object.entries(widths) as [keyof typeof widths, string][]) {
      const { unmount } = render(<Example size={size} />);
      const content = screen.getByRole("dialog");
      expect(content).toHaveAttribute("data-size", size);
      expect(classes(content).filter((c) => c.startsWith("sm:max-w-"))).toEqual([width]);
      unmount();
    }
    render(<Example />);
    expect(screen.getByRole("dialog")).toHaveAttribute("data-size", "sm");
  });

  it("existing call-site classes still apply (width, height limit, surface)", () => {
    render(<Example className="max-h-[calc(100dvh-2rem)] overflow-y-auto border-line bg-panel sm:max-w-3xl" />);
    const list = classes(screen.getByRole("dialog"));
    expect(list.filter((c) => c.startsWith("sm:max-w-"))).toEqual(["sm:max-w-3xl"]);
    expect(list.filter((c) => c.startsWith("max-h-"))).toEqual(["max-h-[calc(100dvh-2rem)]"]);
    expect(list).toContain("bg-panel");
    expect(list).not.toContain("bg-popover");
  });

  it("title: the card-title role with normal leading (a wrapped title keeps its line height)", () => {
    render(<Example />);
    const title = screen.getByRole("heading", { name: /Delete the summer sale/ });
    expect(title).toHaveClass("text-base", "font-semibold");
    expect(title).not.toHaveClass("leading-none");
    expect(title).not.toHaveClass("font-medium");
    // lg and xl dialogs get the section-title size; the title leaves room for the close button.
    expect(title).toHaveClass(
      "group-data-[size=lg]/dialog-content:text-lg",
      "group-data-[size=xl]/dialog-content:text-lg",
      "group-has-data-[slot=dialog-close]/dialog-content:pe-6",
      "pointer-coarse:group-has-data-[slot=dialog-close]/dialog-content:pe-10",
    );
    expect(screen.getByRole("dialog")).toHaveClass("group/dialog-content");
  });

  it("the close button is 40 px on coarse pointers, named, and closes the dialog", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger>Open</DialogTrigger>
        <DialogContent>
          <DialogTitle>Shift times</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    const close = screen.getByRole("button", { name: "Close" });
    expect(close).toHaveAttribute("data-slot", "dialog-close");
    expect(close).toHaveClass("size-7", "pointer-coarse:size-10");
    await user.click(close);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    // Focus goes back to the trigger (UX-A11Y-02).
    expect(screen.getByRole("button", { name: "Open" })).toHaveFocus();
  });

  it("without a close button the title keeps its full width", () => {
    render(<Example close={false} />);
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    expect(document.querySelector('[data-slot="dialog-content"] [data-slot="dialog-close"]')).toBeNull();
  });
});
