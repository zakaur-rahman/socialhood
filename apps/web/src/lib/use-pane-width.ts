"use client";

import { useCallback } from "react";

import { useStoredString } from "@/lib/use-browser-state";

export type PaneWidthLimits = {
  /** The width before anyone resizes the pane, and what a double-click on its handle goes back to. */
  fallback: number;
  min: number;
  max: number;
};

export function clampWidth(value: number, { min, max }: Pick<PaneWidthLimits, "min" | "max">): number {
  return Math.round(Math.min(max, Math.max(min, value)));
}

/**
 * A resizable pane's width in px, remembered per device (UI-078, the owner's request): the inbox
 * list and details, the Ask page's threads and the Ask panel. A stored value outside the limits,
 * or one that is not a number, falls back to the limits; the server render uses `fallback`.
 * Returns the width, a setter (clamped) and a reset to the fallback.
 */
export function usePaneWidth(key: string, limits: PaneWidthLimits): [number, (width: number) => void, () => void] {
  const [stored, setStored] = useStoredString(`socialhood:pane-width:${key}`, String(limits.fallback));
  const parsed = Number.parseInt(stored, 10);
  const width = Number.isFinite(parsed) ? clampWidth(parsed, limits) : limits.fallback;
  const { min, max, fallback } = limits;
  const set = useCallback((next: number) => setStored(String(clampWidth(next, { min, max }))), [setStored, min, max]);
  const reset = useCallback(() => setStored(String(fallback)), [setStored, fallback]);
  return [width, set, reset];
}
