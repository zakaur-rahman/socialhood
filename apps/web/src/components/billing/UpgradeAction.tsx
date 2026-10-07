"use client";

import { Button } from "@/components/ui/button";
import { isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useUpgradeDialog } from "@/lib/api/provider";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * Upgrade beside an inline 402 message (a screen that opted out of the automatic dialog with
 * INLINE_PLAN_LIMITS): it opens the upgrade dialog for that limit. Nothing for other errors, or
 * for agents, who can't upgrade. A banner action: `secondary`, at the small inline size (24 px, 40
 * on touch) it had as a raw button.
 */
export function UpgradeAction({ error, className }: { error: unknown; className?: string }) {
  const upgrade = useUpgradeDialog();
  const workspace = useCurrentWorkspace();
  if (!isPlanLimitError(error) || workspace.role === "agent") return null;
  return (
    <Button
      type="button"
      variant="secondary"
      size="xs"
      onClick={() => upgrade.open(upgradeRequestFrom(error))}
      className={className}
    >
      Upgrade
    </Button>
  );
}
