import type { ReportMetric, ReportPoint } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { dayLabel, plot, seriesSummary } from "@/lib/reports/format";

const WIDTH = 200;
const HEIGHT = 44;
const STROKE = 2;

type Props = {
  label: string;
  unit: ReportMetric["unit"];
  series: ReportPoint[];
  className?: string;
};

/**
 * GR-34: one metric over the weeks, a hand-built SVG in the one series colour (DESIGN_SYSTEM
 * 1.8). The scale starts at 0 (a share runs 0 to 100). A week without a value breaks the line, and
 * a week on its own between two gaps is a dot: nothing is drawn through a gap or put in its place.
 * The latest week has a dot. The picture is labelled with every value in words, and the first and
 * last week sit under it as text; the tile above states the numbers.
 */
export function SeriesChart({ label, unit, series, className }: Props) {
  if (series.length === 0) return null;
  const { runs, last, gaps } = plot(series, unit, WIDTH, HEIGHT);
  const first = series[0].week_start;
  const end = series[series.length - 1].week_start;
  return (
    <figure className={cn("m-0", className)} data-testid="series-chart">
      <svg
        role="img"
        aria-label={seriesSummary({ label, unit, series })}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full overflow-visible text-chart-series-1"
      >
        <line x1={0} x2={WIDTH} y1={HEIGHT - 4} y2={HEIGHT - 4} stroke="currentColor" strokeOpacity={0.2} strokeWidth={1} />
        {runs.map((run, index) =>
          run.length > 1 ? (
            <polyline
              key={index}
              data-testid="series-line"
              points={run.map(([x, y]) => `${x},${y}`).join(" ")}
              fill="none"
              stroke="currentColor"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ) : (
            <circle key={index} data-testid="series-dot" cx={run[0][0]} cy={run[0][1]} r={STROKE} fill="currentColor" />
          ),
        )}
        {last ? <circle data-testid="series-last" cx={last[0]} cy={last[1]} r={STROKE + 1} fill="currentColor" /> : null}
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-fg-secondary">
        <span>{dayLabel(first)}</span>
        {gaps > 0 ? <span data-testid="series-gaps">{gaps === 1 ? "1 week without data" : `${gaps} weeks without data`}</span> : null}
        <span>{dayLabel(end)}</span>
      </figcaption>
    </figure>
  );
}
