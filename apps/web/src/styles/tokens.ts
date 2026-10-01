/**
 * The design tokens from spec §4.2 and the UI audit's design system (docs/ui-audit/DESIGN_SYSTEM.md),
 * as data: the /dev/tokens page renders them and a test checks globals.css against them, so the
 * CSS and the spec cannot drift apart silently. The type-role constants are the source for
 * components: import them (`EYEBROW` …) instead of restating the classes.
 */
/** `swatch` is a literal class so Tailwind emits the variable (it only keeps theme values in use). */
export type ColorToken = { name: string; value: string; use: string; swatch: string };

export const colorTokens: ColorToken[] = [
  // Surfaces
  { name: "canvas", value: "#000000", use: "App and thread background", swatch: "bg-canvas" },
  { name: "panel", value: "#1F1F1F", use: "Sidebar card, list pane, headers, composer bar, popovers", swatch: "bg-panel" },
  { name: "field", value: "#1D1D1D", use: "Inputs, incoming bubbles, segmented track", swatch: "bg-field" },
  { name: "raised", value: "#2A2A2A", use: "Selected row, active segment, focused input, secondary button", swatch: "bg-raised" },
  { name: "raised-hover", value: "#333333", use: "Hover on raised surfaces", swatch: "bg-raised-hover" },
  // States: overlays, so they work on any surface
  { name: "hover", value: "rgb(255 255 255 / 0.05)", use: "Hover fill on any surface; neutral chip fill", swatch: "bg-hover" },
  { name: "pressed", value: "rgb(255 255 255 / 0.10)", use: "Pressed or open (aria-expanded, data-state=open)", swatch: "bg-pressed" },
  { name: "scrim", value: "rgb(0 0 0 / 0.60)", use: "Modal and drawer backdrop", swatch: "bg-scrim" },
  { name: "media-scrim", value: "#000000", use: "On photos and video only, with an opacity (bg-media-scrim/60)", swatch: "bg-media-scrim" },
  // Lines
  { name: "line", value: "rgb(255 255 255 / 0.10)", use: "Borders", swatch: "bg-line" },
  { name: "line-subtle", value: "rgb(255 255 255 / 0.05)", use: "Faint borders", swatch: "bg-line-subtle" },
  { name: "line-strong", value: "rgb(255 255 255 / 0.20)", use: "Emphasised borders", swatch: "bg-line-strong" },
  // Text
  { name: "fg", value: "#FFFFFF", use: "Primary text", swatch: "bg-fg" },
  { name: "fg-secondary", value: "#9B9CA0", use: "Secondary and meta text, timestamps", swatch: "bg-fg-secondary" },
  { name: "fg-disabled", value: "#71717A", use: "Disabled controls and placeholders only", swatch: "bg-fg-disabled" },
  { name: "on-brand", value: "#FFFFFF", use: "Text and icons on the brand gradient, brand-strong, danger-fill, platform fills", swatch: "bg-on-brand" },
  // Brand
  { name: "brand", value: "#567FF8", use: "Non-text marks: focus ring, dots, selection bar, switch on", swatch: "bg-brand" },
  { name: "brand-strong", value: "#4467E6", use: "Solid brand fills that carry text; the gradient's end", swatch: "bg-brand-strong" },
  { name: "brand-deep", value: "#20338A", use: "Gradient start", swatch: "bg-brand-deep" },
  { name: "brand-fg", value: "#9DB5FF", use: "Brand-coloured text and icons on dark", swatch: "bg-brand-fg" },
  { name: "brand-soft", value: "rgb(86 127 248 / 0.15)", use: "Soft brand fills; the info tone", swatch: "bg-brand-soft" },
  { name: "brand-line", value: "rgb(86 127 248 / 0.35)", use: "Brand borders", swatch: "bg-brand-line" },
  { name: "shell-1", value: "#3352CC", use: "Logo tile and upgrade button", swatch: "bg-shell-1" },
  { name: "shell-2", value: "#1C2D70", use: "Logo tile and upgrade button", swatch: "bg-shell-2" },
  // Status
  { name: "success", value: "#22C55E", use: "Success", swatch: "bg-success" },
  { name: "warning", value: "#FB923C", use: "Warning", swatch: "bg-warning" },
  { name: "danger", value: "#EF4444", use: "Danger icons and borders", swatch: "bg-danger" },
  { name: "danger-fg", value: "#FCA5A5", use: "Danger text on dark", swatch: "bg-danger-fg" },
  { name: "danger-fill", value: "#C53030", use: "Failed bubble background", swatch: "bg-danger-fill" },
  { name: "success-soft", value: "rgb(34 197 94 / 0.15)", use: "Success chip, banner and callout fill", swatch: "bg-success-soft" },
  { name: "warning-soft", value: "rgb(251 146 60 / 0.15)", use: "Warning chip, banner and callout fill", swatch: "bg-warning-soft" },
  { name: "danger-soft", value: "rgb(239 68 68 / 0.15)", use: "Danger chip, banner and callout fill; destructive menu highlight", swatch: "bg-danger-soft" },
  // Platforms: fills and glyphs only, never text
  { name: "instagram", value: "#BE185D", use: "Instagram", swatch: "bg-instagram" },
  { name: "whatsapp", value: "#16A34A", use: "WhatsApp", swatch: "bg-whatsapp" },
  { name: "facebook", value: "#2563EB", use: "Facebook", swatch: "bg-facebook" },
  { name: "linkedin", value: "#1E40AF", use: "LinkedIn", swatch: "bg-linkedin" },
];

/** DESIGN_SYSTEM §1.9: four gradients, each with one job; the stops are tokens. */
export const gradientUtilities = [
  {
    name: "bg-brand-gradient",
    value: "linear-gradient(135deg, var(--color-brand-deep) 0%, var(--color-brand-strong) 100%)",
    use: "Primary buttons, outgoing bubbles, count badges; on-brand text",
  },
  {
    name: "bg-brand-gradient-decor",
    value: "linear-gradient(135deg, var(--color-brand-deep) 0%, var(--color-brand) 100%)",
    use: "Meters, progress fills, decorative icon tiles; never under text",
  },
  {
    name: "bg-shell-gradient",
    value: "linear-gradient(135deg, var(--color-shell-1) 0%, var(--color-shell-2) 100%)",
    use: "Logo tile and Upgrade only",
  },
  {
    name: "bg-glow-brand",
    value: "radial-gradient(120% 140% at 0% 0%, var(--color-brand-soft), transparent 60%)",
    use: "One per view at most: the marketing hero and the plan hero",
  },
] as const;

/**
 * shadcn's semantic variables (`:root` in globals.css) and the token each one points at
 * (DESIGN_SYSTEM §1.10). They stay inside components/ui; app code uses the tokens.
 */
export const shadcnAliases = [
  { alias: "background", token: "canvas" },
  { alias: "foreground", token: "fg" },
  { alias: "card", token: "panel" },
  { alias: "card-foreground", token: "fg" },
  { alias: "popover", token: "panel" },
  { alias: "popover-foreground", token: "fg" },
  { alias: "primary", token: "brand-strong" },
  { alias: "primary-foreground", token: "on-brand" },
  { alias: "secondary", token: "raised" },
  { alias: "secondary-foreground", token: "fg" },
  { alias: "muted", token: "field" },
  { alias: "muted-foreground", token: "fg-secondary" },
  { alias: "accent", token: "hover" },
  { alias: "accent-foreground", token: "fg" },
  { alias: "destructive", token: "danger" },
  { alias: "border", token: "line" },
  { alias: "input", token: "line" },
  { alias: "ring", token: "brand" },
] as const;

/** The two sizes Tailwind's scale lacks; each carries its line height. */
export const fontSizes = [
  { name: "text-2xs", size: "0.6875rem", lineHeight: "1rem", px: "11/16", use: "Status badges, chips, eyebrows, kbd" },
  { name: "text-md", size: "0.9375rem", lineHeight: "1.5rem", px: "15/24", use: "Reading: Ask answers and composer, legal prose" },
] as const;

// Type roles (DESIGN_SYSTEM §2.1). Weights 400, 500 and 600 only; tracking −0.025em at 24 px and
// up, +0.08em on eyebrows only; nothing under 11 px.
export const DISPLAY = "text-4xl font-semibold tracking-tight leading-[1.08] sm:text-5xl lg:text-6xl";
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
export const EYEBROW = "text-2xs font-semibold uppercase tracking-[0.08em] text-fg-secondary";
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
export const motionDurations = [
  { name: "duration-fast", variable: "--motion-fast", value: "120ms", use: "Hover, press, toggles, menus, popovers, tooltips; every exit" },
  { name: "duration-normal", variable: "--motion-normal", value: "150ms", use: "Content arriving in place: live message, inline reveals" },
  { name: "duration-slow", variable: "--motion-slow", value: "200ms", use: "Surfaces: dialogs, sheets, the drawer, panels, the suggestion bar" },
] as const;

export const easings = [
  { name: "ease-standard", value: "cubic-bezier(0.4, 0, 0.2, 1)", use: "State changes: colour, opacity, toggles" },
  { name: "ease-enter", value: "cubic-bezier(0, 0, 0.2, 1)", use: "Things arriving" },
  { name: "ease-exit", value: "cubic-bezier(0.4, 0, 1, 1)", use: "Things leaving" },
] as const;

/** Tailwind's breakpoints are kept; `wide` is the one addition. */
export const breakpoints = [
  { name: "md", value: "48rem", px: 768, use: "Top bar and drawer below it", custom: false },
  { name: "lg", value: "64rem", px: 1024, use: "Sidebar expands; three-column dashboards", custom: false },
  { name: "xl", value: "80rem", px: 1280, use: "Inbox details inline; settings two columns", custom: false },
  { name: "wide", value: "90rem", px: 1440, use: "Inbox details open by default; schedule rail inline", custom: true },
] as const;

/** Other utilities defined in globals.css. */
export const otherUtilities = [
  {
    name: "mask-fade-x",
    value: "mask-image: linear-gradient(to right, black calc(100% - 1rem), transparent)",
    use: "A row that scrolls sideways: its trailing 1rem fades; pair with pe-4",
  },
] as const;
