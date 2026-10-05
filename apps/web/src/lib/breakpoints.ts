import { breakpoints } from "@/styles/tokens";

/**
 * The layout breakpoints for JS (DESIGN_SYSTEM §9, UI-ISS-059), in px: the same numbers as CSS's
 * `md:`, `lg:`, `xl:` and `wide:` (Tailwind's theme plus `--breakpoint-wide` in globals.css),
 * read from the token mirror (styles/tokens.ts). Media queries in components come from here; no
 * component writes a width.
 *
 * - `md` 768: the phone top bar and drawer below it; one inbox pane; the schedule agenda.
 * - `lg` 1024: the sidebar expands (outside the inbox).
 * - `xl` 1280: the sidebar expands in the inbox; inbox details inline.
 * - `wide` 1440: inbox details open by default; the schedule rail inline.
 */
export type Breakpoint = (typeof breakpoints)[number]["name"];

export const BREAKPOINTS = Object.fromEntries(breakpoints.map((bp) => [bp.name, bp.px])) as Record<Breakpoint, number>;

/** "This breakpoint and wider", for `useMediaQuery`: `(min-width: 768px)`. */
export function minWidth(breakpoint: Breakpoint): string {
  return `(min-width: ${BREAKPOINTS[breakpoint]}px)`;
}
