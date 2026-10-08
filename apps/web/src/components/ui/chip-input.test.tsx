import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { ChipInput } from "./chip-input";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { fieldControlClass } from "./input";

type Props = Omit<ComponentProps<typeof ChipInput>, "value" | "onValueChange">;

function Harness({ initial = [], ...props }: Props & { initial?: string[] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <ChipInput value={value} onValueChange={setValue} inputLabel="Add a phrase" listLabel="Phrases" {...props} />
      <pre data-testid="value">{JSON.stringify(value)}</pre>
    </>
  );
}

const value = () => JSON.parse(screen.getByTestId("value").textContent ?? "[]") as string[];
const field = (name = "Add a phrase") => screen.getByRole("textbox", { name });
const control = () => field().closest("[data-slot=chip-input-control]") as HTMLElement;
const classes = (value: string) => value.split(/\s+/).filter(Boolean);

describe("ChipInput: adding", () => {
  it("adds on Enter, trims and collapses spaces, and says what it added", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(field(), "  free   shipping {Enter}");
    expect(value()).toEqual(["free shipping"]);
    expect(field()).toHaveValue("");
    expect(screen.getByRole("list", { name: "Phrases" })).toHaveTextContent("free shipping");
    expect(screen.getByRole("status")).toHaveTextContent("Added “free shipping”.");
    expect(screen.getByText("1 of 20")).toBeInTheDocument();
  });

  it("keeps commas inside a phrase by default and splits a pasted list by lines", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(field(), "Free shipping over ₹3,000{Enter}");
    expect(value()).toEqual(["Free shipping over ₹3,000"]);
    await user.click(field());
    await user.paste("Say thanks\nUse first names\r\n\nSign off, warmly");
    expect(value()).toEqual(["Free shipping over ₹3,000", "Say thanks", "Use first names", "Sign off, warmly"]);
    expect(screen.getByRole("status")).toHaveTextContent("Added 3.");
  });

  it("with separator=comma, a typed comma adds and a paste splits on commas, semicolons, tabs and lines", async () => {
    const user = userEvent.setup();
    render(<Harness separator="comma" />);
    await user.type(field(), "link,price{Enter}");
    expect(value()).toEqual(["link", "price"]);
    await user.click(field());
    await user.paste("size; colour\tstock\ndetails");
    expect(value()).toEqual(["link", "price", "size", "colour", "stock", "details"]);
  });

  it("with separator=comma, splits a comma that arrives without a key event (phone keyboards)", () => {
    render(<Harness separator="comma" />);
    fireEvent.change(field(), { target: { value: "menu" } });
    expect(field()).toHaveValue("menu");
    fireEvent.change(field(), { target: { value: "menu, size" } });
    expect(value()).toEqual(["menu", "size"]);
    expect(field()).toHaveValue("");
  });

  it("by default, a comma that arrives without a key event stays in the phrase", () => {
    render(<Harness />);
    fireEvent.change(field(), { target: { value: "Free shipping over ₹3," } });
    expect(field()).toHaveValue("Free shipping over ₹3,");
    expect(value()).toEqual([]);
  });

  it("adds what is typed when the field loses focus", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(field(), "Be brief");
    await user.tab();
    expect(value()).toEqual(["Be brief"]);
  });

  it("ignores Enter while an input method is composing", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(field(), "नमस्ते");
    field().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", isComposing: true, bubbles: true }));
    expect(value()).toEqual([]);
    expect(field()).toHaveValue("नमस्ते");
  });

  it("uses a custom split for typed and pasted text", async () => {
    const user = userEvent.setup();
    render(<Harness split={(text) => text.split("|").map((part) => part.trim())} />);
    await user.type(field(), "a | b{Enter}");
    expect(value()).toEqual(["a", "b"]);
  });
});

describe("ChipInput: validation, maximum and counter", () => {
  it("skips duplicates ignoring case by default", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Price"]} />);
    await user.type(field(), "PRICE{Enter}");
    expect(value()).toEqual(["Price"]);
    expect(screen.getByRole("status")).toHaveTextContent("That one is already in the list.");
    await user.click(field());
    await user.paste("price\nprice ");
    expect(screen.getByRole("status")).toHaveTextContent("2 were already in the list.");
  });

  it("compares duplicates through normalize", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["price"]} normalize={(item) => item.normalize("NFKC").toLowerCase()} />);
    await user.type(field(), "ｐｒｉｃｅ{Enter}");
    expect(value()).toEqual(["price"]);
  });

  it("cuts items to maxLength", async () => {
    const user = userEvent.setup();
    render(<Harness maxLength={5} inputMaxLength={20} />);
    await user.type(field(), "abcdefgh{Enter}");
    expect(value()).toEqual(["abcde"]);
    expect(field()).toHaveAttribute("maxLength", "20");
  });

  it("holds at most max items: leaves the rest out, counts, and stops taking text when full", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["a"]} max={3} placeholder="Type a phrase" />);
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    await user.click(field());
    await user.paste("b\nc\nd\ne");
    expect(value()).toEqual(["a", "b", "c"]);
    expect(screen.getByRole("status")).toHaveTextContent("Up to 3. 2 left out.");
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
    expect(field()).toBeDisabled();
    expect(field()).not.toHaveAttribute("placeholder");
    // The chips stay removable at the maximum, and the field takes text again.
    expect(screen.getByRole("button", { name: "Remove b" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Remove b" }));
    expect(field()).toBeEnabled();
    expect(field()).toHaveFocus();
    expect(field()).toHaveAttribute("placeholder", "Type a phrase");
  });

  it("says things its own way through messages", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        initial={["lawyer"]}
        messages={{ counter: (count, max) => `${count} of ${max} used`, duplicates: () => "Already there." }}
      />,
    );
    expect(screen.getByText("1 of 20 used")).toBeInTheDocument();
    await user.type(field(), "Lawyer{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("Already there.");
  });
});

describe("ChipInput: removing", () => {
  it("removes with a chip's button, or the last chip with Backspace in the empty field, and returns focus", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["link", "price", "details"]} />);
    await user.click(screen.getByRole("button", { name: "Remove price" }));
    expect(value()).toEqual(["link", "details"]);
    expect(screen.getByRole("status")).toHaveTextContent("Removed “price”.");
    expect(field()).toHaveFocus();
    await user.keyboard("{Backspace}");
    expect(value()).toEqual(["link"]);
    expect(screen.getByRole("status")).toHaveTextContent("Removed “details”.");
  });

  it("Backspace in a field with text edits the text, not the chips", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["link"]} />);
    await user.type(field(), "ab{Backspace}");
    expect(field()).toHaveValue("a");
    expect(value()).toEqual(["link"]);
  });

  it("disabled: nothing can be added or removed, and the box is dimmed", () => {
    render(<Harness initial={["link"]} disabled />);
    expect(field()).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove link" })).toBeDisabled();
    expect(control()).toHaveAttribute("data-disabled", "true");
    expect(control()).toHaveClass("data-disabled:opacity-50");
  });
});

describe("ChipInput: Add button", () => {
  it("adds with the button, keeps focus in the field, and doesn't add on blur", async () => {
    const user = userEvent.setup();
    render(<Harness addButton />);
    const add = screen.getByRole("button", { name: "Add" });
    expect(add).toBeDisabled();
    await user.type(field(), "cancel my order");
    expect(add).toBeEnabled();
    await user.click(add);
    expect(value()).toEqual(["cancel my order"]);
    expect(field()).toHaveFocus();
    await user.type(field(), "refund");
    await user.tab();
    expect(value()).toEqual(["cancel my order"]);
    expect(field()).toHaveValue("refund");
  });
});

describe("ChipInput: labels, errors and Field", () => {
  it("names the field and the list, and describes the field with the hint and the counter", () => {
    render(<Harness initial={["a"]} />);
    expect(field()).toHaveAccessibleDescription("Press Enter to add. Paste a list to add several. 1 of 20");
    expect(screen.getByRole("list", { name: "Phrases" })).toBeInTheDocument();
  });

  it("explains the comma in the comma hint; hint={null} hides it", () => {
    const { unmount } = render(<Harness separator="comma" />);
    expect(screen.getByText("Press Enter or type a comma to add. Paste a list to add several.")).toBeInTheDocument();
    unmount();
    render(<Harness hint={null} />);
    expect(field()).toHaveAccessibleDescription("0 of 20");
  });

  it("shows an error on the field: aria-invalid, described, danger edge", () => {
    render(<Harness error="Add at least one phrase." />);
    expect(field()).toHaveAttribute("aria-invalid", "true");
    expect(field()).toHaveAccessibleDescription(/Add at least one phrase\./);
    expect(screen.getByText("Add at least one phrase.")).toHaveClass("text-xs", "text-danger-fg");
    expect(control()).toHaveAttribute("data-invalid", "true");
    expect(control()).toHaveClass("data-invalid:border-danger");
  });

  it("inside a Field: the FieldLabel names it, descriptions and errors are linked, invalid and disabled follow", () => {
    const { rerender } = render(
      <Field>
        <FieldLabel>Keywords</FieldLabel>
        <ChipInput value={["link"]} onValueChange={() => {}} hint={null} />
        <FieldDescription>Messages with any of these start the automation.</FieldDescription>
        <FieldError>Add at least one keyword.</FieldError>
      </Field>,
    );
    const input = screen.getByRole("textbox", { name: "Keywords" });
    expect(input).toHaveAccessibleDescription(
      "1 of 20 Messages with any of these start the automation. Add at least one keyword.",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.closest("[data-slot=chip-input-control]")).toHaveAttribute("data-invalid", "true");

    rerender(
      <Field disabled>
        <FieldLabel>Keywords</FieldLabel>
        <ChipInput value={["link"]} onValueChange={() => {}} />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Keywords" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove link" })).toBeDisabled();
  });
});

describe("ChipInput: look", () => {
  it("is a field: the field recipe on the box, 16 px text below md, the focus outline on the box", () => {
    render(<Harness />);
    const box = control();
    const recipe = classes(fieldControlClass).filter((c) => !["px-3"].includes(c));
    expect(box).toHaveClass(...recipe);
    expect(box).toHaveClass(
      "text-sm",
      "max-md:text-base",
      "min-h-10",
      "has-[input:focus-visible]:outline-2",
      "has-[input:focus-visible]:outline-offset-2",
      "has-[input:focus-visible]:outline-ring",
      "has-[input:focus-visible]:border-ring",
      "has-[input:focus-visible]:bg-raised",
    );
    const list = classes(box.className);
    expect(list.filter((c) => c.includes("ring-3") || c.includes("ring-ring/50"))).toEqual([]);
    expect(list).not.toContain("transition-all");
    // The text field hands its outline to the box (the replacement above), nothing else.
    expect(field()).toHaveClass("focus-visible:outline-none", "placeholder:text-muted-foreground");
  });

  it("chips are brand-soft pills whose × keeps a 24 px target, 40 px on coarse pointers (rows 40 px apart there)", () => {
    render(<Harness initial={["link"]} />);
    const chip = screen.getByRole("listitem");
    expect(chip).toHaveClass("rounded-full", "bg-brand-soft", "text-brand-fg", "text-sm", "pointer-coarse:min-h-8");
    expect(control()).toHaveClass("gap-1.5", "pointer-coarse:gap-y-2");
    const remove = screen.getByRole("button", { name: "Remove link" });
    expect(remove).toHaveClass("size-5", "after:-inset-0.5", "pointer-coarse:after:-inset-2.5", "hover:bg-hover");
    expect(classes(remove.className).filter((c) => c.includes("white/"))).toEqual([]);
  });
});
