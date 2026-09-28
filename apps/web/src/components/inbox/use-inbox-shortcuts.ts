"use client";

import { useEffect, useRef } from "react";

export type ShortcutActions = {
  /** Open the next (j) or previous (k) conversation. */
  move: (step: 1 | -1) => void;
  focusSearch: () => void;
  archive: () => void;
  markUnread: () => void;
  escape: () => void;
};

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

/**
 * FR-INB-12: j/k next and previous conversation, / search, e archive, u mark unread, Esc close
 * panels. Letters are ignored while typing; Esc is left to popovers and dialogs that handle it.
 */
export function useInboxShortcuts(actions: ShortcutActions, enabled = true): void {
  const ref = useRef(actions);
  useEffect(() => {
    ref.current = actions;
  });

  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      if (event.key === "Escape") {
        ref.current.escape();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey || isEditable(event.target)) return;
      // A dialog or menu is open: its own keys win.
      if (document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"]')) return;
      switch (event.key) {
        case "j":
          ref.current.move(1);
          break;
        case "k":
          ref.current.move(-1);
          break;
        case "/":
          ref.current.focusSearch();
          break;
        case "e":
          ref.current.archive();
          break;
        case "u":
          ref.current.markUnread();
          break;
        default:
          return;
      }
      event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
