import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  EYEBROW,
  breakpoints,
  colorTokens,
  easings,
  fontSizes,
  gradientUtilities,
  motionDurations,
  otherUtilities,
  shadcnAliases,
  shadowTokens,
  typeRoles,
} from "./tokens";

const css = readFileSync(join(__dirname, "globals.css"), "utf8");

function declared(name: string): string | undefined {
  const match = css.match(new RegExp(`--color-${name}:\\s*([^;]+);`));
  return match?.[1].trim();
}

/** The body of every top-level block whose header matches, e.g. `:root` or `@theme inline`. */
function blocks(header: RegExp): string[] {
  const found: string[] = [];
  for (const match of css.matchAll(new RegExp(`(^|\\n)${header.source}\\s*\\{`, "g"))) {
    let depth = 1;
    let i = (match.index ?? 0) + match[0].length;
    const start = i;
    for (; i < css.length && depth > 0; i++) {
      if (css[i] === "{") depth++;
      else if (css[i] === "}") depth--;
    }
    found.push(css.slice(start, i - 1));
  }
  return found;
}

const rootAliases = blocks(/:root/)
  .join("\n")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .matchAll(/--([a-z-]+):/g);
// `--radius` is inert (DESIGN_SYSTEM §1.10) and `--motion-*` are durations, not colours.
const rootColorAliases = [...rootAliases].map((m) => m[1]).filter((name) => name !== "radius" && !name.startsWith("motion-"));
const themeInline = blocks(/@theme inline/).join("\n");

describe("design tokens (§4.2, UX-TOK-01)", () => {
  it.each(colorTokens)("globals.css defines $name as $value", ({ name, value }) => {
    expect(declared(name)).toBe(value);
  });

  it.each(gradientUtilities)("defines the $name utility", ({ name, value }) => {
    expect(css).toContain(`@utility ${name} { background-image: ${value}; }`);
  });

  it("builds every gradient from tokens, not hex stops (DESIGN_SYSTEM §1.9)", () => {
    for (const { value } of gradientUtilities) expect(value).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
    const gradientRules = css.match(/@utility bg-[a-z-]+ \{ background-image: [^}]+\}/g) ?? [];
    expect(gradientRules).toHaveLength(gradientUtilities.length);
    for (const rule of gradientRules) expect(rule).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });

  it("maps shadcn's semantic variables onto the tokens", () => {
    expect(css).toMatch(/--background:\s*var\(--color-canvas\)/);
    expect(css).toMatch(/--ring:\s*var\(--color-brand\)/);
    for (const { alias, token } of shadcnAliases) {
      expect(css, `--${alias}`).toMatch(new RegExp(`--${alias}:\\s*var\\(--color-${token}\\);`));
    }
  });

  it("gives every :root alias a --color-* mapping, so its utilities generate CSS (COL-009)", () => {
    expect(rootColorAliases.length).toBeGreaterThan(0);
    expect([...rootColorAliases].sort()).toEqual(shadcnAliases.map((a) => a.alias).sort());
    for (const name of rootColorAliases) {
      expect(themeInline, `--color-${name}`).toMatch(new RegExp(`--color-${name}:\\s*var\\(--${name}\\);`));
    }
  });

  it("points --primary at brand-strong and keeps literals out of the alias layer (UI-ISS-005, UI-ISS-028)", () => {
    expect(css).toMatch(/--primary:\s*var\(--color-brand-strong\)/);
    expect(css).toMatch(/--primary-foreground:\s*var\(--color-on-brand\)/);
    expect(css).toMatch(/--accent:\s*var\(--color-hover\)/);
    expect(blocks(/:root/).join("\n").replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });

  it("keeps the WCAG fixes from UX-TOK-02", () => {
    expect(declared("brand-strong")).toBe("#4467E6"); // the gradient ends at 4.85:1 with white, not #567FF8
    expect(gradientUtilities[0].value).toContain("var(--color-brand-strong) 100%");
    expect(declared("brand-fg")).toBe("#9DB5FF");
    expect(declared("fg-secondary")).toBe("#9B9CA0");
    expect(declared("danger-fill")).toBe("#C53030");
  });

  it("applies the owner's token decisions D-01, D-06 and D-12 (C-069, C-071)", () => {
    // D-01: control edges are white 40%, through --input, so every field, select, checkbox and
    // switch edge is 3:1 or more on every surface.
    expect(declared("line-control")).toBe("rgb(255 255 255 / 0.40)");
    expect(css).toMatch(/--input:\s*var\(--color-line-control\);/);
    // D-06: placeholders are fg-secondary (text, 4.5:1), not fg-disabled.
    const base = blocks(/@layer base/).join("\n");
    expect(base).toMatch(/::placeholder \{ color: var\(--color-fg-secondary\); \}/);
    expect(base).not.toMatch(/fg-disabled/);
    // D-12: what floats sits on overlay, lighter than the panel cards beneath it.
    expect(declared("overlay")).toBe("#262626");
    expect(css).toMatch(/--popover:\s*var\(--color-overlay\);/);
  });

  it.each(shadowTokens)("defines the $name elevation shadow (D-12)", ({ name, value, sample }) => {
    expect(css).toMatch(new RegExp(`--${name}:\\s*${value.replace(/[()/.]/g, "\\$&")};`));
    expect(sample.split(" ")).toEqual(expect.arrayContaining(["bg-overlay", "ring-1", "ring-line", name]));
    // Dark shadows only: no hue, and the edge is a ring, not part of the shadow.
    expect(value).toMatch(/^0 \d+px \d+px -\d+px rgb\(0 0 0 \/ 0\.\d+\)$/);
  });

  it.each(fontSizes)("defines $name as $size with a $lineHeight line height", ({ name, size, lineHeight }) => {
    const token = name.replace("text-", "");
    expect(css).toMatch(new RegExp(`--text-${token}:\\s*${size};`));
    expect(css).toMatch(new RegExp(`--text-${token}--line-height:\\s*${lineHeight};`));
  });

  it.each(motionDurations)("defines $name over $variable ($value)", ({ name, variable, value }) => {
    expect(css).toMatch(new RegExp(`${variable}:\\s*${value};`));
    expect(css).toContain(`@utility ${name} { --tw-duration: var(${variable}); transition-duration: var(${variable}); }`);
  });

  it.each(easings)("defines the $name easing", ({ name, value }) => {
    expect(css).toContain(`--${name}: ${value};`);
  });

  it("adds the wide breakpoint", () => {
    for (const bp of breakpoints.filter((b) => b.custom)) expect(css).toMatch(new RegExp(`--breakpoint-${bp.name}:\\s*${bp.value};`));
  });

  it.each(otherUtilities)("defines the $name utility", ({ name, value }) => {
    expect(css).toContain(`@utility ${name} { ${value}; }`);
  });

  it("sets the base-layer rules: bold is 600, the phone top bar's scroll padding, the reduced-motion net", () => {
    const base = blocks(/@layer base/).join("\n");
    expect(base).toMatch(/strong, b \{ font-weight: 600; \}/);
    expect(base).toMatch(/html \{ @variant max-md \{ scroll-padding-top: 4rem; \} \}/);
    expect(base).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{\s*\[data-slot\$="-overlay"\], \[data-slot\$="-content"\], \[data-slot="skeleton"\] \{\s*animation: none !important;\s*transition: none !important;/,
    );
  });

  it("keeps type roles on the scale: no arbitrary sizes, weights 400–600, one eyebrow", () => {
    expect(EYEBROW).toBe("text-2xs font-semibold uppercase tracking-[0.08em] text-fg-secondary");
    for (const { className } of typeRoles) {
      expect(className).not.toMatch(/text-\[/);
      expect(className).not.toMatch(/font-(bold|extrabold|black|light|thin)/);
      expect(className).not.toMatch(/tracking-\[0\.(1|12|14)em\]/);
    }
    expect(new Set(typeRoles.map((r) => r.name)).size).toBe(typeRoles.length);
  });
});
