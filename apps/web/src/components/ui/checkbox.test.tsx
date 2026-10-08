import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Checkbox } from "./checkbox";

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
const icon = (box: HTMLElement, name: "check" | "minus") => box.querySelector(`svg.lucide-${name}`);

describe("Checkbox", () => {
  it("reads as mixed when indeterminate, and draws a minus instead of the tick", () => {
    render(<Checkbox aria-label="Select all posts" checked="indeterminate" />);
    const box = screen.getByRole("checkbox", { name: "Select all posts" });
    expect(box).toBePartiallyChecked();
    expect(box).toHaveAttribute("aria-checked", "mixed");
    expect(box).toHaveAttribute("data-state", "indeterminate");
    // Both glyphs render; the state shows one: the minus for indeterminate, the tick otherwise.
    expect(icon(box, "minus")).toHaveClass("hidden", "group-data-[state=indeterminate]/checkbox:block");
    expect(icon(box, "check")).toHaveClass("group-data-[state=indeterminate]/checkbox:hidden");
    expect(icon(box, "minus")).toHaveAttribute("aria-hidden", "true");
  });

  it("fills checked and indeterminate alike with brand and an on-brand glyph (3:1 on raised, C-071)", () => {
    render(<Checkbox aria-label="Select" checked />);
    const box = screen.getByRole("checkbox", { name: "Select" });
    expect(box).toBeChecked();
    expect(box).toHaveClass(
      "data-checked:bg-brand",
      "data-checked:border-brand",
      "data-checked:text-on-brand",
      "data-[state=indeterminate]:bg-brand",
      "data-[state=indeterminate]:border-brand",
      "data-[state=indeterminate]:text-on-brand",
    );
    // Not brand-strong (--primary): 2.96:1 against a selected (raised) row.
    expect(classes(box).filter((c) => c.includes("primary"))).toEqual([]);
    expect(icon(box, "check")).not.toBeNull();
  });

  it("is edged by --input when unchecked, with no --input fill, and keeps the global focus outline", () => {
    render(<Checkbox aria-label="Select" />);
    const box = screen.getByRole("checkbox", { name: "Select" });
    expect(box).not.toBeChecked();
    expect(box).toHaveClass("border-input", "rounded-sm", "size-4");
    const list = classes(box);
    expect(list.filter((c) => c.includes("bg-input"))).toEqual([]);
    expect(list).not.toContain("outline-none");
    expect(list.filter((c) => c.includes("ring-3") || c.startsWith("dark:"))).toEqual([]);
    expect(list).not.toContain("transition-all");
  });

  it("has a 40 × 32 hit area, 40 × 40 on coarse pointers", () => {
    render(<Checkbox aria-label="Select" />);
    expect(screen.getByRole("checkbox")).toHaveClass("after:-inset-x-3", "after:-inset-y-2", "pointer-coarse:after:-inset-3");
  });

  it("goes from indeterminate to checked on click, as a select-all does", async () => {
    const onCheckedChange = vi.fn();
    function SelectAll() {
      const [checked, setChecked] = useState<boolean | "indeterminate">("indeterminate");
      return (
        <Checkbox
          aria-label="Select all posts"
          checked={checked}
          onCheckedChange={(value) => {
            onCheckedChange(value);
            setChecked(value);
          }}
        />
      );
    }
    render(<SelectAll />);
    const box = screen.getByRole("checkbox", { name: "Select all posts" });
    await userEvent.click(box);
    expect(onCheckedChange).toHaveBeenCalledWith(true);
    expect(box).toBeChecked();
    expect(box).toHaveAttribute("data-state", "checked");
  });

  it("marks an invalid, unchecked box with the danger edge", () => {
    render(<Checkbox aria-label="Accept" aria-invalid />);
    const box = screen.getByRole("checkbox", { name: "Accept" });
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(box).toHaveClass("aria-invalid:data-unchecked:border-danger");
  });
});
