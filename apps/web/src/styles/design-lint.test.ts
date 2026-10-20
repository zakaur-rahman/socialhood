import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * UI-070's design lint (UI-ISS-028, DESIGN_SYSTEM §1, §4, §8.3): class strings that bypass the
 * tokens or drop the focus outline, checked across the app's source so they can't come back. The
 * palette lock in globals.css makes a default colour generate no CSS; this names where it is.
 * Tests and comment lines are skipped.
 */
const PALETTE =
  "white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const COLOR_UTILITIES =
  "bg|text|border(?:-[trblxyse])?|ring|ring-offset|outline|fill|stroke|from|via|to|shadow|divide|decoration|caret|accent|placeholder";

/** A utility, with or without variants, that isn't part of a longer class name. */
const utility = (body: string) => new RegExp(`(?<![\\w-])${body}(?![\\w-])`);

const LINE_RULES: { pattern: RegExp; rule: string }[] = [
  {
    pattern: utility(`(?:${COLOR_UTILITIES})-(?:${PALETTE})(?:-\\d{2,3})?(?:\\/\\d+)?`),
    rule: "a default Tailwind colour: use a token (on-brand, hover, pressed, scrim, media-scrim …)",
  },
  { pattern: /(?<![\w-])text-\[/, rule: "an arbitrary text size or colour: use a type role or a token" },
  { pattern: /(?<![\w-])rounded(?:-[a-z]{1,2})?-\[(?!inherit\])/, rule: "an arbitrary radius: use the radius scale" },
  { pattern: /(?<![\w-])ring-ring\/\d+/, rule: "the translucent shadcn ring: focus is the outline (DESIGN_SYSTEM §8.3)" },
];

/** A bare `outline-none` (no variant) removes the base layer's focus outline. */
const BARE_OUTLINE = /(?<![\w:-])outline-(?:none|hidden)(?![\w-])/;
/**
 * Allowed when the element is a programmatic focus target (`tabIndex={-1}`: the skip link's
 * <main>, a heading focused after navigation) or when the same line gives a `focus-visible:`
 * replacement. Radix's dialog and popover content are focused on open, the same as a
 * `tabIndex={-1}` target, so their primitives may set it.
 */
const OUTLINE_PRIMITIVES = ["dialog.tsx", "alert-dialog.tsx", "popover.tsx"].map((name) => join("components", "ui", name));

const SRC = join(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

const isComment = (line: string) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line);

function lint(): string[] {
  const hits: string[] = [];
  for (const file of sourceFiles(SRC)) {
    const name = relative(SRC, file);
    if (name.startsWith(`test${sep}`)) continue; // test helpers name the banned classes
    const text = readFileSync(file, "utf8");
    text.split("\n").forEach((line, index) => {
      if (isComment(line)) return;
      for (const { pattern, rule } of LINE_RULES) if (pattern.test(line)) hits.push(`${name}:${index + 1}: ${rule}`);
      if (
        BARE_OUTLINE.test(line) &&
        !line.includes("tabIndex={-1}") &&
        !/(?<![\w-])focus-visible:(?!outline-none)/.test(line) &&
        !OUTLINE_PRIMITIVES.includes(name)
      ) {
        hits.push(`${name}:${index + 1}: outline-none without a focus-visible replacement`);
      }
    });
    // A Button already wears the gradient (variant `default`); restating it on a call site hides
    // the variant it actually renders.
    for (const match of text.matchAll(/<Button\b[^>]*?\bbg-brand-gradient(?![\w-])/g)) {
      const line = text.slice(0, match.index).split("\n").length;
      hits.push(`${name}:${line}: bg-brand-gradient on Button: use the default variant`);
    }
  }
  return hits;
}

describe("design lint (UI-070)", () => {
  it("keeps class strings on the tokens and the focus outline in place", () => {
    expect(lint()).toEqual([]);
  });

  it("catches what it is meant to", () => {
    const palette = LINE_RULES[0].pattern;
    for (const bad of ["bg-red-500", "text-white", "hover:bg-black/60", "border-t-gray-200", "ring-offset-white"]) {
      expect(palette.test(`className="${bad}"`), bad).toBe(true);
    }
    for (const good of ["text-on-brand", "bg-media-scrim/60", "text-fg-secondary", "bg-chart-negative", "bg-transparent", "--color-white"]) {
      expect(palette.test(`className="${good}"`), good).toBe(false);
    }
    expect(LINE_RULES[1].pattern.test(`"text-[13px]"`)).toBe(true);
    expect(LINE_RULES[2].pattern.test(`"rounded-[10px]"`)).toBe(true);
    expect(LINE_RULES[2].pattern.test(`"rounded-[inherit]"`)).toBe(false);
    expect(LINE_RULES[3].pattern.test(`"focus-visible:ring-ring/50"`)).toBe(true);
    expect(BARE_OUTLINE.test(`"outline-none"`)).toBe(true);
    expect(BARE_OUTLINE.test(`"focus-visible:outline-none"`)).toBe(false);
  });
});
