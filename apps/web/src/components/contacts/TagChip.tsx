import type { ReactNode } from "react";

import type { TagRef } from "@/lib/api/types";
import { identityAt } from "@/lib/ui/identity";
import { cn } from "@/lib/utils";

/**
 * A tag: its name beside a dot in the tag's identity colour (GR-02 stores an index into the
 * identity palette), so a tag never wears a status colour. `action` is a small button inside the
 * chip, like a remove control.
 */
export function TagChip({ tag, action, className }: { tag: Pick<TagRef, "name" | "color">; action?: ReactNode; className?: string }) {
  return (
    <span
      data-testid="tag-chip"
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-fg",
        className,
      )}
    >
      <span aria-hidden className={cn("size-2 shrink-0 rounded-full", identityAt(tag.color).dot)} />
      <span className="truncate">{tag.name}</span>
      {action}
    </span>
  );
}
