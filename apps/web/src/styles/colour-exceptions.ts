/**
 * Every intentional colour that is not "a semantic token in a class" (C-100, docs/ui-audit/THEME.md
 * §5). The design lint (design-lint.test.ts) reads this list both ways: a literal, an arbitrary
 * colour value or an allowed shade found in code must be listed here, and a listed entry that no
 * longer exists fails, so the list can't go stale. To add one: write the entry with a reason a
 * reviewer can judge, then run the lint.
 *
 * Kinds:
 * - `code`: text the lint found in a source file (`where` is a path under src/, `match` a substring
 *   of what it found). It allows that text in that file only. Opacity modifiers on tokens go here
 *   too (`match: "bg-panel/50"`); there are none today.
 * - `text`: text that must exist in a file (`where` is a path under src/), because it is a
 *   deliberate dark-only or runtime choice the lint doesn't scan for.
 * - `runtime`: a file that reads token values through `colorValue()` because it can't use CSS
 *   variables; the file must call it and tokens.test.ts holds it to no literals.
 * - `tokens`: a group of colour tokens that are intentional hues (platform brands, status, charts,
 *   media); each must exist in globals.css.
 * - `alias`: the shadcn alias layer in globals.css, kept only for `shadcn add` output.
 * - `asset`: a file outside src/ (path from apps/web; `*` once in the file name for a set) with
 *   colours baked in or written for a medium that can't use the tokens. With `match`, the file must
 *   contain that text.
 */
export type ColourException =
  | { kind: "code"; where: string; match: string; reason: string }
  | { kind: "text"; where: string; match: string; reason: string }
  | { kind: "runtime"; where: string; reason: string }
  | { kind: "tokens"; tokens: string[]; reason: string }
  | { kind: "alias"; where: string; reason: string }
  | { kind: "asset"; where: string; match?: string; reason: string };

export const colourExceptions: ColourException[] = [
  // Intentional hues: tokens, listed so the palette's fixed colours are visible in one place.
  {
    kind: "tokens",
    tokens: ["instagram", "whatsapp", "facebook", "linkedin"],
    reason: "Platform brand colours: the identity of third parties, used for glyphs and fills only, never text.",
  },
  {
    kind: "tokens",
    tokens: ["success", "warning", "danger", "danger-fg", "danger-fill", "success-soft", "warning-soft", "danger-soft"],
    reason: "Status hues are fixed on purpose: a success is green in every screen. The soft steps are their 15% fills.",
  },
  {
    kind: "tokens",
    tokens: ["chart-positive", "chart-neutral", "chart-negative", "chart-series-1"],
    reason: "Chart series: aliases of status and brand tokens, so a series' colour is set in one place (COLOR_SYSTEM §11.6).",
  },
  {
    kind: "tokens",
    tokens: ["media-scrim", "media-wash", "media-chip", "media-heavy", "scrim"],
    reason: "Black over photos, video and behind modals: dark in any theme, so it is not a surface colour. Three named steps replace six opacities.",
  },
  {
    kind: "tokens",
    tokens: ["shell-1", "shell-2"],
    reason: "The logo tile's own gradient: the one place the brand mark has colours of its own. The icon script reads them.",
  },

  // The shadcn layer.
  {
    kind: "alias",
    where: "styles/globals.css",
    reason: "The :root aliases and @theme inline mapping exist only so `shadcn add` output (written in bg-popover, text-muted-foreground …) compiles onto the tokens. Hand-written code never uses the alias class names; the lint refuses them.",
  },

  // Consumers that can't read CSS variables.
  { kind: "runtime", where: "app/layout.tsx", reason: "The viewport themeColor is a meta tag: it takes a value, not a variable." },
  { kind: "runtime", where: "app/manifest.ts", reason: "The web app manifest is JSON: background_color and theme_color are values." },
  { kind: "runtime", where: "app/global-error.tsx", reason: "It replaces the root layout, so the stylesheet isn't loaded: its inline styles take token values." },
  { kind: "runtime", where: "components/marketing/og.tsx", reason: "Satori (next/og) draws the share card and can't read CSS variables." },
  { kind: "runtime", where: "lib/clerk-appearance.ts", reason: "Clerk computes shades from its `variables`, so they must be values; its element styles use the variables." },
  {
    kind: "code",
    where: "components/marketing/og.tsx",
    match: "rgba(0,0,0,0)",
    reason: "The glow's transparent end: Satori parses only the comma form and needs an explicit transparent stop.",
  },

  // Marketing effects: decorative, built from token variables with a fixed share (color-mix).
  {
    kind: "code",
    where: "components/marketing/effects/lamp.tsx",
    match: "color-mix(",
    reason: "The lamp's two cones: brand at 65% over transparent, in an inline conic gradient. A marketing effect, not a theme colour.",
  },
  {
    kind: "code",
    where: "components/marketing/effects/spotlight-new.tsx",
    match: "color-mix(",
    reason: "The spotlight's three beams: brand tints at 3 to 13%, in inline radial gradients. A marketing effect.",
  },
  {
    kind: "code",
    where: "components/marketing/effects/moving-border.tsx",
    match: "bg-[radial-gradient(",
    reason: "The moving border's light spot: a radial gradient of brand-fg that rotates around the frame. A marketing effect.",
  },
  {
    kind: "code",
    where: "components/marketing/AutomationShowcase.tsx",
    match: "bg-[radial-gradient(",
    reason: "A circular brand glow behind the automation shot (closest-side, not the top glow's ellipse). Marketing only.",
  },

  // Deliberate states the lint can't derive.
  {
    kind: "code",
    where: "components/agent/AskComposer.tsx",
    match: "disabled:opacity-100",
    reason: "The send button when empty is a quiet disabled control at full strength with fg-disabled text, not a half-faded one.",
  },
  {
    kind: "code",
    where: "components/inbox/Composer.tsx",
    match: "disabled:opacity-100",
    reason: "The same empty send button as in Ask.",
  },

  // Dark-only assumptions (the light-theme prerequisites list in THEME.md §1).
  { kind: "text", where: "components/ui/avatar.tsx", match: "mix-blend-lighten", reason: "The avatar edge lightens the picture; it only makes sense on a dark surface." },
  { kind: "text", where: "app/layout.tsx", match: 'statusBarStyle: "black"', reason: "iOS status bar over a black canvas." },
  { kind: "text", where: "components/shell/AppSidebar.tsx", match: "url(/grain.jpg)", reason: "A dark grain texture over the sidebar." },
  { kind: "text", where: "components/auth/AuthShell.tsx", match: "url(/grain.jpg)", reason: "The same grain over the auth panel." },

  // Files with colours baked in, and the email templates.
  { kind: "asset", where: "src/app/favicon.ico", reason: "Static binary, drawn from the logo mark." },
  { kind: "asset", where: "src/app/apple-icon.png", reason: "Generated by scripts/generate-icons.mjs from shell-1, shell-2 and fg." },
  { kind: "asset", where: "src/app/(marketing)/og.png", reason: "Static share image; og.tsx draws the same card from tokens." },
  { kind: "asset", where: "public/icons/*.png", reason: "App and badge icons, generated by scripts/generate-icons.mjs from the tokens." },
  { kind: "asset", where: "public/grain.jpg", reason: "A photographic noise texture." },
  { kind: "asset", where: "public/marketing/*.webp", reason: "Product screenshots for the marketing site." },
  {
    kind: "asset",
    where: "../api/src/socialhood/notify/templates/layout.py",
    match: "#09090b",
    reason: "Emails: clients ignore CSS variables and render light, so the templates carry their own zinc palette (#09090b, #27272a, #52525b, #e4e4e7, #f4f4f5, #ffffff) as inline styles. Outside the web app; not changed here (C-100).",
  },
  {
    kind: "asset",
    where: "scripts/ui-shots/shots.spec.ts",
    match: "#4b5262",
    reason: "A placeholder image drawn for screenshots (an SVG with two greys). A test fixture, not shipped.",
  },
  { kind: "asset", where: "src/app/manifest.test.ts", match: "#000000", reason: "The test states the canvas value on purpose, so a canvas change has to be a decision." },
];
