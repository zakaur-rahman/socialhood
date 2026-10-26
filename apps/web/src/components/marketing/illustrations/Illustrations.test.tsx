import { render } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Features } from "../Features";
import { ILLUSTRATIONS, Illustration, type IllustrationName } from "./Illustrations";

/**
 * C-138: the feature cards' pictures were empty boxes in the server's HTML (loaded on scroll with
 * `ssr: false`), so a full-page capture, a crawler or a failed chunk showed blank panels. Every
 * picture must be in the markup the server sends, with visible text, and nothing may hide it.
 */
describe("the feature illustrations", () => {
  const names = Object.keys(ILLUSTRATIONS) as IllustrationName[];

  it.each(names)("%s is in the server's markup, with text and nothing hiding it", (name) => {
    const html = renderToStaticMarkup(<Illustration name={name} />);
    const box = new DOMParser().parseFromString(html, "text/html").querySelector(`[data-illustration="${name}"]`);
    expect(box).not.toBeNull();
    expect(box?.getAttribute("aria-hidden")).toBe("true");
    expect((box?.textContent ?? "").trim().length).toBeGreaterThan(10);
    expect(html).not.toMatch(/opacity:\s*0|visibility:\s*hidden|display:\s*none/);
  });

  it("every feature card's picture has content on the first render", () => {
    const { container } = render(<Features />);
    const boxes = container.querySelectorAll("[data-illustration]");
    expect(boxes.length).toBeGreaterThanOrEqual(names.length);
    for (const box of boxes) {
      expect(box.children.length, box.getAttribute("data-illustration") ?? "").toBeGreaterThan(0);
      expect((box.textContent ?? "").trim().length).toBeGreaterThan(10);
    }
  });
});
