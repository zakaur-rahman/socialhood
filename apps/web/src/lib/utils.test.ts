import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn knows the design system's utilities (C-070)", () => {
  it("treats the gradients and the glow as background images, not colours", () => {
    expect(cn("bg-panel", "bg-glow-brand")).toBe("bg-panel bg-glow-brand");
    expect(cn("bg-brand-gradient", "bg-glow-brand")).toBe("bg-glow-brand");
    expect(cn("bg-shell-gradient", "bg-brand-gradient-decor")).toBe("bg-brand-gradient-decor");
    expect(cn("bg-[url(/a.png)]", "bg-glow-brand")).toBe("bg-glow-brand");
  });

  it("lets a colour given later replace a gradient (a danger override on a gradient Button)", () => {
    expect(cn("bg-brand-gradient text-on-brand", "bg-danger-fill")).toBe("text-on-brand bg-danger-fill");
    expect(cn("hover:bg-brand-gradient", "hover:bg-hover")).toBe("hover:bg-hover");
    // A gradient given later still layers over the variant's colour.
    expect(cn("bg-primary", "bg-brand-gradient")).toBe("bg-primary bg-brand-gradient");
  });

  it("lets a motion token replace a duration or an easing", () => {
    expect(cn("duration-100", "duration-slow")).toBe("duration-slow");
    expect(cn("duration-fast", "duration-200")).toBe("duration-200");
    expect(cn("ease-out", "ease-enter")).toBe("ease-enter");
    expect(cn("ease-standard", "ease-exit")).toBe("ease-exit");
  });

  it("treats the elevation shadows as shadow sizes, not colours (C-071)", () => {
    expect(cn("shadow-floating", "shadow-xl")).toBe("shadow-xl");
    expect(cn("shadow-xl", "shadow-overlay")).toBe("shadow-overlay");
    expect(cn("shadow-floating", "shadow-none")).toBe("shadow-none");
    // A shadow colour layers on a size; it doesn't replace it.
    expect(cn("shadow-overlay", "shadow-black")).toBe("shadow-overlay shadow-black");
    expect(cn("bg-popover", "bg-overlay")).toBe("bg-overlay");
  });

  it("treats the crop mask as a shadow too, and brand-soft-hover as a colour (C-073)", () => {
    expect(cn("shadow-crop-mask", "shadow-none")).toBe("shadow-none");
    expect(cn("shadow-xl", "shadow-crop-mask")).toBe("shadow-crop-mask");
    expect(cn("bg-brand-soft", "bg-brand-soft-hover")).toBe("bg-brand-soft-hover");
    expect(cn("hover:bg-brand-soft-hover", "hover:bg-hover")).toBe("hover:bg-hover");
  });

  it("still merges colours and sizes as tailwind-merge does", () => {
    expect(cn("bg-primary", "bg-danger-fill")).toBe("bg-danger-fill");
    expect(cn("hover:bg-hover", "hover:bg-pressed")).toBe("hover:bg-pressed");
    expect(cn("text-sm", "text-2xs")).toBe("text-2xs");
    expect(cn("px-2", false, { "py-1": true })).toBe("px-2 py-1");
  });
});
