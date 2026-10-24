"use client";

import { useState } from "react";

/**
 * A sidebar tooltip that only shows while the sidebar is collapsed. The tooltip stays mounted in
 * both states (remounting the row would cut its fade), so Radix keeps its own "open" while the
 * sidebar is expanded and the pointer passes over rows; without this, every row hovered before
 * collapsing popped its tooltip the moment the content appeared (owner, 2026-10-25). Any change
 * of state forgets the old "open", so only a hover after collapsing shows one.
 */
export function useCollapsedTooltip(enabled: boolean) {
  const [open, setOpen] = useState(false);
  const [wasEnabled, setWasEnabled] = useState(enabled);
  if (enabled !== wasEnabled) {
    // Adjusting state on a prop change during render (React's documented pattern, no effect).
    setWasEnabled(enabled);
    setOpen(false);
  }
  return { open: enabled && open, onOpenChange: (next: boolean) => setOpen(enabled && next) };
}
