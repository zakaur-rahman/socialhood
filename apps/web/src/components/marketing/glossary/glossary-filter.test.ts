import { describe, expect, it } from "vitest";

import { applyGlossaryFilter, fold, matches } from "./glossary-filter";

function list(): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = `
    <a data-letter-link="O" href="#o">O</a><a data-letter-link="P" href="#p">P</a>
    <section data-letter="O"><ul><li data-term data-channel="WhatsApp" data-text="Opt-in Consent permission"></li></ul></section>
    <section data-letter="P">
      <ul>
        <li data-term data-channel="Instagram" data-text="Private replies one message per comment"></li>
        <li data-term data-channel="WhatsApp" data-text="Per-message pricing Meta's fees"></li>
      </ul>
    </section>`;
  return root;
}

describe("the glossary filter (C-163)", () => {
  it("folds case, accents and punctuation", () => {
    expect(fold("Opt-in")).toBe("opt in");
    expect(fold("Inrō")).toBe("inro");
    expect(matches("Opt-in Consent", "WhatsApp", "opt in", "all")).toBe(true);
    expect(matches("Opt-in Consent", "WhatsApp", "consent", "Instagram")).toBe(false);
    expect(matches("Anything", "Meta", "", "all")).toBe(true);
  });

  it("hides what doesn't match, empty letters too, and counts what shows", () => {
    const root = list();
    expect(applyGlossaryFilter(root, "", "all")).toBe(3);
    expect(applyGlossaryFilter(root, "private", "all")).toBe(1);
    expect(root.querySelector<HTMLElement>('[data-letter="O"]')!.hidden).toBe(true);
    expect(root.querySelector('[data-letter-link="O"]')!.hasAttribute("data-empty")).toBe(true);
    expect(applyGlossaryFilter(root, "", "WhatsApp")).toBe(2);
    expect(applyGlossaryFilter(root, "zzz", "all")).toBe(0);
    expect(applyGlossaryFilter(root, "", "all")).toBe(3);
    expect(root.querySelectorAll("[hidden]")).toHaveLength(0);
  });
});
