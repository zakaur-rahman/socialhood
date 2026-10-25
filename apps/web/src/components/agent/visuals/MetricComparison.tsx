import { useId } from "react";

import { MetricTile } from "@/components/home/MetricTile";
import type { MetricComparisonVisual } from "@/lib/api/types";
import { deltaHints, deltaTrend, formatValue, totalsNote } from "@/lib/agent/visuals";
import { ITEM_TITLE } from "@/styles/tokens";

/**
 * GR-38: a period against another, a card per metric (compare_periods). Every figure and change is
 * the API's. A metric with no reading shows "—" and why, never 0; a metric with gaps says "21 of 22
 * days"; periods that differ in length show the totals without a change, and the note says so.
 *
 * Built from MetricTile (no card around the tiles: cards don't nest). The grid follows the width
 * of its own column (a container query), so it is one column in a 320 px phone, two in the Ask
 * panel and three on the Ask page.
 */
export function MetricComparison({ visual }: { visual: MetricComparisonVisual }) {
  const titleId = useId();
  const note = totalsNote(visual.metrics);
  return (
    <section aria-labelledby={titleId} className="@container space-y-2" data-testid="visual-metric-comparison">
      <h3 id={titleId} className={ITEM_TITLE}>
        {visual.title}
      </h3>
      {visual.note ? <p className="text-xs text-fg-secondary">{visual.note}</p> : null}
      {visual.metrics.length === 0 ? (
        <p className="text-sm text-fg-secondary">No figures to compare.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-2 @xs:grid-cols-2 @2xl:grid-cols-3">
          {visual.metrics.map((metric) => (
            <li key={metric.key} data-metric={metric.key} className="min-w-0">
              <MetricTile
                label={metric.label}
                value={formatValue(metric.format, metric.current)}
                trend={deltaTrend(metric, visual.previous.label)}
                hint={
                  <>
                    {deltaHints(metric, visual.previous.label).map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </>
                }
              />
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="text-xs text-fg-secondary">{note}</p> : null}
    </section>
  );
}
