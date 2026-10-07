import { ArrowDownRight, ArrowUpRight, ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { TONE_CLASS } from "@/lib/ui/tone";
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

/** UX-SCR-01: one metric in bg-panel rounded-xl p-4, the number in text-2xl semibold tabular-nums. */
export function MetricTile({ label, value, badge, hint, trend, href }: Props) {
  const body = (
    <>
      <p className="flex items-center justify-between gap-2 text-xs text-fg-secondary">
        <span>{label}</span>
        {href ? <ChevronRight className="size-4 shrink-0" aria-hidden /> : null}
      </p>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
        <span className="text-2xl font-semibold tabular-nums" data-testid="metric-value">
          {value}
        </span>
        {badge ? (
          <span
            data-testid="metric-badge"
            className={cn("rounded-full px-2 text-2xs leading-5 font-medium", TONE_CLASS[badge.tone])}
          >
            {badge.label}
          </span>
        ) : null}
        {trend ? <TrendChip trend={trend} /> : null}
      </p>
      {hint ? <p className="mt-1 text-xs text-fg-secondary">{hint}</p> : null}
    </>
  );
  const frame = "block h-full rounded-xl border border-line bg-panel p-4";
  if (href) {
    return (
      <Link
        href={href}
        data-testid="metric-tile"
        // An interactive card: the `line-strong` edge on hover (DESIGN_SYSTEM §1.2; a white 5% fill replaced the
        // panel fill and darkened the tile). Focus is the global outline (§8.3), not a halo.
        className={cn(frame, "hover:border-line-strong")}
      >
        {body}
      </Link>
    );
  }
  return (
    <div data-testid="metric-tile" className={frame}>
      {body}
    </div>
  );
}
