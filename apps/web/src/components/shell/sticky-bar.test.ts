import { afterEach, describe, expect, it, vi } from "vitest";

import { reserveBottomBar } from "./sticky-bar";

const root = () => document.documentElement.style;

// jsdom has no layout, so no hit testing; the test says what is painted on top.
if (!document.elementFromPoint) Object.defineProperty(document, "elementFromPoint", { configurable: true, value: () => null });

function bar(height: number, position = "sticky") {
  const element = document.createElement("div");
  element.style.position = position;
  Object.defineProperty(element, "offsetHeight", { configurable: true, get: () => height });
  document.body.append(element);
  return element;
}

afterEach(() => {
  vi.restoreAllMocks();
  document.body.replaceChildren();
  root().removeProperty("scroll-padding-bottom");
  root().removeProperty("--bottom-bar-height");
});

describe("reserveBottomBar (UI-ISS-014: focus never under a sticky bar)", () => {
  it("a sticking bar's height becomes the page's bottom scroll padding, until it unmounts", () => {
    const release = reserveBottomBar(bar(96));
    expect(root().scrollPaddingBottom).toBe("96px");
    // The bar's own controls cancel it (BOTTOM_BAR), so tabbing onto them doesn't scroll the page.
    expect(root().getPropertyValue("--bottom-bar-height")).toBe("96px");
    release?.();
    expect(root().scrollPaddingBottom).toBe("");
    expect(root().getPropertyValue("--bottom-bar-height")).toBe("");
  });

  it("a bar that doesn't stick (a short viewport) reserves nothing, and is measured again on resize", () => {
    const element = bar(96, "static");
    const release = reserveBottomBar(element);
    expect(root().scrollPaddingBottom).toBe("");
    element.style.position = "sticky"; // the viewport grew past 500 px
    window.dispatchEvent(new Event("resize"));
    expect(root().scrollPaddingBottom).toBe("96px");
    release?.();
  });

  it("with two bars, the taller one decides; removing it leaves the other", () => {
    const releaseShort = reserveBottomBar(bar(64));
    const releaseTall = reserveBottomBar(bar(120));
    expect(root().scrollPaddingBottom).toBe("120px");
    releaseTall?.();
    expect(root().scrollPaddingBottom).toBe("64px");
    releaseShort?.();
    expect(root().scrollPaddingBottom).toBe("");
  });

  it("a field tabbed to that stays partly under the bar is scrolled clear; a click isn't", () => {
    const element = bar(86);
    const field = document.createElement("textarea");
    document.body.append(field);
    const rect = (top: number, bottom: number) => ({ top, bottom, left: 0, right: 600 }) as DOMRect;
    element.getBoundingClientRect = () => rect(714, 800);
    field.getBoundingClientRect = () => rect(653, 765); // the browser revealed only the caret
    const scroll = vi.fn();
    field.scrollIntoView = scroll;
    const topmost = vi.spyOn(document, "elementFromPoint").mockReturnValue(element);
    const release = reserveBottomBar(element);

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    field.focus();
    expect(scroll).toHaveBeenCalledWith({ block: "nearest" });

    field.blur();
    scroll.mockClear();
    document.dispatchEvent(new Event("pointerdown"));
    field.focus();
    expect(scroll).not.toHaveBeenCalled();

    // A dialog or menu painted over the bar: the bar doesn't cover the field, nothing moves.
    field.blur();
    topmost.mockReturnValue(field);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    field.focus();
    expect(scroll).not.toHaveBeenCalled();
    release?.();
  });

  it("does nothing for a detached ref", () => {
    expect(reserveBottomBar(null)).toBeUndefined();
    expect(root().scrollPaddingBottom).toBe("");
  });
});
