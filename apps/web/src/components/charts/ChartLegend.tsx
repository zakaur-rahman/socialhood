import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { seriesStyle } from "./palette";

export type LegendItem = {
  key: string;
  label: ReactNode;
  /** Position in the palette (`seriesStyle`). */
  color: number;
  /** A line key for line charts, a square for bars and areas. */
  shape?: "line" | "box";
};

/**
 * The legend: one row of keys for two or more series (a single series is named by the chart's
 * title and needs none). The key mirrors the mark, the text stays in the ordinary ink, and the
 * colour never carries the identity alone: the label is always there.
 */
export function ChartLegend({ items, className, label = "Legend" }: { items: LegendItem[]; className?: string; label?: string }) {
  if (items.length < 2) return null;
  return (
    <ul aria-label={label} className={cn("m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-fg-secondary", className)} data-testid="chart-legend">
      {items.map((item) => (
        <li key={item.key} className="flex min-w-0 items-center gap-1.5">
          <span
            aria-hidden
            className={cn("shrink-0 rounded-full", item.shape === "box" ? "size-2.5 rounded-sm" : "h-0.5 w-3.5", seriesStyle(item.color).bg)}
          />
          <span className="min-w-0 truncate">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}
