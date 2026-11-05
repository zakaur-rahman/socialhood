"use client";

import { useCallback, useSyncExternalStore } from "react";

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

function subscribeResize(onChange: () => void) {
  window.addEventListener("resize", onChange);
  return () => window.removeEventListener("resize", onChange);
}

const rootScale = () => parseFloat(getComputedStyle(document.documentElement).fontSize) / 16 || 1;

/**
 * A resizable pane's width in px, remembered per device (UI-078, the owner's request): the inbox
 * list and details, the Ask page's threads and the Ask panel. `limits` are written for a 16 px root
 * and scale with the root font size, because the text in a pane does; the server can't know that
 * size, so it renders them as written, and the browser corrects them after hydration. A stored value
 * outside the limits, or one that is not a number, falls back to the limits.
 * Returns the width, a setter (clamped), a reset to the fallback and the scaled limits.
 */
export function usePaneWidth(key: string, limits: PaneWidthLimits): [number, (width: number) => void, () => void, PaneWidthLimits] {
  const scale = useSyncExternalStore(subscribeResize, rootScale, () => 1);
  const min = Math.round(limits.min * scale);
  const max = Math.round(limits.max * scale);
  const fallback = Math.round(limits.fallback * scale);
  const [stored, setStored] = useStoredString(`socialhood:pane-width:${key}`, String(fallback));
  const parsed = Number.parseInt(stored, 10);
  const width = Number.isFinite(parsed) ? clampWidth(parsed, { min, max }) : fallback;
  const set = useCallback((next: number) => setStored(String(clampWidth(next, { min, max }))), [setStored, min, max]);
  const reset = useCallback(() => setStored(String(fallback)), [setStored, fallback]);
  return [width, set, reset, { fallback, min, max }];
}
