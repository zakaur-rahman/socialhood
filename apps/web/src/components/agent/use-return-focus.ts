"use client";

import { useRef } from "react";

/**
 * UX-A11Y-02 for sheets opened without a Radix trigger (a shortcut, a row, a store flag): Radix
 * would return focus to its trigger, and there is none, so this remembers what had focus when the
 * sheet opened and returns focus there when it closes.
 */
export function useReturnFocus() {
  const target = useRef<HTMLElement | null>(null);
  return {
    onOpenAutoFocus: () => {
      target.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    },
    onCloseAutoFocus: (event: Event) => {
      event.preventDefault();
      const element = target.current;
      target.current = null;
      if (element?.isConnected) element.focus();
    },
  };
}
