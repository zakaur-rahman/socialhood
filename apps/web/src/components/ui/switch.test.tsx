import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Switch } from "./switch";

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);

describe("Switch", () => {
  it("is brand when on and pressed inside an --input edge when off", () => {
    render(<Switch aria-label="Active" />);
    const control = screen.getByRole("switch", { name: "Active" });
    expect(control).toHaveClass("data-checked:bg-brand", "data-checked:border-transparent", "data-unchecked:bg-pressed", "data-unchecked:border-input");
  });

  it("never fills its track with --input (UI-018 moves --input to a 40% control edge)", () => {
    render(<Switch aria-label="Active" />);
    const list = classes(screen.getByRole("switch"));
    expect(list.filter((c) => c.includes("bg-input") || c.includes("bg-primary"))).toEqual([]);
    expect(list.filter((c) => c.startsWith("dark:"))).toEqual([]);
  });

  it("keeps the global focus outline, names its transitions and stops the thumb under reduced motion", () => {
    render(<Switch aria-label="Active" />);
    const control = screen.getByRole("switch");
    const list = classes(control);
    expect(list).not.toContain("outline-none");
    expect(list).not.toContain("transition-all");
    expect(list.filter((c) => c.includes("ring-3"))).toEqual([]);
    expect(control).toHaveClass("transition-[background-color,border-color]", "duration-fast");
    const thumb = control.querySelector('[data-slot="switch-thumb"]');
    expect(thumb).toHaveClass("transition-transform", "motion-reduce:transition-none", "bg-fg", "data-checked:bg-on-brand");
  });

  it("is at least 40 px tall to a coarse pointer", () => {
    render(<Switch aria-label="Active" />);
    expect(screen.getByRole("switch")).toHaveClass("pointer-coarse:after:-inset-y-3", "pointer-coarse:data-[size=sm]:after:-inset-y-3.5");
  });

  it("toggles and reports its state", async () => {
    const onCheckedChange = vi.fn();
    render(<Switch aria-label="Active" onCheckedChange={onCheckedChange} />);
    const control = screen.getByRole("switch", { name: "Active" });
    expect(control).not.toBeChecked();
    await userEvent.click(control);
    expect(onCheckedChange).toHaveBeenCalledWith(true);
    expect(control).toBeChecked();
    expect(control).toHaveAttribute("data-state", "checked");
  });

  it("keeps its sizes", () => {
    render(<Switch aria-label="Small" size="sm" />);
    expect(screen.getByRole("switch")).toHaveAttribute("data-size", "sm");
  });
});
