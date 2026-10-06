import { act, render, screen } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster, TOAST_ACTION_DURATION } from "@/components/ui/sonner";
import { classes } from "@/test/overlays";

const originalMatchMedia = window.matchMedia;

/** jsdom has no layout: answer min-width media queries for a given viewport width. */
function setWidth(width: number) {
  window.matchMedia = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query);
    return {
      matches: min ? width >= Number(min[1]) : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList;
  };
}

const list = () => document.querySelector("[data-sonner-toaster]") as HTMLElement;
const toastItem = () => document.querySelector("[data-sonner-toast]") as HTMLElement;

/** Sonner adds a toast on a timer after the call; run it. */
function show(fire: () => void) {
  act(() => {
    fire();
    vi.advanceTimersByTime(50);
  });
}

beforeEach(() => vi.useFakeTimers());

afterEach(() => {
  act(() => {
    toast.dismiss();
    vi.advanceTimersByTime(1_000);
  });
  vi.useRealTimers();
  window.matchMedia = originalMatchMedia;
});

describe("Toaster (UI-024)", () => {
  it("sits top centre on phones, clear of Send and the sticky action bars", () => {
    setWidth(375);
    render(<Toaster />);
    show(() => toast("Saved"));
    expect(list()).toHaveAttribute("data-y-position", "top");
    expect(list()).toHaveAttribute("data-x-position", "center");
  });

  it("sits bottom right from md", () => {
    setWidth(1280);
    render(<Toaster />);
    show(() => toast("Saved"));
    expect(list()).toHaveAttribute("data-y-position", "bottom");
    expect(list()).toHaveAttribute("data-x-position", "right");
  });

  it("draws toasts with the tokens, not sonner's palette: the floating surface, a line-strong edge, fg text, danger-fg errors", () => {
    setWidth(1280);
    render(<Toaster />);
    show(() => toast.error("Couldn't save"));
    const item = toastItem();
    expect(item).toHaveAttribute("data-styled", "false");
    expect(item).toHaveAttribute("data-type", "error");
    expect(item).toHaveClass("bg-popover", "border", "border-line-strong", "text-fg", "data-[type=error]:text-danger-fg");
    expect(item).toHaveClass("rounded-lg", "shadow-xl", "text-sm", "font-sans");
    expect(list()).not.toHaveAttribute("data-sonner-theme", "dark");
    expect(classes(item).filter((c) => /#|rgb|hsl|\[\d/.test(c))).toEqual([]);
  });

  it("moves on the motion tokens, beating sonner's own transition, and not at all under reduced motion", () => {
    setWidth(1280);
    render(<Toaster />);
    show(() => toast("Saved"));
    expect(toastItem()).toHaveClass(
      "duration-slow!",
      "ease-enter!",
      "data-[removed=true]:duration-fast!",
      "data-[removed=true]:ease-exit!",
      "motion-reduce:transition-none!",
      "motion-reduce:*:transition-none!",
    );
  });

  it("keeps the focus outline sonner removes", () => {
    setWidth(1280);
    render(<Toaster />);
    show(() => toast("Saved"));
    expect(toastItem()).toHaveClass("focus-visible:outline-2!", "focus-visible:outline-ring!");
  });

  it("gives an action the Button recipe: 28 px, and 40 px on coarse pointers", () => {
    setWidth(375);
    render(<Toaster />);
    show(() => toast("Conversation archived", { action: { label: "Undo", onClick: () => {} }, duration: TOAST_ACTION_DURATION }));
    const undo = screen.getByRole("button", { name: "Undo" });
    expect(undo).toHaveClass("h-7", "pointer-coarse:min-h-10", "bg-raised", "text-fg");
  });

  it("keeps a toast with an action for 10 s, where sonner's default is 4 s", () => {
    setWidth(1280);
    render(<Toaster />);
    expect(TOAST_ACTION_DURATION).toBeGreaterThanOrEqual(10_000);
    show(() => toast("Conversation archived", { action: { label: "Undo", onClick: () => {} }, duration: TOAST_ACTION_DURATION }));
    show(() => toast("Saved"));
    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
    expect(screen.getByText("Conversation archived")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(5_500));
    expect(screen.queryByText("Conversation archived")).not.toBeInTheDocument();
  });
});
