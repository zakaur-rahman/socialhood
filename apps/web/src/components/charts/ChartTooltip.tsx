import type { ReactNode } from "react";

import { FLOATING_SURFACE } from "@/components/ui/floating";
import { cn } from "@/lib/utils";

import { seriesStyle } from "./palette";

export type TooltipRow = {
  key: string;
  label: ReactNode;
  /** The value, as text; the strong element of the row. */
  value: string;
  /** Position in the palette. */
  color: number;
  /** A short second line: the point before, or why there is no value. */
  note?: ReactNode;
};

/**
 * The readout for a hovered or focused point: every series at that x, the value first (strong)
 * and the name after it, each keyed with a short stroke of the series colour. It enhances and
 * never gates: the same numbers are in the chart's table. It does not take the pointer.
 */
export function ChartTooltip({
  title,
  rows,
  style,
  className,
}: {
  title: ReactNode;
  rows: TooltipRow[];
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div
      role="presentation"
      data-testid="chart-tooltip"
      style={style}
      className={cn("pointer-events-none absolute z-20 min-w-36 max-w-64 px-3 py-2 text-xs", FLOATING_SURFACE, className)}
    >
      <p className="mb-1 font-medium text-fg-secondary">{title}</p>
      <ul className="m-0 list-none space-y-1 p-0">
        {rows.map((row) => (
          <li key={row.key} className="flex items-start gap-2">
            <span aria-hidden className={cn("mt-1.5 h-0.5 w-3 shrink-0 rounded-full", seriesStyle(row.color).bg)} />
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline justify-between gap-3">
                <span className="truncate text-fg-secondary">
                  <bdi>{row.label}</bdi>
                </span>
                <span className="font-semibold tabular-nums text-fg">{row.value}</span>
              </span>
              {row.note ? <span className="block text-fg-secondary">{row.note}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
