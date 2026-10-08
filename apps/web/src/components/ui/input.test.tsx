import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fieldControlClass, Input, inputVariants } from "./input";
import { Textarea } from "./textarea";

const classes = (value: string) => value.split(/\s+/).filter(Boolean);

describe("Input", () => {
  it("is a field: the field surface, the --input edge, raised and ring-bordered on focus, danger when invalid", () => {
    render(<Input aria-label="Name" />);
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input).toHaveClass(
      "bg-field",
      "border-input",
      "rounded-lg",
      "px-3",
      "focus-visible:bg-raised",
      "focus-visible:border-ring",
      "aria-invalid:border-danger",
      "disabled:opacity-50",
    );
  });

  it("keeps the global focus outline: no outline-none, no 50% halo, no dark: classes, no transition-all", () => {
    render(<Input aria-label="Name" />);
    const list = classes(screen.getByRole("textbox").className);
    expect(list).not.toContain("outline-none");
    expect(list.filter((c) => c.includes("ring-3") || c.includes("ring-ring/50"))).toEqual([]);
    expect(list.filter((c) => c.startsWith("dark:"))).toEqual([]);
    expect(list).not.toContain("transition-all");
    expect(list).toContain("transition-[color,background-color,border-color]");
  });

  it("is 16 px below md (no iOS zoom) and 14 px from md, even when a call site adds text-sm", () => {
    render(<Input aria-label="Name" className="text-sm" />);
    expect(screen.getByRole("textbox")).toHaveClass("max-md:text-base", "text-sm");
    // The base recipe itself
    expect(classes(fieldControlClass)).toEqual(expect.arrayContaining(["text-sm", "max-md:text-base"]));
  });

  it("takes a size on the control ladder, 40 px on coarse pointers at every size", () => {
    const heights = { sm: "h-7", default: "h-8", lg: "h-9", xl: "h-10" } as const;
    for (const [size, height] of Object.entries(heights) as [keyof typeof heights, string][]) {
      const { unmount } = render(<Input aria-label={size} size={size} />);
      const input = screen.getByRole("textbox", { name: size });
      expect(input).toHaveAttribute("data-size", size);
      expect(input).toHaveClass(height, "pointer-coarse:min-h-10");
      unmount();
    }
    expect(classes(inputVariants())).toContain("h-8");
  });

  it("lets a call site's height win (overrides stay harmless until the sweeps delete them)", () => {
    render(<Input aria-label="Name" className="h-9 bg-field" />);
    const list = classes(screen.getByRole("textbox").className);
    expect(list).toContain("h-9");
    expect(list).not.toContain("h-8");
  });

  it.each(["date", "time", "datetime-local", "month", "week"])(
    "a native %s field shows focus while its picker button has it (the field is then only :focus-within)",
    (type) => {
      const { container } = render(<Input aria-label="When" type={type} />);
      const input = container.querySelector("input")!;
      expect(input).toHaveAttribute("type", type);
      // The global outline's values and the field's ring border and raised fill, from :focus-within.
      expect(input).toHaveClass(
        "focus-within:outline-2",
        "focus-within:outline-offset-2",
        "focus-within:outline-ring",
        "focus-within:border-ring",
        "focus-within:bg-raised",
        "focus-visible:border-ring",
      );
      expect(classes(input.className).filter((c) => c.includes("outline-none") || c.includes("transition-all"))).toEqual([]);
    },
  );

  it.each(["text", "search", "email", "url", undefined])("a %s field keeps the :focus-visible recipe only", (type) => {
    render(<Input aria-label="Name" type={type} />);
    const list = classes(screen.getByRole(type === "search" ? "searchbox" : "textbox").className);
    expect(list.filter((c) => c.startsWith("focus-within:"))).toEqual([]);
    expect(list).toContain("focus-visible:border-ring");
  });

  it("passes native props and aria-invalid through", () => {
    render(<Input aria-label="Web address" type="url" placeholder="https://" aria-invalid disabled />);
    const input = screen.getByRole("textbox", { name: "Web address" });
    expect(input).toHaveAttribute("type", "url");
    expect(input).toHaveAttribute("placeholder", "https://");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toBeDisabled();
  });
});

describe("Input and Textarea", () => {
  it("share one field recipe, so on one card they look the same", () => {
    render(
      <>
        <Input aria-label="Question" />
        <Textarea aria-label="Answer" />
      </>,
    );
    const recipe = classes(fieldControlClass);
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveClass(...recipe);
    expect(screen.getByRole("textbox", { name: "Answer" })).toHaveClass(...recipe);
  });
});
