import { useId } from "react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { deltaTrend } from "@/lib/agent/visuals";
import { gapsNote, plotTrend, pointRow, trendFacts } from "@/lib/agent/trend";
import type { TrendVisual } from "@/lib/api/types";
import { dayLabel } from "@/lib/reports/format";

const WIDTH = 300;
const HEIGHT = 96;
const STROKE = 2;

/**
 * VIS-07: one series over time (metric_trend), a hand-built SVG in the one chart colour
 * (DESIGN_SYSTEM 1.8; a second series waits for the categorical palette). Every value is the API's.
 *
 * - **Gaps are gaps.** A day or week with no reading breaks the line; nothing is drawn through it
 *   or put in its place, and a lone reading between two gaps is a dot. The note under the chart says
 *   how many readings are missing.
 * - **The scale starts at 0**, so a small change doesn't look big; the latest, lowest and highest
 *   points are stated as text.
 * - **Accessible:** the picture's label is the API's own summary, and a table of every point sits
 *   beside it for screen readers. The picture scales with its column: 375 px and the Ask panel.
 */
export function TrendChart({ visual }: { visual: TrendVisual }) {
  const titleId = useId();
  const { runs, last } = plotTrend(visual.points, WIDTH, HEIGHT);
  const facts = trendFacts(visual);
  const change = visual.direction && visual.change_pct !== null && visual.change_pct !== undefined
    ? deltaTrend({ change_pct: visual.change_pct, direction: visual.direction, tone: "neutral" }, "the first reading")
    : null;
  const first = visual.points[0];
  const end = visual.points[visual.points.length - 1];
  const gaps = gapsNote(visual);
  const hasLine = visual.known_points > 0;

  return (
    <Card asChild padding="standard" className="space-y-3">
      <section aria-labelledby={titleId} data-testid="visual-trend">
        <CardHeader>
          <CardTitle id={titleId} className="text-sm">
            {visual.title}
          </CardTitle>
          <CardDescription>
            {visual.granularity === "week" ? "One point a week" : "One point a day"}
            {change ? ` · ${change.text} from the first reading` : ""}
          </CardDescription>
        </CardHeader>
        {hasLine ? (
          <figure className="m-0 space-y-1">
            <svg
              role="img"
              aria-label={visual.summary}
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="h-auto w-full overflow-visible text-chart-series-1"
              data-testid="trend-svg"
            >
              <line x1={0} x2={WIDTH} y1={HEIGHT - 4} y2={HEIGHT - 4} stroke="currentColor" strokeOpacity={0.2} strokeWidth={1} />
              {runs.map((run, index) =>
                run.length > 1 ? (
                  <polyline
                    key={index}
                    data-testid="trend-line"
                    points={run.map(([x, y]) => `${x},${y}`).join(" ")}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={STROKE}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ) : (
                  <circle key={index} data-testid="trend-dot" cx={run[0][0]} cy={run[0][1]} r={STROKE} fill="currentColor" />
                ),
              )}
              {last ? <circle data-testid="trend-last" cx={last[0]} cy={last[1]} r={STROKE + 1} fill="currentColor" /> : null}
            </svg>
            <figcaption className="flex justify-between text-xs text-fg-secondary">
              <span>{first ? dayLabel(first.day) : null}</span>
              <span>{end ? dayLabel(end.day) : null}</span>
            </figcaption>
          </figure>
        ) : (
          <p className="text-sm text-fg-secondary">No readings in this period, so there is nothing to draw.</p>
        )}
        {facts.length > 0 ? (
          <dl className="grid grid-cols-3 gap-2 text-sm" data-testid="trend-facts">
            {facts.map((fact) => (
              <div key={fact.label} className="min-w-0">
                <dt className="text-xs text-fg-secondary">{fact.label}</dt>
                <dd className="font-medium tabular-nums">{fact.value}</dd>
                <dd className="truncate text-xs text-fg-secondary">{fact.day}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {gaps || visual.note ? (
          <p className="text-xs text-fg-secondary" data-testid="trend-gaps">
            {gaps ?? visual.note}
          </p>
        ) : null}
        <table className="sr-only" data-testid="trend-table">
          <caption>{visual.summary}</caption>
          <thead>
            <tr>
              <th scope="col">{visual.granularity === "week" ? "Week" : "Day"}</th>
              <th scope="col">{visual.metric_label}</th>
            </tr>
          </thead>
          <tbody>
            {visual.points.map((point) => {
              const row = pointRow(point, visual);
              return (
                <tr key={point.day}>
                  <th scope="row">{row.label}</th>
                  <td>{row.figure}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </Card>
  );
}
