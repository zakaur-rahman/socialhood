/**
 * The palette from spec §4.2, as data: the /dev/tokens page renders it and a test checks
 * globals.css against it, so the CSS and the spec cannot drift apart silently.
 */
/** `swatch` is a literal class so Tailwind emits the variable (it only keeps theme values in use). */
export type ColorToken = { name: string; value: string; use: string; swatch: string };

export const colorTokens: ColorToken[] = [
  { name: "canvas", value: "#000000", use: "App and thread background", swatch: "bg-canvas" },
  { name: "panel", value: "#1F1F1F", use: "Sidebar card, list pane, headers, composer bar, popovers", swatch: "bg-panel" },
  { name: "field", value: "#1D1D1D", use: "Inputs, incoming bubbles, segmented track", swatch: "bg-field" },
  { name: "raised", value: "#2A2A2A", use: "Selected row, active segment, focused input, secondary button", swatch: "bg-raised" },
  { name: "raised-hover", value: "#333333", use: "Hover on raised surfaces", swatch: "bg-raised-hover" },
  { name: "line", value: "rgb(255 255 255 / 0.10)", use: "Borders", swatch: "bg-line" },
  { name: "line-subtle", value: "rgb(255 255 255 / 0.05)", use: "Faint borders", swatch: "bg-line-subtle" },
  { name: "line-strong", value: "rgb(255 255 255 / 0.20)", use: "Emphasised borders", swatch: "bg-line-strong" },
  { name: "fg", value: "#FFFFFF", use: "Primary text", swatch: "bg-fg" },
  { name: "fg-secondary", value: "#9B9CA0", use: "Secondary and meta text, timestamps", swatch: "bg-fg-secondary" },
  { name: "fg-disabled", value: "#71717A", use: "Disabled controls and placeholders only", swatch: "bg-fg-disabled" },
  { name: "brand", value: "#567FF8", use: "Fills, borders, dots, focus ring", swatch: "bg-brand" },
  { name: "brand-deep", value: "#20338A", use: "Gradient start", swatch: "bg-brand-deep" },
  { name: "brand-fg", value: "#9DB5FF", use: "Brand-coloured text and icons on dark", swatch: "bg-brand-fg" },
  { name: "brand-soft", value: "rgb(86 127 248 / 0.15)", use: "Soft brand fills", swatch: "bg-brand-soft" },
  { name: "brand-line", value: "rgb(86 127 248 / 0.35)", use: "Brand borders", swatch: "bg-brand-line" },
  { name: "shell-1", value: "#3352CC", use: "Logo tile and upgrade button", swatch: "bg-shell-1" },
  { name: "shell-2", value: "#1C2D70", use: "Logo tile and upgrade button", swatch: "bg-shell-2" },
  { name: "success", value: "#22C55E", use: "Success", swatch: "bg-success" },
  { name: "warning", value: "#FB923C", use: "Warning", swatch: "bg-warning" },
  { name: "danger", value: "#EF4444", use: "Danger icons and borders", swatch: "bg-danger" },
  { name: "danger-fg", value: "#FCA5A5", use: "Danger text on dark", swatch: "bg-danger-fg" },
  { name: "danger-fill", value: "#C53030", use: "Failed bubble background", swatch: "bg-danger-fill" },
  { name: "instagram", value: "#BE185D", use: "Instagram", swatch: "bg-instagram" },
  { name: "whatsapp", value: "#16A34A", use: "WhatsApp", swatch: "bg-whatsapp" },
  { name: "facebook", value: "#2563EB", use: "Facebook", swatch: "bg-facebook" },
  { name: "linkedin", value: "#1E40AF", use: "LinkedIn", swatch: "bg-linkedin" },
];

export const gradientUtilities = [
  { name: "bg-brand-gradient", value: "linear-gradient(135deg, #20338A 0%, #4467E6 100%)" },
  { name: "bg-brand-gradient-decor", value: "linear-gradient(135deg, #20338A 0%, #567FF8 100%)" },
  { name: "bg-shell-gradient", value: "linear-gradient(135deg, #3352CC 0%, #1C2D70 100%)" },
] as const;

export const typeRoles = [
  { role: "Page title", className: "text-2xl font-semibold tracking-tight" },
  { role: "Pane title", className: "text-xl font-semibold" },
  { role: "Section title", className: "text-base font-semibold" },
  { role: "Body", className: "text-sm" },
  { role: "Meta", className: "text-xs text-fg-secondary" },
  { role: "Micro label", className: "text-[11px] uppercase tracking-[0.08em] font-semibold text-fg-secondary" },
  { role: "Numbers", className: "tabular-nums" },
] as const;
