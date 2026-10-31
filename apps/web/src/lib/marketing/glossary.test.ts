import { describe, expect, it } from "vitest";

import { STATUS_LABEL } from "./gtm-pages";
import { GLOSSARY, findTerm, glossaryByLetter, termLetter, termWords } from "./glossary";
import { GUIDES, guidePath } from "./guides";
import { PUBLIC_PATHS } from "./site";

/** Pages a term may send a reader to: the public pages and the guides. */
const ROUTES = new Set<string>([...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug))]);
/** Meta's own domains (C-163): a rule comes from Meta's docs or help centres. */
const META_HOSTS = ["developers.facebook.com", "www.facebook.com", "help.instagram.com", "business.whatsapp.com"];

describe("the glossary terms (C-163)", () => {
  it("has 20 to 24 terms with unique slugs, terms and titles", () => {
    expect(GLOSSARY.length).toBeGreaterThanOrEqual(20);
    expect(GLOSSARY.length).toBeLessThanOrEqual(24);
    for (const key of ["slug", "term", "title", "definition"] as const) {
      const values = GLOSSARY.map((term) => term[key]);
      expect(new Set(values).size, key).toBe(values.length);
    }
  });

  it.each(GLOSSARY.map((term) => [term.slug, term] as const))("%s: a short title, one quotable sentence, 200 to 450 words", (slug, term) => {
    expect(slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    expect(term.title.length, term.title).toBeLessThanOrEqual(49);
    expect(term.definition.length, term.definition).toBeGreaterThanOrEqual(50);
    expect(term.definition.length, term.definition).toBeLessThanOrEqual(155);
    // One sentence: a full stop at the end and nowhere else before it.
    expect(term.definition).toMatch(/^[^.]+\.$/);
    expect(termWords(term), slug).toBeGreaterThanOrEqual(200);
    expect(termWords(term), slug).toBeLessThanOrEqual(450);
    expect(term.handling.length).toBeGreaterThan(0);
    for (const item of term.handling) expect(Object.keys(STATUS_LABEL)).toContain(item.status);
  });

  it.each(GLOSSARY.map((term) => [term.slug, term] as const))("%s: Meta's own sources, dated, and links that resolve", (_slug, term) => {
    expect(term.sources.length).toBeGreaterThan(0);
    for (const source of term.sources) {
      expect(META_HOSTS, source.url).toContain(new URL(source.url).host);
      expect(source.checked).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
    expect(term.related.length).toBeGreaterThanOrEqual(2);
    for (const slug of term.related) {
      expect(findTerm(slug), slug).toBeDefined();
      expect(slug).not.toBe(term.slug);
    }
    expect(ROUTES, term.learn.href).toContain(term.learn.href);
    expect(term.updated).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("makes no ranking claims, no requests and no fake proof", () => {
    const text = GLOSSARY.flatMap((term) => [term.title, term.definition, ...term.detail, ...term.handling.flatMap((item) => [item.title, item.body])]).join("\n");
    expect(text).not.toMatch(/\bbest\b|#1|number one|\bplease\b|testimonial|\brated\b/i);
    expect(text).not.toMatch(/\bHindi\b|Hinglish/);
  });

  it("groups the terms A to Z, numbers first", () => {
    const groups = glossaryByLetter();
    expect(groups[0].letter).toBe("#");
    expect(groups.flatMap((group) => group.terms)).toHaveLength(GLOSSARY.length);
    const letters = groups.map((group) => group.letter).filter((letter) => letter !== "#");
    expect(letters).toEqual([...letters].sort());
    for (const group of groups) for (const term of group.terms) expect(termLetter(term)).toBe(group.letter);
  });
});
