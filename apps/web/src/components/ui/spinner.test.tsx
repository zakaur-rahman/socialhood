import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Spinner } from "./spinner";

describe("Spinner (DESIGN_SYSTEM §7.4)", () => {
  it("spins only when motion is allowed, and is decorative by default", () => {
    const { container } = render(<Spinner />);
    const spinner = container.querySelector('[data-slot="spinner"]')!;
    expect(spinner).toHaveClass("motion-safe:animate-spin", "size-4");
    expect(spinner).not.toHaveClass("animate-spin");
    expect(spinner).toHaveAttribute("aria-hidden", "true");
  });

  it.each([
    ["xs", "size-3"],
    ["sm", "size-3.5"],
    ["default", "size-4"],
    ["lg", "size-5"],
  ] as const)("size %s is %s", (size, cls) => {
    const { container } = render(<Spinner size={size} />);
    expect(container.querySelector('[data-slot="spinner"]')).toHaveClass(cls);
  });

  it("is announced when it is the only sign of loading", () => {
    render(<Spinner role="status" aria-label="Loading posts" />);
    const spinner = screen.getByRole("status", { name: "Loading posts" });
    expect(spinner).not.toHaveAttribute("aria-hidden");
  });

  it("takes a colour from its caller", () => {
    const { container } = render(<Spinner className="text-brand-fg" />);
    expect(container.querySelector('[data-slot="spinner"]')).toHaveClass("text-brand-fg", "motion-safe:animate-spin");
  });
});
