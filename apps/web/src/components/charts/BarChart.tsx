"use client";

import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { ChartLegend } from "./ChartLegend";
import { ChartTable } from "./ChartTable";
import { ChartTooltip } from "./ChartTooltip";
import { seriesStyle } from "./palette";

export type BarRow = {
  key: string;
  /** The name shown beside the bar (a mark and a name for an account). */
  label: ReactNode;
  /** The name as text, for the table and the tooltip. */
  name: string;
  /** Position in the palette: the entity's. */
  color: number;
  value: number | null | undefined;
  /** The comparison value (last week), drawn as a thinner, lighter bar of the same colour. */
  previous?: number | null;
  /** Why there is no value ("Not available for WhatsApp"); shown instead of a bar. */
  unavailable?: string | null;
};

type Props = {
  label: string;
  rows: BarRow[];
  format: (value: number) => string;
  /** The change as text for the tooltip ("+12%"), when the caller has one. */
  change?: (row: BarRow) => string | null;
  currentLabel?: string;
  previousLabel?: string;
  className?: string;
};

/**
 * Horizontal bars, one row per entity in its own colour, this period against the one before: the
 * period is the full-colour bar and its value is written at the end of it, the one before is a
 * thinner, lighter bar of the same colour. All bars share one zero-based scale. Bars start flat
 * at the baseline and round at the data end. A row is focusable and hovering or focusing it shows
 * both values and the change; a row with no figure says why instead of drawing a zero.
 */
export function BarChart({ label, rows, format, change, currentLabel = "This week", previousLabel = "Last week", className }: Props) {
  const id = useId();
  const [active, setActive] = useState<string | null>(null);
  if (rows.length === 0) return null;
  const top = Math.max(1, ...rows.flatMap((r) => [r.value ?? 0, r.previous ?? 0]));
  const width = (value: number | null | undefined) => (value ? `${Math.max(1.5, (value / top) * 100)}%` : "0%");
  const hasPrevious = rows.some((r) => r.previous !== undefined && r.previous !== null);

  return (
    <figure className={cn("m-0 space-y-2", className)} data-testid="bar-chart">
      <ul aria-label={label} aria-describedby={`${id}-table`} className="m-0 list-none space-y-1.5 p-0">
        {rows.map((row) => {
          const open = active === row.key;
          const delta = change?.(row) ?? null;
          return (
            <li
              key={row.key}
              data-row={row.key}
              tabIndex={0}
              onPointerEnter={() => setActive(row.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(row.key)}
              onBlur={() => setActive(null)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setActive(null);
              }}
              className="relative grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto] items-center gap-x-2 rounded-sm py-0.5 text-xs sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto]"
            >
              <span className="min-w-0 truncate text-fg-secondary">{row.label}</span>
              {row.unavailable ? (
                <span className="col-span-2 text-fg-secondary">{row.unavailable}</span>
              ) : (
                <>
                  <span className="flex flex-col justify-center gap-0.5 border-l border-line-strong py-0.5">
                    <span aria-hidden data-testid="bar-current" className={cn("h-2.5 rounded-r-sm", seriesStyle(row.color).bg)} style={{ width: width(row.value) }} />
                    {row.previous !== undefined && row.previous !== null ? (
                      <span aria-hidden data-testid="bar-previous" className={cn("h-1.5 rounded-r-sm opacity-40", seriesStyle(row.color).bg)} style={{ width: width(row.previous) }} />
                    ) : null}
                  </span>
                  <span className="min-w-8 text-right font-semibold tabular-nums text-fg">{row.value === null || row.value === undefined ? "—" : format(row.value)}</span>
                </>
              )}
              {open ? (
                <ChartTooltip
                  title={row.name}
                  className="left-1/4 top-full mt-1"
                  rows={[
                    { key: "now", label: currentLabel, color: row.color, value: row.value === null || row.value === undefined ? "No data" : format(row.value) },
                    ...(row.previous !== undefined
                      ? [{ key: "before", label: previousLabel, color: row.color, value: row.previous === null ? "No data" : format(row.previous), note: delta ?? undefined }]
                      : []),
                  ]}
                />
              ) : null}
            </li>
          );
        })}
      </ul>
      {hasPrevious ? (
        <p aria-hidden className="m-0 flex items-center gap-3 text-xs text-fg-secondary">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-4 rounded-sm bg-fg-secondary" /> {currentLabel}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-sm bg-fg-secondary opacity-40" /> {previousLabel}
          </span>
        </p>
      ) : null}
      <ChartLegend items={rows.map((r) => ({ key: r.key, label: r.name, color: r.color, shape: "box" }))} className="sr-only" />
      <div id={`${id}-table`}>
        <ChartTable
          caption={label}
          columns={["Name", currentLabel, ...(hasPrevious ? [previousLabel] : [])]}
          rows={rows.map((r) => ({
            key: r.key,
            cells: [
              r.name,
              r.unavailable ?? (r.value === null || r.value === undefined ? "No data" : format(r.value)),
              ...(hasPrevious ? [r.previous === null || r.previous === undefined ? "No data" : format(r.previous)] : []),
            ],
          }))}
        />
      </div>
    </figure>
  );
}
