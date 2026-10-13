"use client";

import { useEffect, useRef } from "react";

import { SINGLE_KEY_SHORTCUTS_KEY } from "@/lib/inbox/shortcuts";
import { useStoredFlag } from "@/lib/use-browser-state";

export type ShortcutActions = {
  /** Open the next (j) or previous (k) conversation. */
  move: (step: 1 | -1) => void;
  focusSearch: () => void;
  archive: () => void;
  markUnread: () => void;
  /** "?" opens the Keyboard shortcuts dialog. */
  help: () => void;
  escape: () => void;
};

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

/** The per-device "Single-key shortcuts" switch (D-14): on until the user turns it off. */
export function useSingleKeyShortcuts(): [boolean, (on: boolean) => void] {
  return useStoredFlag(SINGLE_KEY_SHORTCUTS_KEY, true);
}

/**
 * FR-INB-12: j/k next and previous conversation, / search, e archive, u mark unread, ? the shortcut
 * list, Esc close panels. Letters are ignored while typing; Esc is left to popovers and dialogs that
 * handle it. With `singleKeys` off (D-14) every character key does nothing; Esc, which is not a
 * character key, and shortcuts with a modifier are not affected.
 */
export function useInboxShortcuts(actions: ShortcutActions, singleKeys = true): void {
  const ref = useRef(actions);
  useEffect(() => {
    ref.current = actions;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      if (event.key === "Escape") {
        ref.current.escape();
        return;
      }
      if (!singleKeys) return;
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
        case "?":
          ref.current.help();
          break;
        default:
          return;
      }
      event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [singleKeys]);
}
