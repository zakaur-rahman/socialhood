import { describe, expect, it, vi } from "vitest";

import { clearSearchOnEscape } from "./search-escape";

function escapeOn(target: EventTarget): KeyboardEvent {
  const event = new KeyboardEvent("keydown", { key: "Escape", cancelable: true, bubbles: true });
  Object.defineProperty(event, "target", { value: target });
  return event;
}

describe("clearSearchOnEscape (Esc in a search field inside a popover)", () => {
  it("empties a search field that has text and keeps the popover open", () => {
    const field = document.createElement("input");
    field.type = "search";
    field.value = "heart";
    const onInput = vi.fn();
    field.addEventListener("input", onInput);
    const event = escapeOn(field);
    clearSearchOnEscape(event);
    expect(field.value).toBe("");
    expect(onInput).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(true);
  });

  it("lets Esc close the popover from an empty field or anything else", () => {
    const empty = document.createElement("input");
    empty.type = "search";
    const fromEmpty = escapeOn(empty);
    clearSearchOnEscape(fromEmpty);
    expect(fromEmpty.defaultPrevented).toBe(false);

    const text = document.createElement("input");
    text.value = "not a search";
    const fromText = escapeOn(text);
    clearSearchOnEscape(fromText);
    expect(fromText.defaultPrevented).toBe(false);
    expect(text.value).toBe("not a search");

    const fromButton = escapeOn(document.createElement("button"));
    clearSearchOnEscape(fromButton);
    expect(fromButton.defaultPrevented).toBe(false);
  });
});
