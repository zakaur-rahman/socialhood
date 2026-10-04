import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FLOATING_MOTION, FLOATING_SURFACE } from "@/components/ui/floating";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { classes, expectReducedMotionCancels } from "@/test/overlays";

const words = (recipe: string) => recipe.split(/\s+/).filter(Boolean);
const content = () => document.querySelector('[data-slot="popover-content"]') as HTMLElement;

function Example({ className }: { className?: string }) {
  return (
    <>
      <button type="button">Elsewhere on the page</button>
      <Popover>
        <PopoverTrigger>Why this reply?</PopoverTrigger>
        <PopoverContent className={className}>
          <p>Matched the FAQ “Do you ship to Pune?”</p>
          <button type="button">Edit the FAQ</button>
        </PopoverContent>
      </Popover>
    </>
  );
}

describe("Popover (UI-013)", () => {
  it("floats on the shared surface with the spec's shadow, so call sites don't add one", async () => {
    const user = userEvent.setup();
    render(<Example />);
    await user.click(screen.getByRole("button", { name: "Why this reply?" }));
    await screen.findByRole("dialog");
    expect(content()).toHaveClass(...words(FLOATING_SURFACE));
    expect(content()).toHaveClass("shadow-xl", "ring-1", "bg-popover", "rounded-lg", "w-72");
    expect(content()).not.toHaveClass("shadow-md");
  });

  it("moves in 120 ms with the enter and exit easings, and not at all under reduced motion", async () => {
    const user = userEvent.setup();
    render(<Example />);
    await user.click(screen.getByRole("button", { name: "Why this reply?" }));
    await screen.findByRole("dialog");
    expect(content()).toHaveClass(...words(FLOATING_MOTION));
    expect(content()).toHaveClass("duration-fast", "data-open:ease-enter", "data-closed:ease-exit", "data-open:zoom-in-97");
    expect(classes(content())).not.toContain("duration-100");
    expectReducedMotionCancels(content());
  });

  it("existing call-site classes still apply (width, padding, today's surface patch)", async () => {
    const user = userEvent.setup();
    render(<Example className="w-80 border-line bg-panel p-3 shadow-xl" />);
    await user.click(screen.getByRole("button", { name: "Why this reply?" }));
    await screen.findByRole("dialog");
    const list = classes(content());
    expect(list.filter((c) => /^w-/.test(c))).toEqual(["w-80"]);
    expect(list.filter((c) => /^p-/.test(c))).toEqual(["p-3"]);
    expect(list.filter((c) => /^shadow-/.test(c))).toEqual(["shadow-xl"]);
  });

  it("keyboard: Enter opens with focus inside, Esc closes back on the trigger", async () => {
    const user = userEvent.setup();
    render(<Example />);
    const trigger = screen.getByRole("button", { name: "Why this reply?" });
    trigger.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit the FAQ" })).toHaveFocus());
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});
