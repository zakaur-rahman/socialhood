import { LineChart } from "@/components/charts/LineChart";
import type { ReportMetric, ReportPoint } from "@/lib/api/types";
import { dayLabel, formatAxis, formatMetric, gapNote, weekLabel } from "@/lib/reports/format";
import { cn } from "@/lib/utils";

type Props = {
  label: string;
  unit: ReportMetric["unit"];
  series: ReportPoint[];
  /** The palette position of the entity this line is for (an account's, or 0 for the workspace). */
  color?: number;
  className?: string;
};

/**
 * GR-34: one metric over the weeks as a compact line chart (components/charts). The scale starts
 * at 0 (a share runs 0 to 100), the first and last week sit under the axis, hovering or focusing
 * reads any week with the week before it, and a week without a value breaks the line instead of
 * being drawn as 0. The tile above states the numbers; the chart carries a table of every week.
 */
export function SeriesChart({ label, unit, series, color = 0, className }: Props) {
  if (series.length === 0) return null;
  const note = gapNote(series);
  return (
    <div className={cn("space-y-1", className)} data-testid="series-chart">
      <LineChart
        compact
        height={72}
        label={`${label} by week`}
        beforeLabel="Week before"
        fixedTop={unit === "percent" ? 100 : undefined}
        format={(value) => formatMetric(unit, value)}
        tickFormat={(value) => formatAxis(unit, value)}
        points={series.map((p) => ({ key: p.week_start, label: dayLabel(p.week_start), title: weekLabel(p.week_start) }))}
        series={[{ key: label, label, color, values: series.map((p) => p.value) }]}
      />
      {note ? (
        <p data-testid="series-gaps" className="m-0 text-xs text-fg-secondary">
          {note}
        </p>
      ) : null}
    </div>
  );
}
