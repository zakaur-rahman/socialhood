import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Field, FieldDescription, FieldLabel } from "./field";
import { fieldControlClass } from "./input";
import { SearchInput } from "./search-input";

function Controlled({ onChange }: { onChange?: (value: string) => void }) {
  const [text, setText] = useState("");
  return (
    <SearchInput
      label="Search automations"
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onChange?.(event.target.value);
      }}
    />
  );
}

const classes = (value: string) => value.split(/\s+/).filter(Boolean);

describe("SearchInput", () => {
  it("is a labelled search field with a leading icon, on the Input recipe", () => {
    render(<SearchInput label="Search accounts" placeholder="Search by name" className="flex-1" />);
    const input = screen.getByRole("searchbox", { name: "Search accounts" });
    expect(input).toHaveAttribute("type", "search");
    expect(input).toHaveAttribute("autocomplete", "off");
    expect(input).toHaveAttribute("data-slot", "input");
    expect(input).toHaveClass(...classes(fieldControlClass).filter((c) => c !== "px-3"), "h-8", "pl-9", "pointer-coarse:min-h-10");
    const wrapper = input.closest("[data-slot=search-input]") as HTMLElement;
    expect(wrapper).toHaveClass("relative", "min-w-0", "flex-1");
    const icon = wrapper.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveClass("left-3", "size-4", "text-fg-secondary", "pointer-events-none");
  });

  it("takes the Input sizes", () => {
    render(<SearchInput label="Search posts" size="lg" />);
    const input = screen.getByRole("searchbox", { name: "Search posts" });
    expect(input).toHaveAttribute("data-size", "lg");
    expect(input).toHaveClass("h-9");
  });

  it("Escape clears a controlled field through its onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);
    const input = screen.getByRole("searchbox", { name: "Search automations" });
    await user.type(input, "price");
    expect(input).toHaveValue("price");
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
    expect(onChange).toHaveBeenLastCalledWith("");
    expect(input).toHaveFocus();
  });

  it("Escape clears an uncontrolled field and stops there; in an empty field it passes on", async () => {
    const user = userEvent.setup();
    const outer = vi.fn();
    render(
      <div onKeyDown={(event) => outer(event.key, event.defaultPrevented)}>
        <SearchInput label="Search emoji" defaultValue="heart" />
      </div>,
    );
    const input = screen.getByRole("searchbox", { name: "Search emoji" });
    await user.click(input);
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
    expect(outer).not.toHaveBeenCalled();
    await user.keyboard("{Escape}");
    expect(outer).toHaveBeenCalledWith("Escape", false);
  });

  it("leaves Escape to a call site that handles it", () => {
    render(<SearchInput label="Search" defaultValue="x" onKeyDown={(event) => event.preventDefault()} />);
    const input = screen.getByRole("searchbox", { name: "Search" });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveValue("x");
  });

  it("passes a ref to the input (the inbox focuses its search with a shortcut)", () => {
    const ref = { current: null as HTMLInputElement | null };
    render(<SearchInput label="Search conversations" ref={ref} />);
    expect(ref.current).toBe(screen.getByRole("searchbox", { name: "Search conversations" }));
  });

  it("inside a Field: the FieldLabel names it and its description is linked", () => {
    render(
      <Field>
        <FieldLabel>Find a post</FieldLabel>
        <SearchInput />
        <FieldDescription>Searches captions.</FieldDescription>
      </Field>,
    );
    const input = screen.getByRole("searchbox", { name: "Find a post" });
    expect(input).toHaveAccessibleDescription("Searches captions.");
  });
});
