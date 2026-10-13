"use client";

import { creditsUpgrade } from "@/components/billing/upgrade-requests";
import { CardInset } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useUpgradeDialog } from "@/lib/api/provider";

import { creditsUsedText, type UsageView } from "./usage";

/**
 * FR-AI-05: the AI credits meter above the account card (Meter, `role="meter"`; it warns from
 * 80 % and turns danger at 100 %, the same thresholds as usage.ts). The rules for who sees it and
 * when it offers Upgrade are in usage.ts. Collapsed, the Meter's ring with a tooltip.
 */
export function UsageCard({
  view,
  collapsed,
}: {
  view: UsageView;
  collapsed: boolean;
}) {
  const upgradeDialog = useUpgradeDialog();
  if (view.kind === "hidden") return null;
  if (view.kind === "loading") {
    if (collapsed) return null;
    return (
      <CardInset padding="compact" className="relative mt-2 w-full" aria-hidden data-testid="usage-loading">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-2.5 h-1.5 w-full" />
        <Skeleton className="mt-2 h-3 w-24" />
      </CardInset>
    );
  }

  const { used, limit, upgrade } = view;
  const text = creditsUsedText(used, limit);

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Meter variant="ring" label="AI credits" value={used} max={limit} valueText={text} className="mt-2" />
        </TooltipTrigger>
        <TooltipContent side="right">AI credits: {text}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <CardInset padding="compact" className="relative mt-2 w-full">
      <Meter label="AI credits" value={used} max={limit} valueText={text} />
      {upgrade ? (
        <div className="mt-2 flex justify-end">
          {/* Opens the upgrade dialog like every Upgrade (UI-063); the drawer stays under it, so
              closing the dialog returns focus here. */}
          <button
            type="button"
            onClick={() => upgradeDialog.open(creditsUpgrade(used, limit))}
            className="bg-shell-gradient flex h-6 shrink-0 items-center rounded-md px-2.5 text-xs font-medium text-on-brand hover:brightness-110 motion-safe:transition-[filter] pointer-coarse:h-10"
          >
            Upgrade
          </button>
        </div>
      ) : null}
    </CardInset>
  );
}
