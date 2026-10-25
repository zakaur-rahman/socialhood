"use client";

import { useId, useState } from "react";

import { cn } from "@/lib/utils";

import { ChartLegend } from "./ChartLegend";
import { ChartTable } from "./ChartTable";
import { ChartTooltip } from "./ChartTooltip";
import { seriesStyle } from "./palette";
import { nearestIndex, niceScale, runsOf, xPercent, yPercent } from "./scale";

export type LineSeries = {
  key: string;
  label: string;
  /** Position in the palette: the entity's, not the series' place in this chart. */
  color: number;
  /** One value per x; null is a gap (nothing is drawn through it or put in its place). */
  values: (number | null | undefined)[];
};

export type LinePoint = {
  key: string;
  /** The axis label ("21 Sep"). */
  label: string;
  /** The tooltip and table heading; defaults to `label`. */
  title?: string;
};

type Props = {
  /** The chart's name, for screen readers and the table. */
  label: string;
  points: LinePoint[];
  series: LineSeries[];
  /** A value as text, for the tooltip and the table. */
  format: (value: number) => string;
  /** A value as a short axis label (a duration as "28h"); defaults to `format`. Always one line. */
  tickFormat?: (value: number) => string;
  /** Pin the top of the axis (100 for a share); otherwise it is the first round tick above the data. */
  fixedTop?: number;
  /** Plot height in px. */
  height?: number;
  /** Less chrome for a tile: the first and last x label only, no legend. */
  compact?: boolean;
  /** The words for a tooltip note on the point before ("Week before"). */
  beforeLabel?: string;
  /** Show the legend (default: two or more series, and not compact). */
  legend?: boolean;
  className?: string;
};

/**
 * A line chart for one or more series on one zero-based axis (never two). Gridlines at round
 * ticks, direct axis labels, a crosshair that snaps to the nearest x with one tooltip listing
 * every series there (and the value at the point before it), and the latest point of each line
 * marked. A gap breaks the line; a point alone between gaps is a dot. Keyboard: focus the plot
 * and use the arrow keys, Home and End; Escape hides the readout. The same numbers are in a
 * screen-reader table and the plot has a text label. Marks are placed in percentages, so it fills
 * any width.
 */
export function LineChart({ label, points, series, format, tickFormat, fixedTop, height = 160, compact = false, beforeLabel = "Before", legend, className }: Props) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const count = points.length;
  if (count === 0 || series.length === 0) return null;

  const known = series.flatMap((s) => s.values).filter((v): v is number => v !== null && v !== undefined);
  const scale = niceScale(Math.max(0, ...known), fixedTop, compact ? 2 : 4);
  const showLegend = legend ?? (!compact && series.length > 1);
  const ticks = compact ? [scale.ticks[0], scale.ticks[scale.ticks.length - 1]] : scale.ticks;
  const axis = tickFormat ?? format;
  // The gutter is as wide as the longest label (in characters), so a label never wraps or clips.
  const gutter = `${Math.max(2, ...ticks.map((tick) => axis(tick).length)) + 1}ch`;
  const xLabels = compact ? [0, count - 1] : labelIndexes(count);

  const move = (ratio: number) => setActive(nearestIndex(ratio, count));
  const step = (delta: number) => setActive((current) => Math.min(count - 1, Math.max(0, (current ?? count - 1) + delta)));

  const tooltipRows = active === null ? [] : series.map((s) => {
    const value = s.values[active];
    const before = active > 0 ? s.values[active - 1] : null;
    return {
      key: s.key,
      label: s.label,
      color: s.color,
      value: value === null || value === undefined ? "No data" : format(value),
      note: before === null || before === undefined ? undefined : `${beforeLabel}: ${format(before)}`,
    };
  });
  const activeX = active === null ? 0 : xPercent(active, count);

  return (
    <figure className={cn("m-0 space-y-2", className)} data-testid="line-chart">
      {/* The top padding keeps the highest axis label inside the chart, clear of whatever is above. */}
      <div className="flex gap-2 pt-2">
        <div aria-hidden className="relative shrink-0 whitespace-nowrap text-xs text-fg-secondary tabular-nums" style={{ height, width: gutter }}>
          {ticks.map((tick) => (
            <span key={tick} className="absolute right-0 -translate-y-1/2 leading-none" style={{ top: `${yPercent(tick, scale.top)}%` }}>
              {axis(tick)}
            </span>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div
            role="group"
            tabIndex={0}
            aria-label={`${label}: use the arrow keys to read each point`}
            aria-describedby={`${id}-table`}
            data-testid="line-plot"
            className="relative rounded-sm outline-offset-4"
            style={{ height }}
            onPointerMove={(event) => {
              const box = event.currentTarget.getBoundingClientRect();
              move(box.width > 0 ? (event.clientX - box.left) / box.width : 1);
            }}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive((current) => current ?? count - 1)}
            onBlur={() => setActive(null)}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") step(-1);
              else if (event.key === "ArrowRight") step(1);
              else if (event.key === "Home") setActive(0);
              else if (event.key === "End") setActive(count - 1);
              else if (event.key === "Escape") setActive(null);
              else return;
              event.preventDefault();
            }}
          >
            {scale.ticks.map((tick) => (
              <div
                key={tick}
                aria-hidden
                className={cn("absolute inset-x-0 border-t", tick === 0 ? "border-line-strong" : "border-line-subtle")}
                style={{ top: `${yPercent(tick, scale.top)}%` }}
              />
            ))}
            <svg aria-hidden viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible">
              {series.map((s) =>
                runsOf(s.values, scale.top).map((run, index) =>
                  run.length > 1 ? (
                    <polyline
                      key={`${s.key}-${index}`}
                      data-testid="series-line"
                      data-series={s.key}
                      points={run.map(([x, y]) => `${x},${y}`).join(" ")}
                      fill="none"
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className={seriesStyle(s.color).line}
                    />
                  ) : null,
                ),
              )}
            </svg>
            {active !== null ? (
              <div aria-hidden data-testid="chart-crosshair" className="absolute inset-y-0 w-px bg-line-strong" style={{ left: `${activeX}%` }} />
            ) : null}
            {series.map((s) => (
              <Dots key={s.key} series={s} count={count} top={scale.top} active={active} />
            ))}
            {active !== null ? (
              <ChartTooltip
                title={points[active].title ?? points[active].label}
                rows={tooltipRows}
                className="top-0"
                style={activeX > 55 ? { right: `${100 - activeX + 2}%` } : { left: `${activeX + 2}%` }}
              />
            ) : null}
          </div>
          <div aria-hidden className={cn("relative mt-2 h-4 text-xs text-fg-secondary", compact && "flex justify-between")}>
            {xLabels.map((index) =>
              compact ? (
                <span key={points[index].key}>{points[index].label}</span>
              ) : (
                <span
                  key={points[index].key}
                  className={cn("absolute whitespace-nowrap", index === 0 ? "translate-x-0" : index === count - 1 ? "-translate-x-full" : "-translate-x-1/2")}
                  style={{ left: index === 0 ? 0 : index === count - 1 ? "100%" : `${xPercent(index, count)}%` }}
                >
                  {points[index].label}
                </span>
              ),
            )}
          </div>
        </div>
      </div>
      {showLegend ? <ChartLegend items={series.map((s) => ({ key: s.key, label: s.label, color: s.color }))} /> : null}
      <div id={`${id}-table`}>
        <ChartTable
          caption={label}
          columns={["Week", ...series.map((s) => s.label)]}
          rows={points.map((point, index) => ({
            key: point.key,
            cells: [point.title ?? point.label, ...series.map((s) => (s.values[index] === null || s.values[index] === undefined ? "No data" : format(s.values[index] as number)))],
          }))}
        />
      </div>
    </figure>
  );
}

/**
 * The dots: the latest point of a line and the hovered point. A point alone between gaps gets a
 * dot unless it is the first reading of a series that has more (a line that starts mid-chart is
 * not preceded by a stray dot there); any point can still be read by hovering or from the table.
 */
function Dots({ series, count, top, active }: { series: LineSeries; count: number; top: number; active: number | null }) {
  const shown = new Set<number>();
  const known = series.values.filter((v) => v !== null && v !== undefined).length;
  series.values.forEach((value, index) => {
    if (value === null || value === undefined) return;
    const alone = (index === 0 || series.values[index - 1] == null) && (index === count - 1 || series.values[index + 1] == null);
    const lastKnown = index === lastIndex(series.values);
    const firstKnown = index === series.values.findIndex((v) => v !== null && v !== undefined);
    if ((alone && (known === 1 || !firstKnown)) || lastKnown || index === active) shown.add(index);
  });
  return (
    <>
      {[...shown].map((index) => (
        <span
          key={index}
          aria-hidden
          data-testid={index === active ? "series-active" : index === lastIndex(series.values) ? "series-last" : "series-dot"}
          className={cn("absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-panel", seriesStyle(series.color).bg)}
          style={{ left: `${xPercent(index, count)}%`, top: `${yPercent(series.values[index] as number, top)}%` }}
        />
      ))}
    </>
  );
}

function lastIndex(values: (number | null | undefined)[]): number {
  for (let i = values.length - 1; i >= 0; i -= 1) if (values[i] !== null && values[i] !== undefined) return i;
  return -1;
}

/** Which x labels to print: the ends and a few between, never so many they collide. */
export function labelIndexes(count: number, most = 5): number[] {
  if (count <= most) return Array.from({ length: count }, (_, i) => i);
  const step = (count - 1) / (most - 1);
  return Array.from(new Set(Array.from({ length: most }, (_, i) => Math.round(i * step))));
}
