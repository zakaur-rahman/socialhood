import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it } from "vitest";

import { FLOATING_MOTION } from "@/components/ui/floating";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { classes, expectReducedMotionCancels } from "@/test/overlays";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const words = (recipe: string) => recipe.split(/\s+/).filter(Boolean);

const ZONES = ["Asia/Kolkata", "Asia/Dubai", "Europe/London", "America/New_York"];

function TimeZone({
  size,
  className,
  position,
}: {
  size?: "sm" | "default" | "lg" | "xl";
  className?: string;
  position?: "popper" | "item-aligned";
}) {
  const [value, setValue] = useState("Asia/Kolkata");
  return (
    <>
      <p>Saved: {value}</p>
      <Select value={value} onValueChange={setValue}>
        <SelectTrigger size={size} className={className} aria-label="Time zone">
          <SelectValue />
        </SelectTrigger>
        <SelectContent position={position}>
          {ZONES.map((zone) => (
            <SelectItem key={zone} value={zone}>
              {zone}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </>
  );
}

describe("Select (UI-013)", () => {
  it("the trigger is on the Input recipe: field surface, --input edge, outline focus with a ring border, no dark: or halo", () => {
    render(<TimeZone />);
    const trigger = screen.getByRole("combobox", { name: "Time zone" });
    expect(trigger).toHaveClass(
      "bg-field",
      "border",
      "border-input",
      "rounded-lg",
      "text-fg",
      "text-sm",
      "max-md:text-base",
      "focus-visible:border-ring",
      "focus-visible:bg-raised",
      "aria-invalid:border-danger",
      "disabled:opacity-50",
      "data-placeholder:text-muted-foreground",
      "transition-[color,background-color,border-color]",
      "duration-fast"
    );
    const list = classes(trigger);
    // shadcn's near-transparent stock field (UI-ISS-030). (Input's inert `file:` classes come along.)
    expect(list.filter((c) => /^(dark:|bg-transparent|bg-input)/.test(c))).toEqual([]);
    expect(list.filter((c) => /ring-(3|ring\/50)|ring-destructive|outline-(none|hidden)$|transition-all/.test(c))).toEqual([]);
  });

  it("looks like an Input of the same size beside it: every Input class but the full width", () => {
    for (const size of ["sm", "default", "lg", "xl"] as const) {
      const { unmount } = render(
        <>
          <Input size={size} aria-label="Name" />
          <TimeZone size={size} />
        </>
      );
      const input = classes(screen.getByRole("textbox", { name: "Name" }));
      const trigger = classes(screen.getByRole("combobox", { name: "Time zone" }));
      expect(input.filter((c) => c !== "w-full" && !trigger.includes(c))).toEqual([]);
      expect(trigger).toContain("w-fit");
      unmount();
    }
  });

  it("sizes on the control ladder (28/32/36/40 px), 40 px on coarse pointers at every size", () => {
    const heights = { sm: "h-7", default: "h-8", lg: "h-9", xl: "h-10" } as const;
    for (const [size, height] of Object.entries(heights) as [keyof typeof heights, string][]) {
      const { unmount } = render(<TimeZone size={size} />);
      const trigger = screen.getByRole("combobox");
      expect(trigger).toHaveAttribute("data-size", size);
      expect(classes(trigger).filter((c) => /^h-/.test(c))).toEqual([height]);
      expect(trigger).toHaveClass("pointer-coarse:min-h-10", "rounded-lg");
      unmount();
    }
  });

  it("existing call-site classes still apply: a height or width replaces the size's", () => {
    render(<TimeZone className="h-9 w-full" />);
    const list = classes(screen.getByRole("combobox"));
    expect(list.filter((c) => /^h-/.test(c))).toEqual(["h-9"]);
    expect(list.filter((c) => /^w-/.test(c))).toEqual(["w-full"]);
  });

  it("the options float on the shared surface and motion, instant under reduced motion; item-aligned doesn't move", async () => {
    const user = userEvent.setup();
    render(<TimeZone position="popper" />);
    await user.click(screen.getByRole("combobox", { name: "Time zone" }));
    const listbox = await screen.findByRole("listbox");
    const content = listbox.closest('[data-slot="select-content"]') ?? listbox;
    expect(content).toHaveClass("shadow-floating", "ring-1", "ring-line", "rounded-lg", "bg-popover", "min-w-36", ...words(FLOATING_MOTION));
    expect(content).not.toHaveClass("duration-100", "shadow-md", "shadow-xl");
    expectReducedMotionCancels(content);
    expect(content).toHaveClass("data-[align-trigger=true]:animate-none");
  });

  it("options share the menu highlight and are 40 px on coarse pointers", async () => {
    const user = userEvent.setup();
    render(<TimeZone />);
    await user.click(screen.getByRole("combobox", { name: "Time zone" }));
    const option = await screen.findByRole("option", { name: "Asia/Dubai" });
    expect(option).toHaveClass(
      "focus:bg-hover",
      "focus-visible:outline-2",
      "focus-visible:-outline-offset-2",
      "focus-visible:outline-ring",
      "group-data-keyboard/floating:data-highlighted:outline-2",
      "pointer-coarse:min-h-10"
    );
    expect(classes(option).filter((c) => /outline-(hidden|none)$/.test(c) || c.includes("accent"))).toEqual([]);
    const listbox = screen.getByRole("listbox");
    expect(listbox).toHaveClass("group/floating");
    await user.keyboard("{ArrowDown}");
    expect(listbox).toHaveAttribute("data-keyboard");
  });

  it("keyboard: opens on the chosen option, arrows and typeahead move, Enter chooses and focus returns to the trigger", async () => {
    const user = userEvent.setup();
    render(<TimeZone />);
    const trigger = screen.getByRole("combobox", { name: "Time zone" });
    trigger.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("option", { name: "Asia/Kolkata" })).toHaveFocus());
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: "Asia/Dubai" })).toHaveFocus();
    await user.keyboard("eu");
    await waitFor(() => expect(screen.getByRole("option", { name: "Europe/London" })).toHaveFocus());
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    expect(screen.getByText("Saved: Europe/London")).toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("Esc closes without choosing and puts focus back on the trigger", async () => {
    const user = userEvent.setup();
    render(<TimeZone />);
    const trigger = screen.getByRole("combobox", { name: "Time zone" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    await screen.findByRole("listbox");
    await user.keyboard("{ArrowDown}{Escape}");
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    expect(screen.getByText("Saved: Asia/Kolkata")).toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
