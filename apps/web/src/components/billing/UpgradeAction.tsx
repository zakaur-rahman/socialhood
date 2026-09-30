"use client";

import { isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useUpgradeDialog } from "@/lib/api/provider";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * Upgrade beside an inline 402 message (a screen that opted out of the automatic dialog with
 * INLINE_PLAN_LIMITS): it opens the upgrade dialog for that limit. Nothing for other errors, or
 * for agents, who can't upgrade.
 */
export function UpgradeAction({ error, className }: { error: unknown; className?: string }) {
  const upgrade = useUpgradeDialog();
  const workspace = useCurrentWorkspace();
  if (!isPlanLimitError(error) || workspace.role === "agent") return null;
  return (
    <button
      type="button"
      onClick={() => upgrade.open(upgradeRequestFrom(error))}
      className={cn(
        "inline-flex min-h-10 shrink-0 items-center rounded-md bg-white/10 px-2.5 text-xs font-medium text-fg hover:bg-white/15 md:min-h-6",
        className,
      )}
    >
      Upgrade
    </button>
  );
}
