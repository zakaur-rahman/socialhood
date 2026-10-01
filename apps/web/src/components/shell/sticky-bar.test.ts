import { afterEach, describe, expect, it } from "vitest";

import { reserveBottomBar } from "./sticky-bar";

const root = () => document.documentElement.style;

function bar(height: number, position = "sticky") {
  const element = document.createElement("div");
  element.style.position = position;
  Object.defineProperty(element, "offsetHeight", { configurable: true, get: () => height });
  document.body.append(element);
  return element;
}

afterEach(() => {
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

  it("does nothing for a detached ref", () => {
    expect(reserveBottomBar(null)).toBeUndefined();
    expect(root().scrollPaddingBottom).toBe("");
  });
});
