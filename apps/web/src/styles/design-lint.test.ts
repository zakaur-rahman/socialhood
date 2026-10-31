import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

import { colourExceptions, type ColourException } from "./colour-exceptions";
import { tokenValues } from "./tokens.generated";

/**
 * UI-070's design lint (UI-ISS-028, DESIGN_SYSTEM §1, §4, §8.3), widened by C-127: class strings
 * and literals that bypass the tokens or drop the focus outline, checked across the app's source so
 * they can't come back. The palette lock in globals.css makes a default colour generate no CSS; this
 * names where it is. Tests and comment lines are skipped.
 *
 * Anything intentional is listed in colour-exceptions.ts with a reason. The lint reads that list
 * both ways: what it finds must be listed, and a listed entry that no longer exists fails.
 */
const SRC = join(__dirname, "..");
const WEB = join(SRC, "..");

const css = readFileSync(join(SRC, "styles", "globals.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

/** Every `--color-*` in globals.css, `@theme` and `@theme inline` alike: the colours a class may name. */
const COLOUR_NAMES = new Set([...css.matchAll(/--color-([a-z0-9-]+):/g)].map((m) => m[1]).filter((name) => name !== "*"));
/** Utilities globals.css defines itself (`bg-brand-gradient`, `duration-fast` …) and the shadow and size theme names. */
const DEFINED_UTILITIES = new Set([
  ...[...css.matchAll(/@utility ([a-z0-9-]+)/g)].map((m) => m[1]),
  ...[...css.matchAll(/--shadow-([a-z0-9-]+):/g)].map((m) => `shadow-${m[1]}`),
  // The type roles, the site's (`text-site-caption`, C-155) included; a `--text-*--line-height` companion is harmless here.
  ...[...css.matchAll(/--text-([a-z0-9-]+):/g)].map((m) => `text-${m[1]}`),
]);

const PALETTE =
  "white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const COLOR_UTILITIES =
  "bg|text|border(?:-[trblxyse])?|ring|ring-offset|outline|fill|stroke|from|via|to|shadow|divide|decoration|caret|accent|placeholder";

/** A utility, with or without variants, that isn't part of a longer class name. */
const utility = (body: string) => new RegExp(`(?<![\\w-])${body}(?![\\w-])`, "g");
/** Every match of a pattern in a line, as text. */
const all = (pattern: RegExp, line: string) => [...line.matchAll(pattern)].map((m) => m[0]);

/** Names after a colour prefix that are not colours: widths, styles, alignments, sizes, positions. */
const NOT_A_COLOUR: Record<string, RegExp> = {
  bg: /^(?:transparent|current|none|auto|clip-[a-z]+|origin-[a-z-]+|repeat(?:-[xy]|-round|-space)?|no-repeat|cover|contain|center|(?:left|right)(?:-(?:top|bottom))?|(?:top|bottom)(?:-(?:left|right))?|fixed|local|scroll|linear-.+|radial.*|conic.*|blend-[a-z-]+|token-image|color|image)$/,
  text: /^(?:xs|sm|base|lg|xl|[2-9]xl|2xs|md|left|right|center|justify|start|end|balance|pretty|wrap|nowrap|ellipsis|clip|current|transparent|inherit|only)$/,
  border: /^(?:transparent|current|solid|dashed|dotted|double|hidden|none|collapse|separate|spacing.*|[trblxyse](?:-\d+)?|\d+)$/,
  outline: /^(?:offset-\d+|none|hidden|dashed|dotted|double|solid|transparent|current)$/,
  ring: /^(?:inset|offset-\d+|transparent|current)$/,
  shadow: /^(?:2xs|xs|sm|md|lg|xl|2xl|inner|none|transparent|current)$/,
  fill: /^(?:current|none|transparent|inherit)$/,
  stroke: /^(?:current|none|transparent|inherit|dashoffset|dasharray|linecap|linejoin|miterlimit)$/,
  divide: /^(?:x|y|x-reverse|y-reverse|solid|dashed|dotted|double|none|transparent|current)$/,
  decoration: /^(?:solid|double|dotted|dashed|wavy|auto|from-font|clone|slice|transparent|current)$/,
  other: /^(?:transparent|current|auto|inherit)$/,
};
const prefixKey = (prefix: string) => (prefix.startsWith("border") ? "border" : prefix in NOT_A_COLOUR ? prefix : prefix === "ring-offset" ? "ring" : "other");

/**
 * Colour utilities that name something globals.css doesn't define. The palette lock makes such a class
 * generate no CSS, so it renders as nothing (`bg-surface` was a transparent card); this is the rule
 * that finds them.
 */
function undefinedColourClasses(line: string): string[] {
  const found: string[] = [];
  // Import paths (`text-generate-effect`) and arbitrary values (`transition-[border-color,…]`) hold no colour classes.
  if (/^\s*import\b|\bfrom ["']/.test(line)) return found;
  line = line.replace(/\[[^\]]*\]/g, "[]");
  const pattern = new RegExp(`(?<![\\w-])(${COLOR_UTILITIES.replace("ring|ring-offset", "ring-offset|ring")})-([a-z][a-z0-9-]*)(?:\\/\\d+)?(?![\\w-])`, "g");
  for (const m of line.matchAll(pattern)) {
    const [text, prefix, name] = m;
    if (COLOUR_NAMES.has(name) || DEFINED_UTILITIES.has(`${prefix}-${name}`)) continue;
    if (NOT_A_COLOUR[prefixKey(prefix)].test(name)) continue;
    found.push(text);
  }
  return found;
}

const SHADCN_ALIASES =
  "background|foreground|card|card-foreground|popover|popover-foreground|primary|primary-foreground|secondary|secondary-foreground|muted|muted-foreground|accent|accent-foreground|destructive|border|input|ring";
const COLOUR_TOKENS_ALT = [...COLOUR_NAMES].sort((a, b) => b.length - a.length).join("|");
const NOT_CODE_VALUE = /^(?:var\(--|url\(|none\b|transparent\b|currentColor$|inherit$|unset$|0$)/;

type Rule = { id: string; rule: string; find: (line: string) => string[]; literalOnly?: boolean };

const RULES: Rule[] = [
  {
    id: "palette",
    rule: "a default Tailwind colour: use a token (on-brand, hover, pressed, scrim, media-scrim …)",
    find: (line) => all(utility(`(?:${COLOR_UTILITIES})-(?:${PALETTE})(?:-\\d{2,3})?(?:\\/\\d+)?`), line),
  },
  {
    id: "undefined-token",
    rule: "a colour class whose token is not defined in globals.css (it generates no CSS and renders nothing)",
    find: undefinedColourClasses,
  },
  {
    id: "arbitrary-colour",
    rule: "an arbitrary colour, shadow or gradient value: name it in globals.css, or list it in colour-exceptions.ts",
    find: (line) => [
      ...all(utility(`(?:${COLOR_UTILITIES})-\\[(?:#|rgba?|hsla?|oklch|oklab|color:|color-mix)[^\\]]*\\]`), line),
      ...all(utility("(?:shadow|from|via|to|fill|stroke|border|ring|outline|decoration|caret|accent)-\\[[^\\]]*\\]"), line),
      ...all(/(?<![\w-])bg-\[(?!url\()[^\]]*\]/g, line),
    ],
  },
  {
    id: "colour-literal",
    rule: "a colour literal (hex, rgb, hsl, oklch, color-mix): the value belongs in globals.css, or list it in colour-exceptions.ts",
    literalOnly: true,
    find: (line) => [
      ...all(/(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g, line),
      ...all(/\b(?:rgba?|hsla?|oklch|oklab)\((?=\s*[\d.])[^)]*\)/g, line),
      ...all(/color-mix\((?:[^()]|\([^()]*\))*\)/g, line),
    ],
  },
  {
    id: "inline-colour",
    rule: "a colour written in an inline style or an SVG attribute: use a token variable, currentColor or colorValue()",
    literalOnly: true,
    find: (line) => {
      const bad: string[] = [];
      const style = /\b(?:color|background|backgroundColor|borderColor|borderTopColor|borderBottomColor|borderLeftColor|borderRightColor|outlineColor|caretColor|accentColor|fill|stroke|stopColor|floodColor|boxShadow|textShadow)\s*:\s*(["'`])([^"'`]*)\1/g;
      const attribute = /\b(?:fill|stroke|stopColor|floodColor)=(["'])([^"']*)\1/g;
      for (const m of [...line.matchAll(style), ...line.matchAll(attribute)]) if (!NOT_CODE_VALUE.test(m[2].trim())) bad.push(m[0]);
      return bad;
    },
  },
  {
    id: "shadcn-alias",
    rule: "a shadcn alias class name: use the token (overlay, field, fg-secondary, line, line-control, brand …)",
    find: (line) => all(utility(`(?:bg|text|border|ring|outline|fill|stroke|divide|from|via|to|shadow)-(?:${SHADCN_ALIASES})`), line),
  },
  {
    id: "opacity-modifier",
    rule: "an opacity modifier on a colour token: use a named shade from globals.css (hover, pressed, media-chip, panel-glass …) or list it",
    find: (line) => all(utility(`(?:${COLOR_UTILITIES.replace("ring|ring-offset", "ring-offset|ring")})-(?:${COLOUR_TOKENS_ALT})\\/\\d+`), line),
  },
  {
    id: "focus-name",
    rule: "outline-ring, border-ring or ring-ring: focus is outline-brand and border-brand (DESIGN_SYSTEM §8.3)",
    find: (line) => all(utility("(?:outline|border|ring)-ring(?:\\/\\d+)?"), line),
  },
  {
    id: "disabled-opacity",
    rule: "a disabled opacity other than 50",
    find: (line) => all(/(?<![\w-])disabled:opacity-(?!50(?![\w-]))\d+/g, line),
  },
  {
    id: "arbitrary-type",
    rule: "an arbitrary tracking or leading: use tracking-eyebrow, leading-display or the scale",
    find: (line) => all(utility("(?:tracking|leading)-\\[[^\\]]*\\]"), line),
  },
  { id: "arbitrary-text", rule: "an arbitrary text size or colour: use a type role or a token", find: (line) => all(/(?<![\w-])text-\[[^\]]*\]/g, line) },
  { id: "arbitrary-radius", rule: "an arbitrary radius: use the radius scale", find: (line) => all(/(?<![\w-])rounded(?:-[a-z]{1,2})?-\[(?!inherit\])[^\]]*\]/g, line) },
  { id: "bare-rounded", rule: "a bare `rounded` (4 px): use rounded-sm", find: (line) => all(/(?<![\w-])rounded(?![\w-])/g, line) },
  { id: "dark-variant", rule: "a dark: variant: the app is dark only; the tokens are the dark values", find: (line) => all(/(?<![\w-])dark:[\w-[]/g, line) },
  { id: "ring-ring-alpha", rule: "the translucent shadcn ring: focus is the outline (DESIGN_SYSTEM §8.3)", find: (line) => all(/(?<![\w-])ring-ring\/\d+/g, line) },
];

/** A bare `outline-none` (no variant) removes the base layer's focus outline. */
const BARE_OUTLINE = /(?<![\w:-])outline-(?:none|hidden)(?![\w-])/;
/**
 * Allowed when the element is a programmatic focus target (`tabIndex={-1}`: the skip link's
 * <main>, a heading focused after navigation) or when the same line gives a `focus-visible:`
 * replacement. Radix's dialog and popover content are focused on open, the same as a
 * `tabIndex={-1}` target, so their primitives may set it.
 */
const OUTLINE_PRIMITIVES = ["dialog.tsx", "alert-dialog.tsx", "popover.tsx"].map((name) => ["components", "ui", name].join("/"));

/** Files the lint doesn't read: generated from globals.css, or the exception list itself. */
const SKIPPED = ["styles/tokens.generated.ts", "styles/colour-exceptions.ts"];

function walk(dir: string, keep: (name: string) => boolean): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "node_modules" ? [] : walk(path, keep);
    return keep(name) ? [path] : [];
  });
}

const isTest = (name: string) => /\.test\.(ts|tsx)$/.test(name);
const isComment = (line: string) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line);
const posix = (path: string) => path.split(sep).join("/");

type Hit = { file: string; line: number; text: string; rule: string; id: string };

/** Every rule hit in the app's source, before the exception list is applied. */
function scan(): Hit[] {
  const hits: Hit[] = [];
  const read = (file: string, name: string, literalOnly: boolean) => {
    const text = readFileSync(file, "utf8");
    text.split("\n").forEach((line, index) => {
      if (isComment(line)) return;
      for (const { id, rule, find, literalOnly: onlyLiterals } of RULES) {
        if (literalOnly && !onlyLiterals) continue;
        for (const found of find(line)) hits.push({ file: name, line: index + 1, text: found, rule, id });
      }
      if (
        !literalOnly &&
        BARE_OUTLINE.test(line) &&
        !line.includes("tabIndex={-1}") &&
        !/(?<![\w-])focus-visible:(?!outline-none)/.test(line) &&
        !OUTLINE_PRIMITIVES.includes(name)
      ) {
        hits.push({ file: name, line: index + 1, text: "outline-none", rule: "outline-none without a focus-visible replacement", id: "outline-none" });
      }
    });
    if (!literalOnly) {
      // A Button already wears the gradient (variant `default`); restating it on a call site hides
      // the variant it actually renders.
      for (const match of text.matchAll(/<Button\b[^>]*?\bbg-brand-gradient(?![\w-])/g)) {
        const line = text.slice(0, match.index).split("\n").length;
        hits.push({ file: name, line, text: "bg-brand-gradient", rule: "bg-brand-gradient on Button: use the default variant", id: "button-gradient" });
      }
    }
  };
  for (const file of walk(SRC, (name) => /\.(ts|tsx)$/.test(name) && !isTest(name))) {
    const name = posix(relative(SRC, file));
    if (name.startsWith("test/") || SKIPPED.includes(name)) continue; // test helpers name the banned classes
    read(file, name, false);
  }
  // Stylesheets other than globals.css, and the build scripts, may not write colours either.
  for (const file of walk(SRC, (name) => name.endsWith(".css") && name !== "globals.css")) read(file, posix(relative(SRC, file)), true);
  for (const file of readdirSync(join(WEB, "scripts")).filter((name) => name.endsWith(".mjs"))) read(join(WEB, "scripts", file), `../scripts/${file}`, true);
  return hits;
}

const covers = (exception: ColourException, hit: Hit) => exception.kind === "code" && exception.where === hit.file && hit.text.includes(exception.match);

/** Files for an `asset` entry; `*` stands for any name in the file's directory. */
function assetFiles(where: string): string[] {
  const path = join(WEB, where);
  if (!where.includes("*")) return existsSync(path) ? [path] : [];
  const dir = dirname(path);
  const pattern = new RegExp(`^${path.slice(dir.length + 1).replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace("*", ".*")}$`);
  return existsSync(dir) ? readdirSync(dir).filter((name) => pattern.test(name)).map((name) => join(dir, name)) : [];
}

describe("design lint (UI-070, C-127)", () => {
  const hits = scan();

  it("keeps class strings on the tokens and the focus outline in place", () => {
    const unexplained = hits.filter((hit) => !colourExceptions.some((exception) => covers(exception, hit)));
    expect(unexplained.map((hit) => `${hit.file}:${hit.line}: ${hit.rule} (${hit.text})`)).toEqual([]);
  });

  it("has no stale entries: every listed code entry still matches something", () => {
    const stale = colourExceptions.filter((exception) => exception.kind === "code" && !hits.some((hit) => covers(exception, hit)));
    expect(stale.map((e) => (e.kind === "code" ? `${e.where}: ${e.match}` : ""))).toEqual([]);
  });

  it("lists text, runtime, token, alias and asset entries that still exist", () => {
    const problems: string[] = [];
    for (const exception of colourExceptions) {
      if (exception.kind === "text") {
        const file = join(SRC, exception.where);
        if (!existsSync(file) || !readFileSync(file, "utf8").includes(exception.match)) problems.push(`text: ${exception.where} no longer has ${exception.match}`);
      } else if (exception.kind === "runtime") {
        const file = join(SRC, exception.where);
        if (!existsSync(file) || !readFileSync(file, "utf8").includes("colorValue")) problems.push(`runtime: ${exception.where} no longer calls colorValue()`);
      } else if (exception.kind === "tokens") {
        const known = new Set([...Object.keys(tokenValues.colors), ...Object.keys(tokenValues.colorAliases)]);
        for (const token of exception.tokens) if (!known.has(token)) problems.push(`tokens: ${token} is not a token`);
      } else if (exception.kind === "alias") {
        const aliases = Object.keys(tokenValues.shadcn);
        if (!existsSync(join(SRC, exception.where)) || aliases.length === 0) problems.push(`alias: ${exception.where} has no alias layer`);
      } else if (exception.kind === "asset") {
        const files = assetFiles(exception.where);
        if (files.length === 0) problems.push(`asset: ${exception.where} does not exist`);
        else if (exception.match && !files.some((file) => readFileSync(file, "utf8").includes(exception.match!))) problems.push(`asset: ${exception.where} no longer has ${exception.match}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it("gives every entry a reason", () => {
    for (const exception of colourExceptions) expect(exception.reason.length, JSON.stringify(exception)).toBeGreaterThan(20);
  });

  it("catches what it is meant to", () => {
    const find = (id: string, line: string) => RULES.find((rule) => rule.id === id)!.find(line);
    // Default Tailwind colours.
    for (const bad of ["bg-red-500", "text-white", "hover:bg-black/60", "border-t-gray-200", "ring-offset-white"]) {
      expect(find("palette", `className="${bad}"`).length, bad).toBeGreaterThan(0);
    }
    for (const good of ["text-on-brand", "bg-media-chip", "text-fg-secondary", "bg-chart-negative", "bg-transparent", "--color-white"]) {
      expect(find("palette", `className="${good}"`), good).toEqual([]);
    }
    // Undefined tokens: the bg-surface bug.
    expect(find("undefined-token", `className="rounded-xl border border-line bg-surface p-4"`)).toEqual(["bg-surface"]);
    expect(find("undefined-token", `className="hover:text-fg-muted data-[open]:border-edge"`)).toEqual(["text-fg-muted", "border-edge"]);
    for (const good of [
      "bg-panel", "bg-panel-glass", "text-fg-secondary", "border-line-subtle", "border-t border-b-2 border-dashed border-l-danger", "ring-1 ring-line ring-offset-2 ring-offset-panel",
      "text-sm text-2xs text-md text-center text-balance", "shadow-floating shadow-glow shadow-xl", "bg-brand-gradient bg-glow-brand-top bg-linear-to-t from-media-heavy to-transparent",
      "outline-2 outline-offset-2 outline-brand", "fill-current stroke-line-strong divide-y divide-line", "bg-clip-padding bg-repeat",
    ]) {
      expect(find("undefined-token", `"${good}"`), good).toEqual([]);
    }
    // Arbitrary colour, shadow and gradient values.
    for (const bad of ["bg-[#fff]", "text-[rgb(1,2,3)]", "shadow-[0_0_4px_red]", "from-[oklch(0.5_0.1_20)]", "bg-[radial-gradient(circle,var(--color-brand),transparent)]", "border-[color:red]"]) {
      expect(find("arbitrary-colour", `"${bad}"`).length, bad).toBeGreaterThan(0);
    }
    for (const good of ["bg-[url(/grain.jpg)]", "bg-brand-gradient", "w-[320px]", "[mask-image:linear-gradient(to_top,white,transparent)]"]) {
      expect(find("arbitrary-colour", `"${good}"`), good).toEqual([]);
    }
    // Literals, in code.
    for (const bad of [`const c = "#1a2b3c";`, `color: "#fff"`, `x = "rgba(0, 0, 0, 0.5)"`, `"hsl(210 40% 90%)"`, `oklch(0.5 0.1 20)`, `color-mix(in srgb, var(--color-brand) 65%, transparent)`]) {
      expect(find("colour-literal", bad).length, bad).toBeGreaterThan(0);
    }
    for (const good of [`href="#features"`, `"&#123;"`, `rgba(\${a})`, `Not an rgb() token`, `var(--color-brand)`, `className="bg-brand"`, `/^rgb\\((\\d+)/`]) {
      expect(find("colour-literal", good), good).toEqual([]);
    }
    // Inline styles and SVG attributes.
    for (const bad of [`style={{ color: "red" }}`, `style={{ backgroundColor: "#111" }}`, `<path fill="#fff" />`, `style={{ boxShadow: "0 1px red" }}`]) {
      expect(find("inline-colour", bad).length, bad).toBeGreaterThan(0);
    }
    for (const good of [`style={{ color: "var(--color-fg)" }}`, `<path fill="currentColor" />`, `style={{ backgroundImage: "url(/grain.jpg)" }}`, `style={{ background: colorValue("canvas") }}`, `stroke="none"`]) {
      expect(find("inline-colour", good), good).toEqual([]);
    }
    // shadcn aliases anywhere.
    for (const bad of ["bg-popover", "text-muted-foreground", "border-input", "ring-ring", "bg-primary", "text-foreground", "hover:bg-accent", "border-border", "bg-background", "bg-destructive"]) {
      expect(find("shadcn-alias", `"${bad}"`).length, bad).toBeGreaterThan(0);
    }
    for (const good of ["bg-overlay", "text-fg-secondary", "border-line-control", "bg-brand-strong", "data-slot=card", "bg-card-glow-xyz"]) {
      expect(find("shadcn-alias", `"${good}"`), good).toEqual([]);
    }
    // Opacity modifiers on tokens.
    for (const bad of ["bg-panel/50", "hover:bg-fg/90", "border-on-brand/30", "shadow-brand/15", "from-canvas/90", "bg-media-scrim/70", "bg-brand-soft/20"]) {
      expect(find("opacity-modifier", `"${bad}"`).length, bad).toBeGreaterThan(0);
    }
    for (const good of ["bg-panel-glass", "opacity-50", "bg-brand-soft-hover", "w-1/2", "bg-media-chip", "h-px"]) {
      expect(find("opacity-modifier", `"${good}"`), good).toEqual([]);
    }
    // Focus names, disabled opacity, tracking and leading, radius, dark.
    for (const bad of ["outline-ring", "border-ring", "ring-ring", "focus-visible:outline-ring"]) expect(find("focus-name", `"${bad}"`).length, bad).toBeGreaterThan(0);
    for (const good of ["outline-brand", "border-brand", "ring-brand", "ring-1"]) expect(find("focus-name", `"${good}"`), good).toEqual([]);
    expect(find("disabled-opacity", `"disabled:opacity-30"`)).toEqual(["disabled:opacity-30"]);
    expect(find("disabled-opacity", `"disabled:opacity-100"`)).toEqual(["disabled:opacity-100"]);
    expect(find("disabled-opacity", `"disabled:opacity-50 disabled:pointer-events-none"`)).toEqual([]);
    expect(find("arbitrary-type", `"tracking-[0.08em] leading-[1.08]"`)).toEqual(["tracking-[0.08em]", "leading-[1.08]"]);
    expect(find("arbitrary-type", `"tracking-tight leading-display tracking-eyebrow"`)).toEqual([]);
    expect(find("arbitrary-text", `"text-[13px]"`)).toEqual(["text-[13px]"]);
    expect(find("arbitrary-radius", `"rounded-[10px]"`)).toEqual(["rounded-[10px]"]);
    expect(find("arbitrary-radius", `"rounded-[inherit]"`)).toEqual([]);
    expect(find("bare-rounded", `"items-center rounded text-sm"`)).toEqual(["rounded"]);
    expect(find("bare-rounded", `"rounded-sm rounded-t-lg rounded-full"`)).toEqual([]);
    expect(find("dark-variant", `"dark:bg-input/30"`)).toEqual(["dark:b"]);
    expect(find("dark-variant", `"bg-panel dark"`)).toEqual([]);
    expect(find("ring-ring-alpha", `"focus-visible:ring-ring/50"`)).toEqual(["ring-ring/50"]);
    // The outline rule.
    expect(BARE_OUTLINE.test(`"outline-none"`)).toBe(true);
    expect(BARE_OUTLINE.test(`"focus-visible:outline-none"`)).toBe(false);
  });

  it("reads the exception list as a filter: a listed literal passes, an unlisted one does not", () => {
    const hit: Hit = { file: "components/x.tsx", line: 1, text: "color-mix(in srgb, red 5%, transparent)", rule: "r", id: "colour-literal" };
    const listed: ColourException = { kind: "code", where: "components/x.tsx", match: "color-mix(", reason: "A reason that is long enough to read." };
    expect(covers(listed, hit)).toBe(true);
    expect(covers({ ...listed, where: "components/y.tsx" }, hit)).toBe(false);
    expect(covers({ ...listed, match: "rgba(" }, hit)).toBe(false);
    expect(covers({ kind: "text", where: "components/x.tsx", match: "color-mix(", reason: listed.reason }, hit)).toBe(false);
  });

  it("builds its token set from globals.css, aliases included", () => {
    expect(COLOUR_NAMES.has("panel")).toBe(true);
    expect(COLOUR_NAMES.has("popover")).toBe(true); // @theme inline
    expect(COLOUR_NAMES.has("surface")).toBe(false);
    expect(DEFINED_UTILITIES.has("bg-brand-gradient")).toBe(true);
    expect(DEFINED_UTILITIES.has("shadow-glow")).toBe(true);
  });
});
