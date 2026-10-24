"use client";

import { creditsUpgrade } from "@/components/billing/upgrade-requests";
import { CardInset } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useUpgradeDialog } from "@/lib/api/provider";
import { cn } from "@/lib/utils";

import { creditsUsedText, type UsageView } from "./usage";

/**
 * FR-AI-05: the AI credits meter above the account card (Meter, `role="meter"`; it warns from
 * 80 % and turns danger at 100 %, the same thresholds as usage.ts). The rules for who sees it and
 * when it offers Upgrade are in usage.ts. Collapsed, the Meter's ring with a tooltip. Both forms stay
 * mounted: the card fades and its row collapses (grid rows 1fr to 0fr) as the ring's grows, so the
 * swap eases instead of popping; the hidden one is inert and out of the accessibility tree.
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

  let card: React.ReactNode = null;
  let ring: React.ReactNode = null;
  let text = "";
  if (view.kind === "loading") {
    card = (
      <CardInset padding="compact" className="w-full min-w-53.5" aria-hidden data-testid="usage-loading">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-2.5 h-1.5 w-full" />
        <Skeleton className="mt-2 h-3 w-24" />
      </CardInset>
    );
  } else {
    const { used, limit, upgrade } = view;
    text = creditsUsedText(used, limit);
    ring = <Meter variant="ring" label="AI credits" value={used} max={limit} valueText={text} />;
    card = (
      <CardInset padding="compact" className="w-full min-w-53.5">
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

  const layer = (shown: boolean) =>
    cn(
      "grid motion-safe:group-data-[ready=true]/sb:transition-[grid-template-rows,opacity] motion-safe:group-data-[ready=true]/sb:duration-slow motion-safe:group-data-[ready=true]/sb:ease-standard",
      shown ? "grid-rows-[1fr] opacity-100" : "pointer-events-none grid-rows-[0fr] opacity-0",
    );

  return (
    <div className="relative mt-2 w-full">
      <div className={layer(!collapsed)} inert={collapsed} aria-hidden={collapsed}>
        <div className="min-h-0 overflow-hidden">{card}</div>
      </div>
      {ring ? (
        <div className={layer(collapsed)} inert={!collapsed} aria-hidden={!collapsed}>
          <div className="min-h-0 overflow-hidden pl-0.5">
            <Tooltip>
              <TooltipTrigger asChild>{ring}</TooltipTrigger>
              {collapsed ? <TooltipContent side="right">AI credits: {text}</TooltipContent> : null}
            </Tooltip>
          </div>
        </div>
      ) : null}
    </div>
  );
}
