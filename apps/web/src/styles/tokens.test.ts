import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { JSON_PATH, TS_PATH, generate, render } from "../../scripts/gen-tokens.mjs";
import {
  EYEBROW,
  breakpoints,
  chartAliases,
  colorTokens,
  colorValue,
  customVariants,
  describedColors,
  easings,
  fontSizes,
  glowShadows,
  gradientUtilities,
  motionDurations,
  otherUtilities,
  radiusTokens,
  radiusValue,
  shadcnAliases,
  shadowTokens,
  typeRoles,
} from "./tokens";

const css = readFileSync(join(__dirname, "globals.css"), "utf8");
/** A source file under src/, for the checks on the token consumers. */
const source = (path: string) => readFileSync(join(__dirname, "..", path), "utf8");
const unix = (text: string) => text.replace(/\r\n/g, "\n");
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");

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
// `--motion-*` are durations and `--gradient-*` gradients, not colour aliases.
const rootColorAliases = [...rootAliases].map((m) => m[1]).filter((name) => !name.startsWith("motion-") && !name.startsWith("gradient-"));
const themeInline = blocks(/@theme inline/).join("\n");
/** Every `--color-*` declared in `@theme` (the palette lock, `--color-*`, is not a token). */
const themeColorNames = [...blocks(/@theme/).join("\n").replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/--color-([a-z0-9-]+):/g)].map((m) => m[1]);

describe("one source of truth (C-100)", () => {
  it("has generated files that match globals.css exactly: run `pnpm tokens` after editing it", () => {
    const { json, ts } = render(generate(css));
    expect(unix(readFileSync(JSON_PATH, "utf8"))).toBe(json);
    expect(unix(readFileSync(TS_PATH, "utf8"))).toBe(ts);
  });

  it("describes every --color-* token and nothing else", () => {
    const described = [...describedColors, ...chartAliases.map((a) => a.name)];
    expect([...themeColorNames].sort()).toEqual([...described].sort());
    for (const token of colorTokens) {
      expect(token.use, token.name).not.toBe("");
      expect(token.swatch, token.name).toBe(`bg-${token.name}`);
    }
  });

  it("writes no theme value in tokens.ts: no colour, gradient or easing literal", () => {
    expect(source("styles/tokens.ts")).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(|linear-gradient|radial-gradient|cubic-bezier/);
  });
});

describe("design tokens (§4.2, UX-TOK-01)", () => {
  it.each(colorTokens)("globals.css defines $name as $value", ({ name, value }) => {
    expect(declared(name)).toBe(value);
  });

  it.each(gradientUtilities)("defines the $name utility over $variable", ({ name, variable, value }) => {
    expect(css).toContain(`@utility ${name} { background-image: var(${variable}); }`);
    expect(css).toMatch(new RegExp(`${variable}:\\s*${escape(value)};`));
  });

  it("builds every gradient from tokens, not hex stops (DESIGN_SYSTEM §1.9)", () => {
    for (const { value } of gradientUtilities) expect(value).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
    const gradientRules = css.match(/@utility bg-[a-z-]+ \{ background-image: [^}]+\}/g) ?? [];
    expect(gradientRules).toHaveLength(gradientUtilities.length);
    for (const rule of gradientRules) expect(rule).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });

  it("maps shadcn's semantic variables onto the tokens (kept only for `shadcn add` output)", () => {
    expect(css).toMatch(/--background:\s*var\(--color-canvas\)/);
    expect(css).toMatch(/--ring:\s*var\(--color-brand\)/);
    expect(shadcnAliases).toHaveLength(18);
    for (const { alias, token } of shadcnAliases) {
      expect(css, `--${alias}`).toMatch(new RegExp(`--${alias}:\\s*var\\(--color-${token}\\);`));
      expect(colorTokens.map((t) => t.name), `${alias} -> ${token}`).toContain(token);
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
    const aliasLines = blocks(/:root/)
      .join("\n")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((line) => !line.includes("--gradient-") && !line.includes("--motion-"));
    expect(aliasLines.join("\n")).not.toMatch(/#[0-9a-f]{3,8}\b/i);
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
    expect(css).toMatch(new RegExp(`--${name}:\\s*${escape(value)};`));
    expect(sample.split(" ")).toEqual(expect.arrayContaining(["bg-overlay", "ring-1", "ring-line", name]));
    // Dark shadows only: no hue, and the edge is a ring, not part of the shadow.
    expect(value).toMatch(/^0 \d+px \d+px -\d+px rgb\(0 0 0 \/ 0\.\d+\)$/);
  });

  it.each(glowShadows)("defines the $name marketing glow from the brand token (C-100)", ({ name, value }) => {
    expect(css).toMatch(new RegExp(`--${name}:\\s*${escape(value)};`));
    expect(value).toContain("var(--color-brand)");
    expect(value).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
  });

  it.each(radiusTokens)("defines $name as $value", ({ key, value }) => {
    expect(css).toMatch(new RegExp(`--radius-${key}:\\s*${value};`));
    expect(radiusValue(key)).toBe(value);
  });

  it("drops the inert shadcn --radius and names the eyebrow tracking and display leading", () => {
    expect(css).not.toMatch(/--radius:/);
    expect(css).toMatch(/--tracking-eyebrow:\s*0\.08em;/);
    expect(css).toMatch(/--leading-display:\s*1\.08;/);
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

  it("defines the breakpoints, wide being the addition", () => {
    for (const bp of breakpoints) expect(css).toMatch(new RegExp(`--breakpoint-${bp.name}:\\s*${bp.value};`));
    expect(breakpoints.map((b) => b.px)).toEqual([768, 1024, 1280, 1440]);
  });

  it.each(otherUtilities)("defines the $name utility", ({ name, value }) => {
    expect(css).toContain(`@utility ${name} { ${value}; }`);
  });

  it("names the crop mask instead of an arbitrary shadow: a token colour, not an elevation (C-073)", () => {
    const mask = otherUtilities.find((u) => u.name === "shadow-crop-mask")!;
    expect(mask.value).toContain("var(--color-media-scrim) 60%");
    expect(mask.value).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
    // Elevation stays two shadows; the mask is a utility of its own.
    expect(css).not.toMatch(/--shadow-crop-mask/);
    expect(shadowTokens.map((s) => s.name)).not.toContain("shadow-crop-mask");
  });

  it.each(customVariants)("defines the $name variant as $value", ({ name, value }) => {
    expect(css).toContain(`@custom-variant ${name} (${value});`);
  });

  it("adds the brand-soft hover step between brand-soft and brand-line (C-073)", () => {
    const alpha = (name: string) => Number(declared(name)?.match(/\/ ([\d.]+)\)$/)?.[1]);
    expect(declared("brand-soft-hover")).toBe("rgb(86 127 248 / 0.25)");
    expect(alpha("brand-soft")).toBeLessThan(alpha("brand-soft-hover"));
    expect(alpha("brand-soft-hover")).toBeLessThan(alpha("brand-line"));
  });

  it("derives the named shades (media, panel, on-brand, danger) from their base token, not from a second literal", () => {
    const shades = colorTokens.filter((t) => /^(media-(wash|chip|heavy)|canvas-veil|panel-(glass|veil)|on-brand-(soft|line|line-strong)|fg-hover|danger-line|warning-line|danger-fill-hover)$/.test(t.name));
    expect(shades).toHaveLength(13);
    for (const { name, value } of shades) expect(value, name).toMatch(/^color-mix\(in srgb, var\(--color-[a-z-]+\) \d+%, transparent\)$/);
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
    expect(EYEBROW).toBe("text-2xs font-semibold uppercase tracking-eyebrow text-fg-secondary");
    for (const { className } of typeRoles) {
      expect(className).not.toMatch(/(text|tracking|leading)-\[/);
      expect(className).not.toMatch(/font-(bold|extrabold|black|light|thin)/);
    }
    expect(new Set(typeRoles.map((r) => r.name)).size).toBe(typeRoles.length);
  });

  it("locks the palette: Tailwind's default colours are cleared before the tokens (UI-070, UI-ISS-028)", () => {
    const theme = blocks(/@theme/)[0].replace(/\/\*[\s\S]*?\*\//g, "").trim();
    expect(theme.startsWith("--color-*: initial;")).toBe(true);
    // White and black survive only as tokens.
    expect(css).not.toMatch(/--color-(white|black):/);
  });

  it.each(chartAliases)("aliases $name to $token: no new hue (UI-ISS-097)", ({ name, token, swatch }) => {
    expect(declared(name)).toBe(`var(--color-${token})`);
    expect(colorTokens.map((t) => t.name)).toContain(token);
    expect(swatch).toBe(`bg-${name}`);
    expect(colorValue(name)).toBe(colorValue(token));
  });

  it.each(["lib/clerk-appearance.ts", "components/marketing/og.tsx", "app/manifest.ts", "app/layout.tsx", "app/global-error.tsx"])(
    "%s reads its colours from tokens.ts instead of restating them (UI-ISS-095)",
    (path) => {
      const text = source(path);
      expect(text).toContain("colorValue");
      // rgba(0,0,0,0) is the OG glow's transparent end, not a token.
      expect(text.replaceAll("rgba(0,0,0,0)", "")).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(\d/i);
    },
  );

  it("gives Clerk the brand gradient and the radii as CSS variables, and the icon script its colours from the generated tokens (C-100)", () => {
    const clerk = source("lib/clerk-appearance.ts");
    expect(clerk).toContain('backgroundImage: "var(--gradient-brand)"');
    expect(clerk).not.toMatch(/linear-gradient|0\.5rem|0\.75rem/);
    const icons = readFileSync(join(__dirname, "..", "..", "scripts", "generate-icons.mjs"), "utf8");
    expect(icons).toContain("tokens.generated.json");
    expect(icons).not.toMatch(/\b0x(33|52|cc|1c|2d|70)\b/i); // the old hard-coded gradient bytes
  });

  it("looks colour tokens up by name and refuses unknown ones", () => {
    expect(colorValue("canvas")).toBe("#000000");
    expect(colorValue("brand-line")).toBe("rgb(86 127 248 / 0.35)");
    expect(() => colorValue("red-500")).toThrow(/Unknown colour token/);
    expect(() => radiusValue("huge")).toThrow(/Unknown radius token/);
  });
});
