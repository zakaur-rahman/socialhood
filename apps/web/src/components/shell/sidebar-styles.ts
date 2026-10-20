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
 * touch), 14 px text; the active row is raised, with the selection bar on its left edge.
 * Collapsed, a 40 px icon button.
 */
export function sidebarRowClass({ active = false, collapsed }: { active?: boolean; collapsed: boolean }): string {
  return cn(
    "relative flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-fg-secondary pointer-coarse:h-10",
    // Colours only: transition-colors includes outline-color, which faded the focus outline in from
    // grey (A11Y-023); the outline must appear in brand at once (DESIGN_SYSTEM §7.3).
    "hover:bg-hover hover:text-fg motion-safe:transition-[color,background-color]",
    active && SELECTED_ROW,
    collapsed && "size-10 justify-center gap-0 px-0 pointer-coarse:size-10",
  );
}

/** Row icons: 18 px, brand-coloured on the active row. */
export function sidebarIconClass(active = false): string {
  return cn("size-4.5 shrink-0", active && "text-brand-fg");
}

/** A keyboard shortcut hint ("Ctrl K", "⌘["): 11 px (`text-2xs`, the type floor; DESIGN_SYSTEM §2.1). */
export const KBD_CLASS =
  "shrink-0 rounded-sm border border-line bg-hover px-1 font-sans text-2xs font-medium text-fg-secondary";
