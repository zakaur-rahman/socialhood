import { cn } from "@/lib/utils";

/**
 * The selection bar (DESIGN_SYSTEM §5, §8.3; UI-ISS-053): 2 px `brand` on the leading edge, inset
 * 8 px from the top and bottom, rounded. One implementation for the sidebar's active row and Ask's
 * selected thread. It is the row's `::before`, so the row is `relative`.
 */
export const SELECTION_BAR =
  "before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-brand";

/** A selected row or nav item (§8.3): `raised`, full-strength text and the selection bar. */
export const SELECTED_ROW = cn("bg-raised text-fg hover:bg-raised", SELECTION_BAR);

/**
 * A sidebar row (UX-SH-01): nav links, Notifications, Help and Collapse. 36 px tall (40 px for
 * touch), 14 px text; the active row is raised, with the selection bar on its left edge. The
 * rows are left-aligned with the same padding collapsed or not, so the icon column (64 px card:
 * centred at 32 px) never moves while the card resizes; collapsed is the expanded row clipped.
 */
export function sidebarRowClass({ active = false }: { active?: boolean } = {}): string {
  return cn(
    // text-left: a row that is a <button> (Notifications) would centre its stretched label.
    "relative flex h-9 w-full items-center gap-3 overflow-hidden rounded-lg px-3.5 text-left text-sm font-medium whitespace-nowrap text-fg-secondary pointer-coarse:h-10",
    // Colours only: transition-colors includes outline-color, which faded the focus outline in from
    // grey (A11Y-023); the outline must appear in brand at once (DESIGN_SYSTEM §7.3).
    "hover:bg-hover hover:text-fg motion-safe:transition-[color,background-color]",
    active && SELECTED_ROW,
  );
}

/**
 * Fades (and slides a little) the text that only the expanded sidebar shows. Leaving is quick, so
 * the text is gone before the card is narrow; arriving waits for the card to open, so the text
 * never wraps or squashes. The transition exists only under `motion-safe` and once the sidebar has
 * mounted (the nav's `data-ready`), so reduced motion and the first paint are instant. Pair it with
 * `aria-hidden` (or `inert`) while hidden.
 */
export function sidebarFadeClass(visible: boolean, { slide = true }: { slide?: boolean } = {}): string {
  return cn(
    "motion-safe:group-data-[ready=true]/sb:transition-[opacity,translate] motion-safe:group-data-[ready=true]/sb:ease-standard",
    visible
      ? "opacity-100 motion-safe:group-data-[ready=true]/sb:delay-(--motion-fast) motion-safe:group-data-[ready=true]/sb:duration-normal"
      : cn("pointer-events-none opacity-0 motion-safe:group-data-[ready=true]/sb:duration-fast", slide && "-translate-x-1"),
  );
}

/** A row's label: fades with the sidebar, never wraps, and ellipsises only once it has room. */
export function sidebarLabelClass(collapsed: boolean): string {
  return cn("min-w-0 flex-1 overflow-hidden whitespace-nowrap", collapsed ? "text-clip" : "text-ellipsis", sidebarFadeClass(!collapsed));
}

/** Row icons: 18 px, brand-coloured on the active row. */
export function sidebarIconClass(active = false): string {
  return cn("size-4.5 shrink-0", active && "text-brand-fg");
}

/** A keyboard shortcut hint ("Ctrl K", "⌘["): 11 px (`text-2xs`, the type floor; DESIGN_SYSTEM §2.1). */
export const KBD_CLASS =
  "shrink-0 rounded-sm border border-line bg-hover px-1 font-sans text-2xs font-medium text-fg-secondary";
