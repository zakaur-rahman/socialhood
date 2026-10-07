"use client";

import { useReturnFocus } from "@/components/agent/use-return-focus";

/**
 * useReturnFocus (UX-A11Y-02) for the automations dialogs that open without a trigger, plus a
 * fallback: a dialog reached by a link from another page (Home's checklist opens the gallery at
 * /automations/new; Ask's hand-off opens the draft there) remembers nothing on this page, so on
 * close focus goes to `fallback` (New automation) instead of falling to `<body>`.
 */
export function useReturnFocusOr(fallback?: () => HTMLElement | null) {
  const returnFocus = useReturnFocus();
  return {
    onOpenAutoFocus: returnFocus.onOpenAutoFocus,
    onCloseAutoFocus: (event: Event) => {
      returnFocus.onCloseAutoFocus(event);
      const active = document.activeElement;
      if (!active || active === document.body) fallback?.()?.focus();
    },
  };
}
