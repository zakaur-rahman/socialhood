import { ArrowDownRight, ArrowUpRight, ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { Trend } from "./format";

const TREND_TONE = { good: "text-success", bad: "text-danger-fg", neutral: "text-fg-secondary" } as const;

/** The change from the period before, coloured when it is good or bad news. */
export function TrendChip({ trend }: { trend: Trend }) {
  const tone = trend.good === null ? "neutral" : trend.good ? "good" : "bad";
  const Icon = trend.direction === "up" ? ArrowUpRight : trend.direction === "down" ? ArrowDownRight : null;
  return (
    <span data-testid="trend" data-tone={tone} className={cn("inline-flex items-center gap-0.5 text-xs font-medium", TREND_TONE[tone])}>
      {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
      <span aria-hidden>{trend.text}</span>
      <span className="sr-only">{trend.words}</span>
    </span>
  );
}

type Props = {
  label: string;
  value: string;
  /** A rule-based label beside the number (Attention, Fast; components/home/rules.ts). */
  badge?: { label: string; tone: "warning" | "success" } | null;
  /** One line under the number: what it counts, or how to get a first value. */
  hint?: ReactNode;
  trend?: Trend | null;
  /** The whole tile links here (Needs reply opens that inbox view). */
  href?: Route;
};

/** UX-SCR-01: one metric on a Card, the number in text-2xl semibold tabular-nums. */
export function MetricTile({ label, value, badge, hint, trend, href }: Props) {
  const body = (
    <>
      <p className="flex items-center justify-between gap-2 text-xs text-fg-secondary">
        <span>{label}</span>
        {href ? <ChevronRight className="size-4 shrink-0" aria-hidden /> : null}
      </p>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
        {/* While another period loads the old number stays, in the secondary colour: opacity on text
            would break its contrast. HomeScreen's overview group is `aria-busy` then. */}
        <span
          className="text-2xl font-semibold tabular-nums group-aria-busy/overview:text-fg-secondary"
          data-testid="metric-value"
        >
          {value}
        </span>
        {badge ? (
          <Badge data-testid="metric-badge" tone={badge.tone}>
            {badge.label}
          </Badge>
        ) : null}
        {trend ? <TrendChip trend={trend} /> : null}
      </p>
      {hint ? <p className="mt-1 text-xs text-fg-secondary">{hint}</p> : null}
    </>
  );
  if (href) {
    return (
      // An interactive card: the `line-strong` edge on hover (DESIGN_SYSTEM §1.2). Focus is the global
      // outline (§8.3), not a halo.
      <Card asChild className="block h-full hover:border-line-strong">
        <Link href={href} data-testid="metric-tile">
          {body}
        </Link>
      </Card>
    );
  }
  return (
    <Card data-testid="metric-tile" className="h-full">
      {body}
    </Card>
  );
}
