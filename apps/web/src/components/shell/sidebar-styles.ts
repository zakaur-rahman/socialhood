import { cn } from "@/lib/utils";

/**
 * A sidebar row (UX-SH-01): nav links, Notifications, Help and Collapse. 36 px tall (40 px for
 * touch), 14 px text; the active row is raised, with a 2 px brand bar on its left edge. Collapsed,
 * a 40 px icon button.
 */
export function sidebarRowClass({ active = false, collapsed }: { active?: boolean; collapsed: boolean }): string {
  return cn(
    "relative flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-fg-secondary pointer-coarse:h-10",
    "hover:bg-white/5 hover:text-fg motion-safe:transition-colors",
    active &&
      "bg-raised text-fg hover:bg-raised before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-brand",
    collapsed && "size-10 justify-center gap-0 px-0 pointer-coarse:size-10",
  );
}

/** Row icons: 18 px, brand-coloured on the active row. */
export function sidebarIconClass(active = false): string {
  return cn("size-[18px] shrink-0", active && "text-brand-fg");
}

/** A keyboard shortcut hint ("Ctrl K", "⌘["). */
export const KBD_CLASS =
  "shrink-0 rounded border border-line bg-white/5 px-1 font-sans text-[10px] leading-4 font-medium text-fg-secondary";
