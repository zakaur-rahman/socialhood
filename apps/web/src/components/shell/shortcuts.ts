"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { modifierKey } from "@/lib/agent/format";

const noSubscribe = () => () => {};

/** "Ctrl" or "⌘", read after hydration (the server assumes Ctrl). */
export function useModifierKey(): "Ctrl" | "⌘" {
  return useSyncExternalStore(
    noSubscribe,
    () => modifierKey(typeof navigator === "undefined" ? undefined : navigator.platform || navigator.userAgent),
    () => "Ctrl",
  );
}

/** A shortcut hint: "⌘K" on a Mac, "Ctrl K" elsewhere. */
export function shortcutHint(modifier: "Ctrl" | "⌘", key: string): string {
  return modifier === "⌘" ? `⌘${key}` : `Ctrl ${key}`;
}

/** For aria-keyshortcuts on the collapse button. */
export const COLLAPSE_SHORTCUT_ARIA = "Control+[ Meta+[";

type KeyInfo = Pick<KeyboardEvent, "key" | "code" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">;

/** Ctrl+[ (⌘[ on a Mac). The physical key counts too, for layouts where [ needs AltGr. */
export function isCollapseShortcut(event: KeyInfo): boolean {
  return (
    (event.ctrlKey || event.metaKey) &&
    !event.altKey &&
    !event.shiftKey &&
    (event.key === "[" || event.code === "BracketLeft")
  );
}

/** Typing in a field, a text area or rich text: shortcuts without their own field stay out. */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  if (target instanceof HTMLElement && target.isContentEditable) return true;
  if (target.closest('[contenteditable]:not([contenteditable="false"])')) return true;
  return target.matches("input, textarea, select");
}

function dialogOpen(): boolean {
  return document.querySelector('[role="dialog"], [role="alertdialog"]') !== null;
}

/**
 * Ctrl/⌘ [ collapses or expands the sidebar. It is ignored while typing and while a dialog is
 * open (the Ask panel, a sheet, a confirmation), and does nothing when there is no toggle.
 */
export function useCollapseShortcut(onToggle: (() => void) | undefined): void {
  const ref = useRef(onToggle);
  useEffect(() => {
    ref.current = onToggle;
  });
  const enabled = Boolean(onToggle);

  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.repeat || !isCollapseShortcut(event)) return;
      if (isTyping(event.target) || dialogOpen()) return;
      event.preventDefault();
      ref.current?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
