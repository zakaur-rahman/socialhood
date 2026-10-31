// Writes src/styles/tokens.generated.ts and tokens.generated.json from src/styles/globals.css, the
// one place theme values are written (C-127, docs/ui-audit/THEME.md). No dependencies.
//
//   node scripts/gen-tokens.mjs          (pnpm tokens; also runs before `pnpm dev` and `pnpm build`)
//
// It reads: the `@theme` block (colours, shadows, font sizes, tracking, leading, radii, easings,
// breakpoints, spacing and containers; a colour or shadow that differs between themes is written `light-dark(LIGHT, DARK)`
// and split into a dark set and a light set, C-129), the `:root` variables (motion durations, gradients, shadcn aliases), `@custom-variant`
// lines and the one-line `@utility` rules. tokens.test.ts runs `generate()` again and fails when
// the committed files differ, so an edit to globals.css without `pnpm tokens` can't land.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const CSS_PATH = join(root, "src", "styles", "globals.css");
export const JSON_PATH = join(root, "src", "styles", "tokens.generated.json");
export const TS_PATH = join(root, "src", "styles", "tokens.generated.ts");

/** The body of every top-level block whose header matches, e.g. `:root` or `@theme inline`. */
function blocks(css, header) {
  const found = [];
  for (const match of css.matchAll(new RegExp(`(^|\\n)${header}\\s*\\{`, "g"))) {
    let depth = 1;
    let i = (match.index ?? 0) + match[0].length;
    const start = i;
    for (; i < css.length && depth > 0; i += 1) {
      if (css[i] === "{") depth += 1;
      else if (css[i] === "}") depth -= 1;
    }
    found.push(css.slice(start, i - 1));
  }
  return found;
}

/** `--name: value;` declarations of a block, in file order (values never contain a semicolon). */
function declarations(body) {
  const out = [];
  for (const match of body.matchAll(/--([a-z0-9-*]+):\s*([^;]+);/g)) out.push([match[1], match[2].trim().replace(/\s+/g, " ")]);
  return out;
}

/**
 * Picks one side of every `light-dark(LIGHT, DARK)` in a value, nested ones included:
 * `resolveTheme("0 1px light-dark(#fff, #000)", "dark")` is `0 1px #000`. A value without the
 * function is the same in both themes and comes back unchanged. The arguments are split at the
 * top-level comma, so `color-mix(in srgb, …)` and `rgb(…)` inside them are safe.
 */
export function resolveTheme(value, theme) {
  const open = value.indexOf("light-dark(");
  if (open === -1) return value;
  let depth = 0;
  let comma = -1;
  let i = open + "light-dark(".length;
  const start = i;
  for (; i < value.length; i += 1) {
    const ch = value[i];
    if (ch === "(") depth += 1;
    else if (ch === ")") {
      if (depth === 0) break;
      depth -= 1;
    } else if (ch === "," && depth === 0 && comma === -1) comma = i;
  }
  if (comma === -1 || i >= value.length) throw new Error(`Unbalanced light-dark() in: ${value}`);
  const light = value.slice(start, comma).trim();
  const dark = value.slice(comma + 1, i).trim();
  const rest = value.slice(i + 1);
  return resolveTheme(value.slice(0, open) + (theme === "light" ? light : dark) + resolveTheme(rest, theme), theme);
}

const stripComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** @param {string} source the text of globals.css */
export function generate(source) {
  const css = stripComments(source.replace(/\r\n/g, "\n"));
  const themeAll = declarations(blocks(css, "@theme").join("\n"));
  // The dark set is the default: `colors`, `shadows` and the rest are the dark values, as before.
  // The light set repeats every colour and shadow, resolved the same way (one side of each pair).
  const theme = themeAll.map(([name, value]) => [name, resolveTheme(value, "dark")]);
  const themeLight = themeAll.map(([name, value]) => [name, resolveTheme(value, "light")]);
  const pairs = themeAll.filter(([, value]) => value.includes("light-dark(")).map(([name]) => name);
  const rootVars = declarations(blocks(css, ":root").join("\n"));

  const colors = {};
  const colorAliases = {};
  const shadows = {};
  const fontSizes = {};
  const tracking = {};
  const leading = {};
  const radius = {};
  const easings = {};
  const breakpoints = {};
  const spacing = {};
  const containers = {};
  for (const [name, value] of theme) {
    if (name === "color-*") continue; // the palette lock, `--color-*: initial`
    const alias = value.match(/^var\(--color-([a-z0-9-]+)\)$/);
    if (name.startsWith("color-")) {
      if (alias) colorAliases[name.slice(6)] = alias[1];
      else colors[name.slice(6)] = value;
    } else if (name.startsWith("shadow-")) shadows[name.slice(7)] = value;
    else if (name.startsWith("text-") && name.endsWith("--line-height")) {
      (fontSizes[name.slice(5, -13)] ??= {}).lineHeight = value;
    } else if (name.startsWith("text-")) (fontSizes[name.slice(5)] ??= {}).size = value;
    else if (name.startsWith("tracking-")) tracking[name.slice(9)] = value;
    else if (name.startsWith("leading-")) leading[name.slice(8)] = value;
    else if (name.startsWith("radius-")) radius[name.slice(7)] = value;
    else if (name.startsWith("ease-")) easings[name.slice(5)] = value;
    else if (name.startsWith("breakpoint-")) breakpoints[name.slice(11)] = value;
    else if (name.startsWith("spacing-")) spacing[name.slice(8)] = value; // the public site's rhythm (C-157)
    else if (name.startsWith("container-")) containers[name.slice(10)] = value;
  }

  const colorsLight = {};
  const shadowsLight = {};
  for (const [name, value] of themeLight) {
    if (name.startsWith("color-") && name !== "color-*" && !value.match(/^var\(--color-[a-z0-9-]+\)$/)) colorsLight[name.slice(6)] = value;
    else if (name.startsWith("shadow-")) shadowsLight[name.slice(7)] = value;
  }
  const themed = pairs.map((name) => name.replace(/^(color|shadow)-/, "$1:"));

  const motion = {};
  const gradients = {};
  const shadcn = {};
  for (const [name, value] of rootVars) {
    const token = value.match(/^var\(--color-([a-z0-9-]+)\)$/);
    if (name.startsWith("motion-")) motion[name.slice(7)] = value;
    else if (name.startsWith("gradient-")) gradients[name.slice(9)] = value;
    else if (token) shadcn[name] = token[1];
  }

  const variants = {};
  for (const match of css.matchAll(/@custom-variant ([a-z-]+) \((.+)\);/g)) variants[match[1]] = match[2];

  // One-line utilities with a single declaration, like `@utility mask-fade-x { mask-image: …; }`.
  const utilities = {};
  for (const match of css.matchAll(/@utility ([a-z-]+) \{ ([a-z-]+: [^{};]+); \}/g)) {
    if (match[2].startsWith("background-image: var(--gradient-")) continue; // the gradients above
    if (match[2].startsWith("--tw-duration")) continue; // the durations, from `motion`
    utilities[match[1]] = match[2];
  }

  return { colors, colorsLight, themed, colorAliases, shadows, shadowsLight, fontSizes, tracking, leading, radius, easings, breakpoints, spacing, containers, motion, gradients, shadcn, variants, utilities };
}

/** The two files' text, from the generated values. */
export function render(values) {
  const json = `${JSON.stringify(values, null, 2)}\n`;
  const ts = `// Generated by scripts/gen-tokens.mjs from globals.css: do not edit. Change the value in\n// globals.css and run \`pnpm tokens\` (docs/ui-audit/THEME.md). tokens.test.ts fails on drift.\n\nexport const tokenValues = ${JSON.stringify(values, null, 2)} as const;\n`;
  return { json, ts };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const { json, ts } = render(generate(readFileSync(CSS_PATH, "utf8")));
  writeFileSync(JSON_PATH, json);
  writeFileSync(TS_PATH, ts);
  console.log("tokens: wrote tokens.generated.ts and tokens.generated.json");
}
