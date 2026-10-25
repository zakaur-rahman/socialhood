/**
 * Layout of the trend visual (VIS-07). The values are the API's, from the metric_trend tool; this
 * only lays them out as a line and words them. Pure, tested directly.
 *
 * A point without a reading is a gap: the line breaks there and nothing is drawn through it or in
 * its place (never a zero). The scale starts at 0, so a small change doesn't look like a big one;
 * the lowest and highest points are stated as text beside the picture.
 */
import { dayLabel } from "@/lib/reports/format";
import type { TrendPoint, TrendVisual } from "@/lib/api/types";

import { formatValue, NONE } from "./visuals";

export type Plotted = {
  /** Runs of consecutive points with a reading, each a list of [x, y] in the viewBox. A gap ends a run. */
  runs: [number, number][][];
  /** The latest point with a reading. */
  last: [number, number] | null;
  /** How many points have no reading. */
  gaps: number;
};

export function plotTrend(points: Pick<TrendPoint, "value">[], width: number, height: number, pad = 4): Plotted {
  const known = points.map((p) => p.value).filter((v): v is number => v !== null && v !== undefined);
  const top = Math.max(1, ...known);
  const step = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;
  const runs: [number, number][][] = [];
  let current: [number, number][] = [];
  let last: [number, number] | null = null;
  points.forEach((point, index) => {
    if (point.value === null || point.value === undefined) {
      if (current.length) runs.push(current);
      current = [];
      return;
    }
    // A single point sits in the middle rather than at the left edge.
    const x = points.length > 1 ? pad + index * step : width / 2;
    const y = height - pad - (point.value / top) * (height - pad * 2);
    const at: [number, number] = [Number(x.toFixed(1)), Number(y.toFixed(1))];
    current.push(at);
    last = at;
  });
  if (current.length) runs.push(current);
  return { runs, last, gaps: points.length - known.length };
}

/** "12 Oct" for a day, "Week of 12 Oct" for a week's first day. */
export function pointLabel(point: Pick<TrendPoint, "day">, granularity: TrendVisual["granularity"]): string {
  return granularity === "week" ? `Week of ${dayLabel(point.day)}` : dayLabel(point.day);
}

/** One table row of the text version: the label and the figure, or "No reading". */
export function pointRow(
  point: TrendPoint,
  visual: Pick<TrendVisual, "granularity" | "format">,
): { label: string; figure: string } {
  return {
    label: pointLabel(point, visual.granularity),
    figure: point.value === null || point.value === undefined ? "No reading" : formatValue(visual.format, point.value),
  };
}

/** The highlighted figures under the chart: latest, lowest and highest, with the day each was. */
export function trendFacts(visual: TrendVisual): { label: string; value: string; day: string }[] {
  const facts: { label: string; value: string; day: string | null; point: TrendPoint | null | undefined }[] = [
    { label: "Latest", value: "", day: null, point: visual.last },
    { label: "Lowest", value: "", day: null, point: visual.lowest },
    { label: "Highest", value: "", day: null, point: visual.highest },
  ];
  return facts
    .filter((fact) => fact.point)
    .map((fact) => ({
      label: fact.label,
      value: formatValue(visual.format, fact.point?.value),
      day: fact.point ? pointLabel(fact.point, visual.granularity) : NONE,
    }));
}

/** "21 of 22 days have a reading", or null when none is missing. */
export function gapsNote(visual: Pick<TrendVisual, "points" | "known_points" | "granularity">): string | null {
  const missing = visual.points.length - visual.known_points;
  if (missing <= 0) return null;
  const unit = visual.granularity === "week" ? "weeks" : "days";
  return `${visual.known_points} of ${visual.points.length} ${unit} have a reading. The line breaks where there is none.`;
}
