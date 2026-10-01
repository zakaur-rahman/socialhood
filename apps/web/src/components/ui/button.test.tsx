import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

import { Button, buttonVariants } from "./button";

const VARIANTS = ["default", "secondary", "outline", "ghost", "destructive", "destructive-ghost", "link"] as const;
const SIZES = ["xs", "sm", "default", "lg", "xl", "icon-xs", "icon-sm", "icon", "icon-lg"] as const;

const classes = (el: Element) => el.getAttribute("class")!.split(/\s+/);

describe("Button variants (DESIGN_SYSTEM §8.2, §8.3)", () => {
  it("default is the primary: the brand gradient with on-brand text and a brightness hover", () => {
    render(<Button>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("data-variant", "default");
    expect(button).toHaveClass("bg-brand-gradient", "text-on-brand", "hover:brightness-110", "active:brightness-95");
    // Not the solid `bg-primary` (white on it was 3.63:1) and no colour hover painting under the gradient.
    expect(classes(button).filter((c) => /primary/.test(c))).toEqual([]);
  });

  it.each([
    ["secondary", ["bg-raised", "text-fg", "hover:bg-raised-hover"]],
    ["outline", ["border-line-strong", "hover:bg-hover", "aria-expanded:bg-pressed"]],
    ["ghost", ["hover:bg-hover", "aria-expanded:bg-pressed"]],
    ["destructive", ["bg-danger-fill", "text-on-brand", "hover:bg-danger-fill/90"]],
    ["destructive-ghost", ["text-danger-fg", "hover:bg-danger-soft"]],
    ["link", ["text-brand-fg", "hover:underline"]],
  ] as const)("%s uses the design-system tokens", (variant, expected) => {
    render(<Button variant={variant}>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass(...expected);
  });

  it.each(VARIANTS)("%s keeps the global focus outline: no outline removal, no ring halo", (variant) => {
    render(<Button variant={variant}>Go</Button>);
    const list = classes(screen.getByRole("button", { name: "Go" }));
    expect(list.filter((c) => /outline-(none|hidden)|ring-|focus-visible:border/.test(c))).toEqual([]);
  });

  it.each(VARIANTS)("%s uses no shadcn alias, palette colour or light-theme dark: class", (variant) => {
    render(<Button variant={variant}>Go</Button>);
    const list = classes(screen.getByRole("button", { name: "Go" }));
    expect(
      list.filter((c) => /(^|:)(bg|text|border)-(primary|secondary|muted|accent|destructive|input|background|foreground|white|black)\b|^dark:/.test(c)),
    ).toEqual([]);
  });

  it("transitions named properties for the fast duration, never transition-all or the outline colour", () => {
    render(<Button variant="ghost">Go</Button>);
    const button = screen.getByRole("button", { name: "Go" });
    expect(button).toHaveClass("transition-[color,background-color,border-color,filter]", "duration-fast", "ease-standard", "motion-reduce:transition-none");
    expect(button).not.toHaveClass("transition-all");
  });
});

describe("Button sizes (DESIGN_SYSTEM §8.4)", () => {
  it.each([
    ["xs", "h-6"],
    ["sm", "h-7"],
    ["default", "h-8"],
    ["lg", "h-9"],
  ] as const)("%s keeps its desktop height (%s) and is 40 px on a coarse pointer", (size, height) => {
    render(<Button size={size}>Go</Button>);
    const button = screen.getByRole("button", { name: "Go" });
    expect(button).toHaveClass(height, "pointer-coarse:min-h-10");
    // Touch sizing comes from the pointer, not the viewport width.
    expect(classes(button).filter((c) => /^(md|sm):/.test(c))).toEqual([]);
  });

  it("xl is 40 px on every pointer (settings forms)", () => {
    render(<Button size="xl">Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveClass("h-10");
  });

  it.each([
    ["icon-xs", "size-6"],
    ["icon-sm", "size-7"],
    ["icon", "size-8"],
    ["icon-lg", "size-9"],
  ] as const)("%s is %s and 40 px square on a coarse pointer", (size, square) => {
    render(<Button size={size} aria-label="More" />);
    expect(screen.getByRole("button", { name: "More" })).toHaveClass(square, "pointer-coarse:size-10");
  });

  it.each(["xs", "sm"] as const)("%s text is text-xs (no 12.8 px) with the small radius", (size) => {
    render(<Button size={size}>Go</Button>);
    const button = screen.getByRole("button", { name: "Go" });
    expect(button).toHaveClass("text-xs", "rounded-md");
    expect(button).not.toHaveClass("text-sm", "rounded-lg");
  });

  it.each(["icon-xs", "icon-sm"] as const)("%s has the small radius", (size) => {
    render(<Button size={size} aria-label="More" />);
    expect(screen.getByRole("button", { name: "More" })).toHaveClass("rounded-md");
  });

  it.each(["default", "lg", "xl", "icon", "icon-lg"] as const)("%s keeps rounded-lg and text-sm", (size) => {
    render(<Button size={size}>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass("rounded-lg", "text-sm");
  });

  it.each(SIZES)("%s has no arbitrary radius or text size", (size) => {
    render(<Button size={size}>Go</Button>);
    expect(classes(screen.getByRole("button", { name: "Go" })).filter((c) => /rounded-\[|text-\[/.test(c))).toEqual([]);
  });
});

describe("Button loading", () => {
  it("sets aria-busy, disables the button and shows a spinner that stops under reduced motion", () => {
    render(<Button loading>Save</Button>);
    // The label stays in the accessible name while it is hidden.
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    const spinner = button.querySelector('[data-slot="spinner"]')!;
    expect(spinner).toHaveAttribute("aria-hidden", "true");
    expect(spinner).toHaveClass("motion-safe:animate-spin");
    expect(spinner).not.toHaveClass("animate-spin");
  });

  it("keeps the width: the content stays laid out, transparent, in the spinner's grid cell", () => {
    render(
      <Button loading>
        <svg data-testid="icon" /> Save changes
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Save changes" });
    const content = within(button).getByText("Save changes");
    expect(content).toHaveClass("opacity-0", "col-start-1", "row-start-1");
    expect(content).not.toHaveClass("hidden", "invisible", "sr-only");
    expect(content).toContainElement(screen.getByTestId("icon"));
    expect(button.querySelector('[data-slot="spinner"]')).toHaveClass("col-start-1", "row-start-1");
    expect(content.parentElement).toHaveClass("grid");
  });

  it.each([
    ["xs", "size-3"],
    ["icon-xs", "size-3"],
    ["sm", "size-3.5"],
    ["default", "size-4"],
    ["xl", "size-4"],
  ] as const)("the spinner matches the %s icon size (%s)", (size, iconSize) => {
    render(<Button size={size} loading aria-label="Save" />);
    expect(screen.getByRole("button", { name: "Save" }).querySelector('[data-slot="spinner"]')).toHaveClass(iconSize);
  });

  it("without loading, renders its children as they are, enabled and not busy", () => {
    render(<Button>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).toBeEnabled();
    expect(button.querySelector('[data-slot="spinner"]')).toBeNull();
    expect(button.firstChild?.nodeType).toBe(Node.TEXT_NODE);
  });

  it("disabled stays disabled when not loading", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});

describe("Overrides until the area sweeps migrate them", () => {
  it("a danger fill given after the variant drops the gradient, so today's danger overrides stay red", () => {
    const merged = cn(buttonVariants(), "bg-danger-fill text-white hover:bg-danger-fill/90");
    expect(merged.split(" ")).toContain("bg-danger-fill");
    expect(merged).not.toMatch(/bg-brand-gradient/);

    render(<Button className="bg-danger-fill text-white hover:bg-danger-fill/90">Delete</Button>);
    const button = screen.getByRole("button", { name: "Delete" });
    expect(button).toHaveClass("bg-danger-fill");
    expect(button).not.toHaveClass("bg-brand-gradient");
  });

  it("the pasted gradient on a default Button is a harmless duplicate", () => {
    render(<Button className="bg-brand-gradient text-white">Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(classes(button).filter((c) => c === "bg-brand-gradient")).toHaveLength(1);
    expect(button).toHaveClass("text-white", "hover:brightness-110");
    expect(button).not.toHaveClass("text-on-brand");
  });

  it("asChild merges the child's own classes, so an override on the child wins", () => {
    render(
      <Button asChild size="sm">
        <a href="/x" className="bg-danger-fill text-white">
          Open
        </a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Open" });
    expect(link).toHaveAttribute("data-slot", "button");
    expect(link).toHaveClass("bg-danger-fill", "text-white", "h-7", "rounded-md");
    expect(link).not.toHaveClass("bg-brand-gradient", "text-on-brand", "rounded-lg");
  });

  it("an AlertDialogAction with a danger fill is red, not the gradient (the Disconnect confirmation)", () => {
    render(
      <AlertDialog open>
        <AlertDialogContent>
          <AlertDialogTitle>Disconnect?</AlertDialogTitle>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction className="bg-danger-fill text-white hover:bg-danger-fill/90">Disconnect</AlertDialogAction>
        </AlertDialogContent>
      </AlertDialog>,
    );
    const action = screen.getByRole("button", { name: "Disconnect" });
    expect(action).toHaveClass("bg-danger-fill", "hover:bg-danger-fill/90");
    expect(action).not.toHaveClass("bg-brand-gradient");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveClass("border-line-strong");
  });
});
