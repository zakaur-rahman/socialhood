/**
 * What the design tokens are for, as data: the /dev/tokens page renders it and tokens.test.ts
 * checks it against globals.css. The VALUES are not written here: globals.css is the only place a
 * theme value is written, and `pnpm tokens` (scripts/gen-tokens.mjs) copies them into
 * tokens.generated.ts, which this file reads (C-127, docs/ui-audit/THEME.md). What lives here is
 * the description of each token (name, use, swatch class) and the type-role constants, which
 * components import (`EYEBROW` …) instead of restating the classes.
 */
import { tokenValues } from "./tokens.generated";

/** `swatch` is a literal class so Tailwind emits the variable (it only keeps theme values in use). */
export type ColorToken = { name: string; value: string; light: string; use: string; swatch: string };

/** The two themes (C-129) and the values for code that can't read CSS variables, from token-values.ts (C-152). */
export type { Theme } from "./token-values";
export { colorValue, radiusValue } from "./token-values";

/** What each colour is for, by name. Every `--color-*` in globals.css needs an entry (tokens.test.ts). */
const colorMeta: Record<string, { use: string; swatch: string }> = {
  // Surfaces
  canvas: { use: "App and thread background", swatch: "bg-canvas" },
  panel: { use: "Cards, sidebar, list pane, headers, composer bar, the phone drawer", swatch: "bg-panel" },
  field: { use: "Inputs, incoming bubbles, segmented track", swatch: "bg-field" },
  raised: { use: "Selected row, active segment, focused input, secondary button", swatch: "bg-raised" },
  "raised-hover": { use: "Hover on raised surfaces", swatch: "bg-raised-hover" },
  overlay: { use: "What floats: popovers, menus, select options, dialogs, sheets, toasts (D-12)", swatch: "bg-overlay" },
  // States: overlays, so they work on any surface
  hover: { use: "Hover fill on any surface; neutral chip fill", swatch: "bg-hover" },
  pressed: { use: "Pressed or open (aria-expanded, data-state=open)", swatch: "bg-pressed" },
  scrim: { use: "Modal and drawer backdrop", swatch: "bg-scrim" },
  "media-scrim": { use: "On photos and video only; the base of the three media steps", swatch: "bg-media-scrim" },
  "media-wash": { use: "A light dim over a photo: file cards, thumbnails", swatch: "bg-media-wash" },
  "media-chip": { use: "A label or button on a photo: count chips, captions", swatch: "bg-media-chip" },
  "media-heavy": { use: "Text over a photo: upload progress, the end of a caption fade", swatch: "bg-media-heavy" },
  "canvas-veil": { use: "A dimmed cell or inset: days outside the month, a card in a flow", swatch: "bg-canvas-veil" },
  "panel-glass": { use: "Marketing cards over the page glow", swatch: "bg-panel-glass" },
  "panel-veil": { use: "The floating marketing nav over scrolled content", swatch: "bg-panel-veil" },
  // Glass (C-128): a surface token at a set strength; the glass-* utilities add the blur
  "panel-frost": { use: "Work panes on glass: sidebar, inbox panes, headers, composer bar (82% panel, light blur)", swatch: "bg-panel-frost" },
  "card-glass": { use: "Cards on glass (68% panel, medium blur)", swatch: "bg-card-glass" },
  "overlay-frost": { use: "What floats on glass: menus, popovers, selects, dialogs, sheets, toasts (86% overlay, strong blur)", swatch: "bg-overlay-frost" },
  "raised-frost": { use: "The secondary button on glass (72% raised)", swatch: "bg-raised-frost" },
  "frost-outline": { use: "The outline button on glass (45% panel)", swatch: "bg-frost-outline" },
  "ambient-1": { use: "The ambient light's top-left glow, behind the glass", swatch: "bg-ambient-1" },
  "ambient-2": { use: "The ambient light's top-right glow", swatch: "bg-ambient-2" },
  "ambient-3": { use: "The ambient light's bottom pool", swatch: "bg-ambient-3" },
  // Lines
  "line-glass": { use: "A card's edge on glass, quieter than line", swatch: "bg-line-glass" },
  line: { use: "Borders", swatch: "bg-line" },
  "line-subtle": { use: "Faint borders", swatch: "bg-line-subtle" },
  "line-strong": { use: "Emphasised borders", swatch: "bg-line-strong" },
  "line-control": { use: "Control edges, 3:1 or more on every surface: fields, selects, checkboxes, switches (D-01)", swatch: "bg-line-control" },
  // Text
  fg: { use: "Primary text", swatch: "bg-fg" },
  "fg-secondary": { use: "Secondary and meta text, timestamps, placeholders (D-06)", swatch: "bg-fg-secondary" },
  "fg-disabled": { use: "Disabled controls only", swatch: "bg-fg-disabled" },
  "fg-hover": { use: "Hover on the inverse button (bg-fg)", swatch: "bg-fg-hover" },
  "on-brand": { use: "Text and icons on the brand gradient, brand-strong, danger-fill, platform fills", swatch: "bg-on-brand" },
  "on-brand-soft": { use: "A quiet fill on a brand bubble: image and button previews", swatch: "bg-on-brand-soft" },
  "on-brand-line": { use: "An edge on a brand bubble", swatch: "bg-on-brand-line" },
  "on-brand-line-strong": { use: "A chip edge on a brand bubble", swatch: "bg-on-brand-line-strong" },
  // Brand
  brand: { use: "Non-text marks: focus ring, dots, selection bar, switch on, checkbox checked", swatch: "bg-brand" },
  "brand-strong": { use: "Solid brand fills that carry text; the gradient's end", swatch: "bg-brand-strong" },
  "brand-deep": { use: "Gradient start", swatch: "bg-brand-deep" },
  "brand-fg": { use: "Brand-coloured text and icons on dark", swatch: "bg-brand-fg" },
  "brand-soft": { use: "Soft brand fills; the info tone", swatch: "bg-brand-soft" },
  "brand-soft-hover": { use: "Hover and open on brand-soft: the soft button (C-073)", swatch: "bg-brand-soft-hover" },
  "brand-line": { use: "Brand borders", swatch: "bg-brand-line" },
  "shell-1": { use: "Logo tile and upgrade button", swatch: "bg-shell-1" },
  "shell-2": { use: "Logo tile and upgrade button", swatch: "bg-shell-2" },
  // Status
  success: { use: "Success", swatch: "bg-success" },
  warning: { use: "Warning", swatch: "bg-warning" },
  danger: { use: "Danger icons and borders", swatch: "bg-danger" },
  "danger-fg": { use: "Danger text on dark", swatch: "bg-danger-fg" },
  "danger-fill": { use: "Failed bubble background; the destructive button", swatch: "bg-danger-fill" },
  "danger-fill-hover": { use: "Hover on the destructive button", swatch: "bg-danger-fill-hover" },
  "success-soft": { use: "Success chip, banner and callout fill", swatch: "bg-success-soft" },
  "warning-soft": { use: "Warning chip, banner and callout fill", swatch: "bg-warning-soft" },
  "danger-soft": { use: "Danger chip, banner and callout fill; destructive menu highlight", swatch: "bg-danger-soft" },
  "danger-line": { use: "Danger callout edge", swatch: "bg-danger-line" },
  "warning-line": { use: "Warning callout edge", swatch: "bg-warning-line" },
  // Platforms: fills and glyphs only, never text
  instagram: { use: "Instagram", swatch: "bg-instagram" },
  whatsapp: { use: "WhatsApp", swatch: "bg-whatsapp" },
  facebook: { use: "Facebook", swatch: "bg-facebook" },
  linkedin: { use: "LinkedIn", swatch: "bg-linkedin" },
  web: { use: "Website chat (GR-28)", swatch: "bg-web" },
  // The platforms' own logo colours: logo tiles only, never under text
  "instagram-logo-1": { use: "Instagram logo gradient, first stop", swatch: "bg-instagram-logo-1" },
  "instagram-logo-2": { use: "Instagram logo gradient, second stop", swatch: "bg-instagram-logo-2" },
  "instagram-logo-3": { use: "Instagram logo gradient, third stop", swatch: "bg-instagram-logo-3" },
  "instagram-logo-4": { use: "Instagram logo gradient, last stop", swatch: "bg-instagram-logo-4" },
  "facebook-logo": { use: "Facebook logo tile", swatch: "bg-facebook-logo" },
  "whatsapp-logo": { use: "WhatsApp logo tile", swatch: "bg-whatsapp-logo" },
  // The categorical chart palette after series 1 (brand): charts only, never text
  "chart-series-2": { use: "Chart series 2 (orange): the 2th account, platform or topic in a chart", swatch: "bg-chart-series-2" },
  "chart-series-3": { use: "Chart series 3 (aqua): the 3th account, platform or topic in a chart", swatch: "bg-chart-series-3" },
  "chart-series-4": { use: "Chart series 4 (yellow): the 4th account, platform or topic in a chart", swatch: "bg-chart-series-4" },
  "chart-series-5": { use: "Chart series 5 (magenta): the 5th account, platform or topic in a chart", swatch: "bg-chart-series-5" },
  "chart-series-6": { use: "Chart series 6 (blue): the 6th account, platform or topic in a chart", swatch: "bg-chart-series-6" },
  // The public site's palette (C-155): paper, night and the accent; public pages only
  "paper": { use: "The public site's page: the light paper bands (C-155)", swatch: "bg-paper" },
  "paper-deep": { use: "The public site's second paper: the controls band, the FAQ, chips", swatch: "bg-paper-deep" },
  "sheet": { use: "Cards and panels on the public site's paper", swatch: "bg-sheet" },
  "ink": { use: "Text on the public site's paper; the main button", swatch: "bg-ink" },
  "ink-secondary": { use: "Secondary text on paper: 8:1 on paper", swatch: "bg-ink-secondary" },
  "ink-tertiary": { use: "Meta text on paper: 5.66:1 on paper, 5.27:1 on paper-deep (C-157)", swatch: "bg-ink-tertiary" },
  "site-line-control": { use: "A control's edge on paper (secondary button, inputs): 3.42:1 on paper, 3.74:1 on sheet (C-157)", swatch: "bg-site-line-control" },
  "night-line-control": { use: "A control's edge on night: 3.63:1 on night (C-157)", swatch: "bg-night-line-control" },
  "rule": { use: "Borders on paper", swatch: "bg-rule" },
  "rule-subtle": { use: "Faint borders on paper", swatch: "bg-rule-subtle" },
  "night": { use: "The public site's night bands: how it decides, trust, closing, footer", swatch: "bg-night" },
  "night-raised": { use: "Cards on a night band", swatch: "bg-night-raised" },
  "night-high": { use: "Incoming bubbles and rows on night cards", swatch: "bg-night-high" },
  "night-ink": { use: "Text on a night band", swatch: "bg-night-ink" },
  "night-ink-secondary": { use: "Secondary text on night", swatch: "bg-night-ink-secondary" },
  "night-ink-tertiary": { use: "Meta text on night: 6:1 on night", swatch: "bg-night-ink-tertiary" },
  "iris": { use: "The public site's accent, four roles only: links, focus, selection and AI moments (C-157)", swatch: "bg-iris" },
  "iris-ink": { use: "Accent text on iris-soft", swatch: "bg-iris-ink" },
  "iris-soft": { use: "Soft accent fills on paper: draft chips, matched comments", swatch: "bg-iris-soft" },
  "iris-night": { use: "The accent on a night band", swatch: "bg-iris-night" },
  "iris-mist": { use: "A quiet accent bar segment in the comment summary: 3.24:1 on sheet", swatch: "bg-iris-mist" },
  "site-ok": { use: "Positive status text and marks on paper", swatch: "bg-site-ok" },
  "site-ok-soft": { use: "Positive chip fill on paper", swatch: "bg-site-ok-soft" },
  "site-wait": { use: "Waiting status text on paper (Needs you)", swatch: "bg-site-wait" },
  "site-wait-soft": { use: "Waiting chip fill on paper", swatch: "bg-site-wait-soft" },
  "site-wait-mark": { use: "The dot of a status that waits on someone else: 3.92:1 on paper", swatch: "bg-site-wait-mark" },
  "instagram-night": { use: "The Instagram mark on a night band: 4.94:1 on night-raised (C-157)", swatch: "bg-instagram-night" },
  "web-night": { use: "The website-chat mark on a night band: 5.01:1 on night-high (C-157)", swatch: "bg-web-night" },
  "site-stop": { use: "Stopped status text and marks on paper (spam)", swatch: "bg-site-stop" },
  "site-stop-soft": { use: "Stopped chip fill on paper", swatch: "bg-site-stop-soft" },
  "handoff": { use: "The hand-off callout's amber on night", swatch: "bg-handoff" },
  "handoff-ink": { use: "Hand-off text on night", swatch: "bg-handoff-ink" },
  "handoff-ink-strong": { use: "Hand-off emphasis on night", swatch: "bg-handoff-ink-strong" },
  "comment": { use: "The mark for an Instagram comment in the demos", swatch: "bg-comment" },
  "avatar-1": { use: "Demo avatar tint", swatch: "bg-avatar-1" },
  "avatar-2": { use: "Demo avatar tint", swatch: "bg-avatar-2" },
  "avatar-3": { use: "Demo avatar tint", swatch: "bg-avatar-3" },
  "avatar-4": { use: "Demo avatar tint", swatch: "bg-avatar-4" },
  "avatar-5": { use: "Demo avatar tint", swatch: "bg-avatar-5" },
  "avatar-6": { use: "Demo avatar tint", swatch: "bg-avatar-6" },
};

/**
 * Colours that are the same in both themes on purpose, written once in globals.css: a literal here
 * has no `light-dark()`. Every other literal colour must be a pair (tokens.test.ts), so a new token
 * can't be added to one theme only. Shades (`color-mix` of another token) follow their base and
 * are not listed.
 */
export const themeInvariant: Record<string, string> = {
  "media-scrim": "Black over photos and video, dark in any theme",
  "on-brand": "White on the brand gradient, brand-strong, danger-fill and platform fills, in both themes",
  "brand-strong": "The gradient's end and the primary fill: white on it is 5.82:1 in both themes",
  "brand-deep": "The gradient's start",
  "shell-1": "The logo tile's own gradient; the icons are drawn from it",
  "shell-2": "The logo tile's own gradient; the icons are drawn from it",
  "danger-fill": "The failed bubble and the destructive button carry white text: 5.47:1 in both themes",
  instagram: "A third party's brand colour",
  whatsapp: "A third party's brand colour",
  facebook: "A third party's brand colour",
  linkedin: "A third party's brand colour",
  web: "The website chat's badge fill: white on it is 5.5:1 in both themes",
  "instagram-logo-1": "A third party's logo colour",
  "instagram-logo-2": "A third party's logo colour",
  "instagram-logo-3": "A third party's logo colour",
  "instagram-logo-4": "A third party's logo colour",
  "facebook-logo": "A third party's logo colour",
  "whatsapp-logo": "A third party's logo colour",
  "paper": "The public site's own palette (C-155): the same whatever the app theme",
  "paper-deep": "The public site's own palette (C-155): the same whatever the app theme",
  "sheet": "The public site's own palette (C-155): the same whatever the app theme",
  "ink": "The public site's own palette (C-155): the same whatever the app theme",
  "ink-secondary": "The public site's own palette (C-155): the same whatever the app theme",
  "ink-tertiary": "The public site's own palette (C-155): the same whatever the app theme",
  "site-line-control": "The public site's own palette (C-155): the same whatever the app theme",
  "night-line-control": "The public site's own palette (C-155): the same whatever the app theme",
  "rule": "The public site's own palette (C-155): the same whatever the app theme",
  "rule-subtle": "The public site's own palette (C-155): the same whatever the app theme",
  "night": "The public site's own palette (C-155): the same whatever the app theme",
  "night-raised": "The public site's own palette (C-155): the same whatever the app theme",
  "night-high": "The public site's own palette (C-155): the same whatever the app theme",
  "night-ink": "The public site's own palette (C-155): the same whatever the app theme",
  "night-ink-secondary": "The public site's own palette (C-155): the same whatever the app theme",
  "night-ink-tertiary": "The public site's own palette (C-155): the same whatever the app theme",
  "iris": "The public site's own palette (C-155): the same whatever the app theme",
  "iris-ink": "The public site's own palette (C-155): the same whatever the app theme",
  "iris-soft": "The public site's own palette (C-155): the same whatever the app theme",
  "iris-night": "The public site's own palette (C-155): the same whatever the app theme",
  "iris-mist": "The public site's own palette (C-155): the same whatever the app theme",
  "site-ok": "The public site's own palette (C-155): the same whatever the app theme",
  "site-ok-soft": "The public site's own palette (C-155): the same whatever the app theme",
  "site-wait": "The public site's own palette (C-155): the same whatever the app theme",
  "site-wait-soft": "The public site's own palette (C-155): the same whatever the app theme",
  "site-wait-mark": "The public site's own palette (C-155): the same whatever the app theme",
  "instagram-night": "The public site's own palette (C-155): the same whatever the app theme",
  "web-night": "The public site's own palette (C-155): the same whatever the app theme",
  "site-stop": "The public site's own palette (C-155): the same whatever the app theme",
  "site-stop-soft": "The public site's own palette (C-155): the same whatever the app theme",
  "handoff": "The public site's own palette (C-155): the same whatever the app theme",
  "handoff-ink": "The public site's own palette (C-155): the same whatever the app theme",
  "handoff-ink-strong": "The public site's own palette (C-155): the same whatever the app theme",
  "comment": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-1": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-2": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-3": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-4": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-5": "The public site's own palette (C-155): the same whatever the app theme",
  "avatar-6": "The public site's own palette (C-155): the same whatever the app theme",
};

/** The colour tokens, in the order of globals.css, with their values from the generated file. */
export const colorTokens: ColorToken[] = Object.entries(tokenValues.colors as Record<string, string>).map(([name, value]) => ({
  name,
  value,
  light: (tokenValues.colorsLight as Record<string, string>)[name] ?? value,
  use: colorMeta[name]?.use ?? "",
  swatch: colorMeta[name]?.swatch ?? `bg-${name}`,
}));

/** The names `colorMeta` describes, for the test that every token has a description and no entry is stale. */
export const describedColors: string[] = Object.keys(colorMeta);

/**
 * The chart palette (COLOR_SYSTEM §11.6, UI-ISS-097): aliases of existing tokens, no new hues.
 * Status series (sentiment, failures) sit on the status tokens; a single neutral series on brand.
 * Categorical series (accounts, people) use the identity palette (lib/ui/identity.ts) instead.
 */
const chartMeta = [
  { name: "chart-positive", use: "Positive sentiment", swatch: "bg-chart-positive" },
  { name: "chart-neutral", use: "Neutral sentiment", swatch: "bg-chart-neutral" },
  { name: "chart-negative", use: "Negative sentiment; failures", swatch: "bg-chart-negative" },
  { name: "chart-series-1", use: "A single series: runs, the 7-day trend", swatch: "bg-chart-series-1" },
] as const;
export const chartAliases = chartMeta.map((entry) => ({
  ...entry,
  token: (tokenValues.colorAliases as Record<string, string>)[entry.name],
}));

/** DESIGN_SYSTEM §1.9: four gradients, each with one job, plus the marketing top glow; the stops are tokens. */
const gradientMeta = [
  { name: "bg-brand-gradient", key: "brand", use: "Primary buttons, outgoing bubbles, count badges; on-brand text" },
  { name: "bg-brand-gradient-decor", key: "brand-decor", use: "Meters, progress fills, decorative icon tiles; never under text" },
  { name: "bg-shell-gradient", key: "shell", use: "Logo tile and Upgrade only" },
  { name: "bg-instagram-logo-gradient", key: "instagram-logo", use: "Instagram's logo tile (Add account); never under text" },
  { name: "bg-glow-brand", key: "glow-brand", use: "One per view at most: the plan hero" },
  { name: "bg-ambient", key: "ambient", use: "The light behind the glass, fixed on the body; not for components" },
  { name: "bg-glow-brand-top", key: "glow-brand-top", use: "The marketing glow at the top of a section: the hero, the illustration cards" },
  { name: "bg-glow-brand-centre", key: "glow-brand-centre", use: "A round marketing glow behind one object: the hero's hub" },
] as const;
export const gradientUtilities = gradientMeta.map(({ name, key, use }) => ({
  name,
  variable: `--gradient-${key}`,
  value: (tokenValues.gradients as Record<string, string>)[key],
  use,
}));

/**
 * shadcn's semantic variables (`:root` in globals.css) and the token each one points at
 * (DESIGN_SYSTEM §1.10). Nothing hand-written uses these names; they are there so `shadcn add`
 * output compiles.
 */
export const shadcnAliases = Object.entries(tokenValues.shadcn as Record<string, string>).map(([alias, token]) => ({ alias, token }));

/**
 * Elevation (DESIGN_SYSTEM §6; D-12): the two dark shadows, set by the primitives, never at call
 * sites. The 1 px `line` edge is a separate `ring-1 ring-line` (a sheet: its side border), so a
 * call site's leftover `shadow-xl` replaces only the drop shadow. `sample` is a literal class list
 * so Tailwind emits it for /dev/tokens.
 */
const shadowMeta = [
  { name: "shadow-floating", use: "Level 1, on overlay: popovers, menus, select options, toasts", sample: "bg-overlay ring-1 ring-line shadow-floating" },
  { name: "shadow-overlay", use: "Level 2, on overlay over the scrim: dialogs, alert dialogs, sheets", sample: "bg-overlay ring-1 ring-line shadow-overlay" },
] as const;
export const shadowTokens = shadowMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.shadows as Record<string, string>)[entry.name.replace("shadow-", "")],
  light: (tokenValues.shadowsLight as Record<string, string>)[entry.name.replace("shadow-", "")],
}));

/** The glass family (C-128): a top highlight, a soft drop, the buttons' inner light and glow. */
const glassShadowMeta = [
  { name: "shadow-glass", use: "Glass cards: a top highlight and a soft drop (C-128)", sample: "bg-card-glass ring-1 ring-line-glass shadow-glass" },
  { name: "shadow-highlight", use: "The outline button: the top highlight alone", sample: "bg-frost-outline ring-1 ring-line shadow-highlight" },
  { name: "shadow-button-primary", use: "The primary button: an inner highlight and an indigo glow", sample: "bg-brand-gradient shadow-button-primary" },
  { name: "shadow-button-secondary", use: "The secondary button: an inset edge and the highlight", sample: "bg-raised-frost shadow-button-secondary" },
] as const;
export const glassShadows = glassShadowMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.shadows as Record<string, string>)[entry.name.replace("shadow-", "")],
  light: (tokenValues.shadowsLight as Record<string, string>)[entry.name.replace("shadow-", "")],
}));

/** The marketing glow family (C-127): brand-tinted drops under marketing and auth cards. */
const glowMeta = [
  { name: "shadow-glow", use: "Marketing and auth cards: a brand-tinted 2xl drop", sample: "bg-panel shadow-glow" },
  { name: "shadow-glow-hover", use: "A marketing card on hover: a softer xl drop", sample: "bg-panel shadow-glow-hover" },
  { name: "shadow-glow-button", use: "The marketing primary button and the logo mark: a tight lg drop", sample: "bg-panel shadow-glow-button" },
] as const;
export const glowShadows = glowMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.shadows as Record<string, string>)[entry.name.replace("shadow-", "")],
}));

/** The radius scale (DESIGN_SYSTEM §4); `sample` is a literal class so Tailwind emits it. */
const radiusMeta = [
  { name: "rounded-sm", key: "sm", use: "Checkboxes, small tags, keyboard hints", sample: "rounded-sm" },
  { name: "rounded-md", key: "md", use: "Small buttons, tooltips, thumbnails", sample: "rounded-md" },
  { name: "rounded-lg", key: "lg", use: "Inputs, buttons, selects, menus, popovers, toasts", sample: "rounded-lg" },
  { name: "rounded-xl", key: "xl", use: "App cards, dialogs, sheets", sample: "rounded-xl" },
  { name: "rounded-2xl", key: "2xl", use: "Marketing cards", sample: "rounded-2xl" },
] as const;
export const radiusTokens = radiusMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.radius as Record<string, string>)[entry.key],
}));

const remPx = (rem: string) => Math.round(parseFloat(rem) * 16);

/** The two sizes Tailwind's scale lacks; each carries its line height. */
const fontSizeMeta = [
  { name: "text-2xs", key: "2xs", use: "Status badges, chips, eyebrows, kbd" },
  { name: "text-md", key: "md", use: "Reading: Ask answers and composer, legal prose" },
] as const;
export const fontSizes = fontSizeMeta.map(({ name, key, use }) => {
  const { size, lineHeight } = (tokenValues.fontSizes as Record<string, { size: string; lineHeight: string }>)[key];
  return { name, size, lineHeight, px: `${remPx(size)}/${remPx(lineHeight)}`, use };
});

// Type roles (DESIGN_SYSTEM §2.1). Weights 400, 500 and 600 only; tracking −0.025em at 24 px and
// up, +0.08em on eyebrows only (`tracking-eyebrow`); nothing under 11 px.
export const DISPLAY = "text-4xl font-semibold tracking-tight leading-display sm:text-5xl lg:text-6xl";
export const MARKETING_HEADING = "text-3xl font-semibold tracking-tight sm:text-4xl";
export const PAGE_TITLE = "text-2xl font-semibold tracking-tight";
export const KPI = "text-2xl font-semibold tracking-tight tabular-nums";
export const PANE_TITLE = "text-lg font-semibold";
export const SECTION_TITLE = "text-lg font-semibold";
export const CARD_TITLE = "text-base font-semibold";
export const ITEM_TITLE = "text-sm font-semibold";
export const READING = "text-md";
export const BODY = "text-sm";
export const MESSAGE = "text-sm leading-relaxed";
export const CONTROL = "text-sm font-medium";
export const INPUT_TEXT = "text-base md:text-sm";
export const META = "text-xs text-fg-secondary";
export const SMALL_CONTROL = "text-xs font-medium";
export const CHIP = "text-2xs font-medium";
export const COUNT = "text-xs font-medium";
export const EYEBROW = "text-2xs font-semibold uppercase tracking-eyebrow text-fg-secondary";
export const MONO = "font-mono text-xs";

export const typeRoles = [
  { role: "Display (marketing hero)", name: "DISPLAY", className: DISPLAY },
  { role: "Marketing heading", name: "MARKETING_HEADING", className: MARKETING_HEADING },
  { role: "Page title", name: "PAGE_TITLE", className: PAGE_TITLE },
  { role: "KPI number", name: "KPI", className: KPI },
  { role: "Pane title", name: "PANE_TITLE", className: PANE_TITLE },
  { role: "Section title", name: "SECTION_TITLE", className: SECTION_TITLE },
  { role: "Card and dialog title", name: "CARD_TITLE", className: CARD_TITLE },
  { role: "Item title", name: "ITEM_TITLE", className: ITEM_TITLE },
  { role: "Reading (Ask, legal)", name: "READING", className: READING },
  { role: "Body", name: "BODY", className: BODY },
  { role: "Message", name: "MESSAGE", className: MESSAGE },
  { role: "Control", name: "CONTROL", className: CONTROL },
  { role: "Input (16 px on phones)", name: "INPUT_TEXT", className: INPUT_TEXT },
  { role: "Meta, hint, table header", name: "META", className: META },
  { role: "Small control", name: "SMALL_CONTROL", className: SMALL_CONTROL },
  { role: "Chip, status badge", name: "CHIP", className: CHIP },
  { role: "Count badge", name: "COUNT", className: COUNT },
  { role: "Eyebrow", name: "EYEBROW", className: EYEBROW },
  { role: "Mono", name: "MONO", className: MONO },
] as const;

/** DESIGN_SYSTEM §7: `duration-*` utilities over `--motion-*` variables, which tw-animate-css reads too. */
const motionMeta = [
  { name: "duration-fast", key: "fast", use: "Hover, press, toggles, menus, popovers, tooltips; every exit" },
  { name: "duration-normal", key: "normal", use: "Content arriving in place: live message, inline reveals" },
  { name: "duration-slow", key: "slow", use: "Surfaces: dialogs, sheets, the drawer, panels, the suggestion bar" },
] as const;
export const motionDurations = motionMeta.map(({ name, key, use }) => ({
  name,
  variable: `--motion-${key}`,
  value: (tokenValues.motion as Record<string, string>)[key],
  use,
}));

const easingMeta = [
  { name: "ease-standard", use: "State changes: colour, opacity, toggles" },
  { name: "ease-enter", use: "Things arriving" },
  { name: "ease-exit", use: "Things leaving" },
] as const;
export const easings = easingMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.easings as Record<string, string>)[entry.name.replace("ease-", "")],
}));

export type BreakpointName = "md" | "lg" | "xl" | "wide";

/** Tailwind's breakpoints are kept; `wide` is the one addition. */
const breakpointMeta: { name: BreakpointName; use: string; custom: boolean }[] = [
  { name: "md", use: "Top bar and drawer below it", custom: false },
  { name: "lg", use: "Sidebar expands; three-column dashboards", custom: false },
  { name: "xl", use: "Inbox details inline; settings two columns", custom: false },
  { name: "wide", use: "Inbox details open by default; schedule rail inline", custom: true },
];
export const breakpoints = breakpointMeta.map((entry) => {
  const value = (tokenValues.breakpoints as Record<string, string>)[entry.name];
  return { ...entry, value, px: remPx(value) };
});

/**
 * Variants defined in globals.css besides Tailwind's own (`dark` stays for library code, C-002).
 * `short` names the one viewport-height condition, so no call site writes the media query.
 */
export const customVariants = [
  {
    name: "short",
    value: (tokenValues.variants as Record<string, string>).short,
    use: "Short viewports (200% zoom, a landscape phone): sticky bars stay in the flow, their text on one line",
  },
];

/** Other utilities defined in globals.css. */
const otherUtilityMeta = [
  { name: "mask-fade-x", use: "A row that scrolls sideways: its trailing 1rem fades; pair with pe-4" },
  { name: "shadow-crop-mask", use: "The crop box: dims the photo outside it (media-scrim 60%); its container clips. Not an elevation" },
] as const;
export const otherUtilities = otherUtilityMeta.map((entry) => ({
  ...entry,
  value: (tokenValues.utilities as Record<string, string>)[entry.name],
}));
