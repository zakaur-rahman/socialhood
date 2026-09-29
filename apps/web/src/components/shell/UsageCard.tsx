"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { BILLING_HREF } from "./nav";
import { creditsUsedText, type UsageTone, type UsageView } from "./usage";

const BAR: Record<UsageTone, string> = { normal: "bg-brand", warning: "bg-warning", danger: "bg-danger" };
const RING: Record<UsageTone, string> = { normal: "text-brand", warning: "text-warning", danger: "text-danger" };
const FIGURE: Record<UsageTone, string> = {
  normal: "text-fg-secondary",
  warning: "text-warning",
  danger: "text-danger-fg",
};

/**
 * FR-AI-05: the AI credits meter above the account card. The rules for who sees it and when it
 * offers Upgrade are in usage.ts. Collapsed, a small ring with a tooltip.
 */
export function UsageCard({
  view,
  collapsed,
  slug,
  onNavigate,
}: {
  view: UsageView;
  collapsed: boolean;
  slug: string;
  onNavigate?: () => void;
}) {
  if (view.kind === "hidden") return null;
  if (view.kind === "loading") {
    if (collapsed) return null;
    return (
      <div className="relative mt-2 w-full rounded-lg border border-line p-3" aria-hidden data-testid="usage-loading">
        <Skeleton className="h-3 w-20 motion-reduce:animate-none" />
        <Skeleton className="mt-2.5 h-1.5 w-full motion-reduce:animate-none" />
        <Skeleton className="mt-2 h-3 w-24 motion-reduce:animate-none" />
      </div>
    );
  }

  const { used, limit, percent, tone, upgrade } = view;
  const text = creditsUsedText(used, limit);

  if (collapsed) {
    const radius = 11;
    const circumference = 2 * Math.PI * radius;
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div role="img" aria-label={`AI credits: ${text}`} className="relative mt-2 grid size-10 place-items-center">
            <svg viewBox="0 0 28 28" className="size-7 -rotate-90" aria-hidden>
              <circle cx="14" cy="14" r={radius} fill="none" strokeWidth="3" className="stroke-white/10" />
              <circle
                cx="14"
                cy="14"
                r={radius}
                fill="none"
                strokeWidth="3"
                strokeLinecap="round"
                stroke="currentColor"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - percent / 100)}
                className={RING[tone]}
              />
            </svg>
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">AI credits: {text}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <div className="relative mt-2 w-full rounded-lg border border-line bg-white/[0.03] p-3">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-fg">AI credits</span>
        <span className={cn("font-medium tabular-nums", FIGURE[tone])}>{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="AI credits used"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={Math.min(used, limit)}
        aria-valuetext={text}
        data-tone={tone}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"
      >
        <div
          className={cn("h-full rounded-full motion-safe:transition-[width] motion-safe:duration-500", BAR[tone])}
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className={cn("mt-2 flex items-center justify-between gap-2", upgrade && "min-h-6")}>
        <p className="min-w-0 truncate text-xs text-fg-secondary tabular-nums">{text}</p>
        {upgrade ? (
          <Link
            href={BILLING_HREF(slug)}
            onClick={onNavigate}
            className="bg-shell-gradient flex h-6 shrink-0 items-center rounded-md px-2.5 text-xs font-medium text-white hover:brightness-110 motion-safe:transition-[filter] pointer-coarse:h-8"
          >
            Upgrade
          </Link>
        ) : null}
      </div>
    </div>
  );
}
