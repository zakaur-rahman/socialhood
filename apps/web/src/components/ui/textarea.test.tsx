import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Textarea } from "./textarea";

const classes = (el: HTMLElement) => el.className.split(/\s+/).filter(Boolean);

describe("Textarea", () => {
  it("is 16 px below md, so iOS doesn't zoom on focus, and 14 px from md", () => {
    render(<Textarea aria-label="Answer" />);
    expect(screen.getByRole("textbox", { name: "Answer" })).toHaveClass("max-md:text-base", "text-sm");
  });

  it("stays 16 px on phones when a call site still passes text-sm (CaptionEditor)", () => {
    render(<Textarea aria-label="Caption" className="min-h-28 resize-y bg-field text-sm focus:bg-raised" />);
    expect(screen.getByRole("textbox", { name: "Caption" })).toHaveClass("max-md:text-base");
  });

  it("uses the field surface and edge, the global focus outline and the danger edge when invalid", () => {
    render(<Textarea aria-label="Answer" aria-invalid />);
    const textarea = screen.getByRole("textbox", { name: "Answer" });
    expect(textarea).toHaveClass("bg-field", "border-input", "focus-visible:border-ring", "focus-visible:bg-raised", "aria-invalid:border-danger");
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    const list = classes(textarea);
    expect(list).not.toContain("outline-none");
    expect(list.filter((c) => c.includes("ring-3") || c.includes("destructive"))).toEqual([]);
  });

  it("keeps the message leading and grows with its content", () => {
    render(<Textarea aria-label="Answer" rows={6} />);
    const textarea = screen.getByRole("textbox", { name: "Answer" });
    expect(textarea).toHaveClass("leading-relaxed", "field-sizing-content", "min-h-20", "py-2");
    expect(textarea).toHaveAttribute("rows", "6");
  });
});
