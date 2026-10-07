import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Trash2 } from "lucide-react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FLOATING_ITEM, FLOATING_MOTION } from "@/components/ui/floating";
import { classes, expectReducedMotionCancels } from "@/test/overlays";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const words = (recipe: string) => recipe.split(/\s+/).filter(Boolean);

/** The highlight every item shares: the hover fill, the inset keyboard outline, 40 px on touch. */
function expectItemHighlight(item: Element) {
  expect(item).toHaveClass(
    "focus:bg-hover",
    "focus-visible:outline-2",
    "focus-visible:-outline-offset-2",
    "focus-visible:outline-ring",
    // Firefox: the outline also keys off the highlight while the keyboard moves it.
    "group-data-keyboard/floating:data-highlighted:outline-2",
    "group-data-keyboard/floating:data-highlighted:-outline-offset-2",
    "group-data-keyboard/floating:data-highlighted:outline-ring",
    "pointer-coarse:min-h-10",
    "rounded-md",
    "text-sm"
  );
  const list = classes(item);
  // Nothing hides the outline, and no shadcn leftovers: the 1.15:1 raised fill or icons and
  // secondary text forced white on the highlight.
  expect(list.filter((c) => /outline-(hidden|none)$/.test(c))).toEqual([]);
  expect(list.filter((c) => c.includes("bg-accent") || c.includes("text-accent-foreground") || c.startsWith("dark:"))).toEqual([]);
}

function Menu({ onDelete = () => {}, modal }: { onDelete?: () => void; modal?: boolean }) {
  return (
    <>
      <button type="button">Elsewhere on the page</button>
      <DropdownMenu modal={modal}>
        <DropdownMenuTrigger>More actions</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Automation</DropdownMenuLabel>
          <DropdownMenuItem>Duplicate</DropdownMenuItem>
          <DropdownMenuItem>Pause</DropdownMenuItem>
          <DropdownMenuItem>Move up</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 aria-hidden /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}

function Everything() {
  return (
    <DropdownMenu defaultOpen>
      <DropdownMenuTrigger>Filters</DropdownMenuTrigger>
      <DropdownMenuContent className="w-44 border-line bg-panel shadow-xl">
        <DropdownMenuLabel className="text-xs text-fg-secondary">Posts</DropdownMenuLabel>
        <DropdownMenuItem>Plain</DropdownMenuItem>
        <DropdownMenuCheckboxItem checked>Published</DropdownMenuCheckboxItem>
        <DropdownMenuRadioGroup value="all">
          <DropdownMenuRadioItem value="all">All</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSub open>
          <DropdownMenuSubTrigger>More</DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuItem>Nested</DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

describe("DropdownMenu (UI-013)", () => {
  it("highlights every kind of item with the hover fill and an inset keyboard outline (UI-ISS-001)", async () => {
    render(<Everything />);
    const menu = await screen.findByRole("menu", { name: "Filters" });
    expectItemHighlight(within(menu).getByRole("menuitem", { name: "Plain" }));
    expectItemHighlight(within(menu).getByRole("menuitemcheckbox", { name: "Published" }));
    expectItemHighlight(within(menu).getByRole("menuitemradio", { name: "All" }));
    const sub = within(menu).getByRole("menuitem", { name: "More" });
    expectItemHighlight(sub);
    expect(sub).toHaveClass("data-open:bg-pressed");
    expect(FLOATING_ITEM).toContain("focus:bg-hover");
  });

  it("a destructive item is danger-fg, icon and label alike, on a danger-soft highlight (UI-ISS-009)", async () => {
    const user = userEvent.setup();
    render(<Menu />);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    const item = await screen.findByRole("menuitem", { name: "Delete" });
    expect(item).toHaveAttribute("data-variant", "destructive");
    expect(item).toHaveClass(
      "data-[variant=destructive]:text-danger-fg",
      "data-[variant=destructive]:focus:bg-danger-soft",
      "data-[variant=destructive]:focus:text-danger-fg",
      "data-[variant=destructive]:*:[svg]:text-danger-fg"
    );
    // `danger` (#EF4444) is 4.38:1 as text: never on an item.
    expect(classes(item).filter((c) => c.includes("destructive") && !c.startsWith("data-[variant=destructive]:"))).toEqual([]);
    expect(classes(item).filter((c) => /text-(danger|destructive)$/.test(c))).toEqual([]);
    expectItemHighlight(item);
  });

  it("floats at least 192 px wide and as wide as its items, with the floating shadow (D-12)", async () => {
    const user = userEvent.setup();
    render(<Menu />);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    const content = await screen.findByRole("menu", { name: "More actions" });
    expect(content).toHaveAttribute("data-slot", "dropdown-menu-content");
    expect(content).toHaveClass("w-auto", "min-w-48", "shadow-floating", "ring-1", "ring-line", "rounded-lg", "bg-popover", "p-1");
    expect(content).not.toHaveClass("shadow-xl");
    // Not the trigger's width (wrong for icon triggers), and never wider than the viewport allows.
    expect(classes(content).filter((c) => c.includes("trigger-width"))).toEqual([]);
    expect(content).toHaveClass("max-w-(--radix-dropdown-menu-content-available-width)");
  });

  it("existing call-site classes still apply: a width replaces w-auto; today's surface patch is harmless", async () => {
    render(<Everything />);
    const content = await screen.findByRole("menu", { name: "Filters" });
    const list = classes(content);
    expect(list.filter((c) => /^w-/.test(c))).toEqual(["w-44"]);
    expect(list.filter((c) => /^shadow-/.test(c))).toEqual(["shadow-xl"]);
    expect(list.filter((c) => /^bg-/.test(c))).toEqual(["bg-panel"]);
    // The edge is a ring of its own, so the call site's shadow doesn't take it away.
    expect(list.filter((c) => /^ring-/.test(c))).toEqual(["ring-1", "ring-line"]);
  });

  it("moves in 120 ms with the enter and exit easings, a 97% zoom and a 4 px slide, and not at all under reduced motion", async () => {
    render(<Everything />);
    const content = await screen.findByRole("menu", { name: "Filters" });
    expect(content).toHaveClass(...words(FLOATING_MOTION));
    expect(content).toHaveClass("duration-fast", "data-open:ease-enter", "data-closed:ease-exit", "data-open:zoom-in-97", "data-[side=bottom]:slide-in-from-top-1");
    expect(content).not.toHaveClass("duration-100");
    expectReducedMotionCancels(content);
    const sub = document.querySelector('[data-slot="dropdown-menu-sub-content"]') as HTMLElement;
    expect(sub).toHaveClass("shadow-floating", "bg-popover", "min-w-48");
    expectReducedMotionCancels(sub);
  });

  it("labels are text-xs secondary text without a call-site class", async () => {
    render(<Everything />);
    const label = (await screen.findByText("Posts")) as HTMLElement;
    expect(label).toHaveClass("text-xs", "text-fg-secondary");
  });

  it("isn't modal: the page behind stays exposed, so nothing focusable hides under aria-hidden", async () => {
    const user = userEvent.setup();
    render(<Menu />);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    await screen.findByRole("menu");
    const outside = screen.getByRole("button", { name: "Elsewhere on the page" });
    expect(outside.closest("[aria-hidden]")).toBeNull();
    expect(document.querySelectorAll('[aria-hidden="true"] button')).toHaveLength(0);
  });

  it("a call site can still ask for a modal menu", async () => {
    const user = userEvent.setup();
    const { container } = render(<Menu modal />);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    await screen.findByRole("menu");
    await waitFor(() => expect(container).toHaveAttribute("aria-hidden", "true"));
  });

  it("keyboard: Enter opens on the first item, arrows and typeahead move, Esc closes back on the trigger", async () => {
    const user = userEvent.setup();
    render(<Menu />);
    const trigger = screen.getByRole("button", { name: "More actions" });
    trigger.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Duplicate" })).toHaveFocus());
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Pause" })).toHaveFocus();
    await user.keyboard("m");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Move up" })).toHaveFocus());
    await user.keyboard("{Tab}");
    expect(screen.getByRole("menuitem", { name: "Move up" })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  // Typeahead keeps consecutive letters. In the production build Radix kept only the last one
  // (Next's minifier dropped the call that stores them; patches/ restores it, see
  // radix-typeahead-build.test.ts). These run Radix unminified, so they guard the wrapper's handlers.
  function Conversation({ onSelect }: { onSelect: () => void }) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger>Conversation</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={onSelect}>Archive</DropdownMenuItem>
          <DropdownMenuItem onSelect={onSelect}>Mark as read</DropdownMenuItem>
          <DropdownMenuItem onSelect={onSelect}>Mark as spam</DropdownMenuItem>
          <DropdownMenuItem onSelect={onSelect}>Move</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  async function openConversation(onSelect = vi.fn()) {
    const user = userEvent.setup();
    render(<Conversation onSelect={onSelect} />);
    screen.getByRole("button", { name: "Conversation" }).focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Archive" })).toHaveFocus());
    return user;
  }

  it('typeahead: "Mo" reaches Move past Mark as read', async () => {
    const user = await openConversation();
    await user.keyboard("M");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Mark as read" })).toHaveFocus());
    await user.keyboard("o");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Move" })).toHaveFocus());
    expect(screen.getByRole("menu")).toHaveAttribute("data-keyboard");
  });

  it("typeahead: a space while typing is part of the search, not a choice", async () => {
    const onSelect = vi.fn();
    const user = await openConversation(onSelect);
    await user.keyboard("Mark as s");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Mark as spam" })).toHaveFocus());
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("marks the menu data-keyboard from a key press until the pointer moves, for the highlight's outline", async () => {
    const user = userEvent.setup();
    const onKeyDownCapture = vi.fn();
    const onPointerMove = vi.fn();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger>More actions</DropdownMenuTrigger>
        <DropdownMenuContent onKeyDownCapture={onKeyDownCapture} onPointerMove={onPointerMove}>
          <DropdownMenuItem>Duplicate</DropdownMenuItem>
          <DropdownMenuItem>Pause</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
    await user.click(screen.getByRole("button", { name: "More actions" }));
    const menu = await screen.findByRole("menu");
    expect(menu).toHaveClass("group/floating");
    expect(menu).not.toHaveAttribute("data-keyboard");
    await user.keyboard("{ArrowDown}");
    expect(menu).toHaveAttribute("data-keyboard");
    expect(onKeyDownCapture).toHaveBeenCalled();
    await user.pointer({ target: screen.getByRole("menuitem", { name: "Pause" }) });
    expect(menu).not.toHaveAttribute("data-keyboard");
    expect(onPointerMove).toHaveBeenCalled();
  });

  it("choosing an item by keyboard runs it and puts focus back on the trigger", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<Menu onDelete={onDelete} />);
    const trigger = screen.getByRole("button", { name: "More actions" });
    trigger.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Duplicate" })).toHaveFocus());
    await user.keyboard("{End}{Enter}");
    expect(onDelete).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
