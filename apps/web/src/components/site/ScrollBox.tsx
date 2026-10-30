import type { ReactNode } from "react";

/**
 * A wide table's sideways scroll box (C-159): on a phone the legal tables keep a readable width and
 * scroll inside this box, so it is a named region keyboard users can reach and scroll with the arrow
 * keys (WCAG 2.1.1, axe `scrollable-region-focusable`). The site's focus ring marks it.
 */
export function ScrollBox({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}
