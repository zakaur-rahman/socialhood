"use client";

import { useEffect, useRef } from "react";

/** The shortcut's key with Ctrl (Windows, Linux) or ⌘ (Mac). Inbox keys are unmodified letters. */
export const ASK_SHORTCUT_KEY = "k";
/** For aria-keyshortcuts on the buttons that open the panel. */
export const ASK_SHORTCUT_ARIA = "Control+K Meta+K";

export function isAskShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">): boolean {
  return (
    event.key.toLowerCase() === ASK_SHORTCUT_KEY && (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey
  );
}

/**
 * Ctrl/⌘ K anywhere in the app (FR-AGT-01). It works while typing, since it has a modifier, and
 * leaves other dialogs alone: with one open, their keys win.
 */
export function useAskShortcut(onShortcut: () => void, enabled = true): void {
  const ref = useRef(onShortcut);
  useEffect(() => {
    ref.current = onShortcut;
  });

  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.repeat || !isAskShortcut(event)) return;
      event.preventDefault();
      ref.current();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
