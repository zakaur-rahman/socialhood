/**
 * Every intentional colour that is not "a semantic token in a class" (C-127, docs/ui-audit/THEME.md
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
  // The website chat widget's accent presets (GR-28): colours a business picks for its own site.
  ...["#4467E6", "#0F766E", "#15803D", "#BE185D", "#C2410C", "#334155"].map(
    (match): ColourException => ({
      kind: "code",
      where: "components/widget/accents.ts",
      match,
      reason:
        "Widget accent presets: the widget runs in its own frame on a customer's site and can't read our variables, so the business's chosen colour is stored and sent as hex. Customer data, not our theme.",
    }),
  ),
  // Intentional hues: tokens, listed so the palette's fixed colours are visible in one place.
  {
    kind: "tokens",
    tokens: ["instagram", "whatsapp", "facebook", "linkedin"],
    reason: "Platform brand colours: the identity of third parties, used for glyphs and fills only, never text.",
  },
  {
    kind: "tokens",
    tokens: ["instagram-logo-1", "instagram-logo-2", "instagram-logo-3", "instagram-logo-4", "facebook-logo", "whatsapp-logo"],
    reason:
      "The platforms' exact logo colours, for logo tiles that carry no text (Add account). The fills above are darkened for white text; these match the real marks.",
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
    tokens: ["chart-series-2", "chart-series-3", "chart-series-4", "chart-series-5", "chart-series-6"],
    reason:
      "The categorical chart palette after the brand hue: the fixed order for accounts, platforms and topics. Distinct hues on purpose, validated for colour-blind separation in both themes; charts only, never text.",
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
  { kind: "runtime", where: "app/(marketing)/layout.tsx", reason: "The public site's viewport themeColor is a meta tag: the paper value, not a variable (C-155)." },
  { kind: "runtime", where: "lib/pwa/manifest.ts", reason: "The web app manifest is JSON: background_color and theme_color are values. Dark on purpose in light mode: the installed app opens on the dark default (C-129)." },
  { kind: "runtime", where: "app/global-error.tsx", reason: "It replaces the root layout, so the stylesheet isn't loaded: its inline styles take token values, dark: the page can't know the theme (C-129)." },
  { kind: "runtime", where: "components/marketing/og.tsx", reason: "Satori (next/og) draws the share card and can't read CSS variables. The card is drawn on the public site's paper with the site's tokens (C-157): a share image is one picture for every theme." },
  { kind: "runtime", where: "lib/theme.ts", reason: "The theme-color meta tag takes a value, not a variable: the canvas of the theme on screen (C-129), or the public site's paper (C-155)." },
  { kind: "runtime", where: "lib/clerk-appearance.ts", reason: "Clerk computes shades from its `variables`, so they must be values; its element styles use the variables." },

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

  // Choices that stay dark or are texture, not a token (the light-theme list in THEME.md §1, C-129).
  { kind: "text", where: "app/layout.tsx", match: 'statusBarStyle: "black"', reason: "iOS reads the status bar style once, at launch, so it can't follow the theme: black suits the default (Dark)." },
  { kind: "text", where: "components/shell/AppSidebar.tsx", match: "url(/grain.jpg)", reason: "A grain texture over the sidebar; its opacity is --grain-opacity, which is 0 on light." },
  { kind: "text", where: "components/auth/AuthShell.tsx", match: "url(/grain.jpg)", reason: "The same grain over the auth panel." },

  // Files with colours baked in, and the email templates.
  { kind: "asset", where: "src/app/favicon.ico", reason: "Generated by scripts/generate-icons.mjs from shell-1, shell-2, fg and brand-deep." },
  { kind: "asset", where: "src/app/apple-icon.png", reason: "Generated by scripts/generate-icons.mjs from shell-1, shell-2, fg and brand-deep." },
  { kind: "asset", where: "src/app/(marketing)/og.png", reason: "The share image is drawn at build time by og.tsx from tokens; no file sits here." },
  { kind: "asset", where: "public/icons/*.png", reason: "App and badge icons, generated by scripts/generate-icons.mjs from the tokens." },
  { kind: "asset", where: "public/grain.jpg", reason: "A photographic noise texture." },
  { kind: "asset", where: "public/marketing/*.webp", reason: "Product screenshots for the marketing site." },
  {
    kind: "asset",
    where: "../api/src/socialhood/notify/templates/layout.py",
    match: "#09090b",
    reason: "Emails: clients ignore CSS variables and render light, so the templates carry their own zinc palette (#09090b, #27272a, #52525b, #e4e4e7, #f4f4f5, #ffffff) as inline styles. Outside the web app; not changed here (C-127).",
  },
  {
    kind: "asset",
    where: "scripts/ui-shots/shots.spec.ts",
    match: "#4b5262",
    reason: "A placeholder image drawn for screenshots (an SVG with two greys). A test fixture, not shipped.",
  },
  { kind: "asset", where: "src/lib/pwa/manifest.test.ts", match: "#131520", reason: "The test states the canvas value on purpose, so a canvas change has to be a decision." },
];
