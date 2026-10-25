"use client";

import { usePathname } from "next/navigation";

/** The address that was asked for, in small mono type; nothing renders until the path is known. */
export function RequestedPath() {
  const path = usePathname();
  if (!path) return null;
  return (
    <p className="max-w-full truncate rounded-md bg-raised px-2 py-1 font-mono text-xs text-fg-secondary" data-testid="requested-path" title={path}>
      {path}
    </p>
  );
}
