import { describe, expect, it } from "vitest";

import { isAskShortcut } from "./use-ask-shortcut";

const keys = { ctrlKey: false, metaKey: false, altKey: false, shiftKey: false };

describe("the Ask shortcut (FR-AGT-01)", () => {
  it("is Ctrl or ⌘ with K, in either case, and nothing else held", () => {
    expect(isAskShortcut({ ...keys, key: "k", ctrlKey: true })).toBe(true);
    expect(isAskShortcut({ ...keys, key: "K", metaKey: true })).toBe(true);
    expect(isAskShortcut({ ...keys, key: "k" })).toBe(false);
    expect(isAskShortcut({ ...keys, key: "k", ctrlKey: true, shiftKey: true })).toBe(false);
    expect(isAskShortcut({ ...keys, key: "k", ctrlKey: true, altKey: true })).toBe(false);
    expect(isAskShortcut({ ...keys, key: "j", ctrlKey: true })).toBe(false);
  });

  it("ignores the keyless keydown events autofill and password managers send", () => {
    const autofill = { ...keys, key: undefined } as unknown as KeyboardEvent;
    expect(isAskShortcut(autofill)).toBe(false);
    expect(isAskShortcut({ ...autofill, ctrlKey: true })).toBe(false);
  });
});
