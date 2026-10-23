/**
 * Presentation of the weekly report (GR-34). Every number and every change is the API's
 * (services/reports.py works them out, the digest email carries the same ones); these functions
 * only format them and lay a series out as a line. Pure, tested directly.
 */
import { DASH, formatCount, formatPercent, formatWait, type Trend } from "@/components/home/format";
import type { ReportMetric, ReportPoint } from "@/lib/api/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MINUS = "−";
const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

/** A `?week=` value worth asking the API about: a plain date (the API checks it is a Monday). */
export function parseWeekParam(value: string | null | undefined): string | null {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

/** "21 Sep" for a YYYY-MM-DD day. */
export function dayLabel(day: string): string {
  const [, month, date] = day.split("-").map(Number);
  return `${date} ${MONTHS[month - 1]}`;
}

/** "Week of 21 Sep": a week by its Monday. */
export function weekLabel(monday: string): string {
  return `Week of ${dayLabel(monday)}`;
}

/** A report figure as text: "1,204", "62.5%", "12 min", or "—" when it isn't known. */
export function formatMetric(unit: ReportMetric["unit"], value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  if (unit === "percent") return formatPercent(value);
  if (unit === "seconds") return formatWait(value);
  return formatCount(Math.round(value));
}

/**
 * The change chip of a tile, from the API's change: a percent for counts and times, points for a
 * share. Null when the API gave no direction (a side is unknown). "New" is a rise from none. The
 * tone follows `lower_is_better` (a faster first response is good news).
 */
export function reportTrend(metric: ReportMetric): Trend | null {
  const { direction, change_pct: pct, change_points: points, lower_is_better: lower } = metric;
  if (!direction) return null;
  const good = direction === "flat" ? null : (direction === "up") !== lower;
  if (direction === "flat") {
    return { direction, good: null, text: "No change", words: "no change from the week before" };
  }
  if (points !== null && points !== undefined) {
    const size = oneDecimal.format(Math.abs(points));
    return {
      direction,
      good,
      text: `${points > 0 ? "+" : MINUS}${size} pts`,
      words: `${direction} ${size} percentage points from the week before`,
    };
  }
  if (pct === null || pct === undefined) {
    return { direction, good, text: "New", words: `${direction} from none the week before` };
  }
  const size = oneDecimal.format(Math.abs(pct));
  return {
    direction,
    good,
    text: `${pct > 0 ? "+" : MINUS}${size}%`,
    words: `${direction} ${size}% from the week before`,
  };
}

/** The line under a tile's number: the week before, or why there is nothing to compare with. */
export function previousLine(metric: ReportMetric): string {
  return metric.previous === null || metric.previous === undefined
    ? "Week before: no data"
    : `Week before: ${formatMetric(metric.unit, metric.previous)}`;
}

export type Plot = {
  /** Runs of consecutive weeks with a value, each a list of [x, y] in the viewBox. A gap ends a run. */
  runs: [number, number][][];
  /** The latest week's point, when it has a value. */
  last: [number, number] | null;
  /** How many weeks have no value. */
  gaps: number;
};

/**
 * Lays a series out in a width x height box. The scale starts at 0 (a count or a time) or spans 0
 * to 100 (a share), so a small change doesn't look like a big one. A week without a value breaks
 * the line: nothing is drawn through it and nothing stands in for it.
 */
export function plot(
  points: Pick<ReportPoint, "value">[],
  unit: ReportMetric["unit"],
  width: number,
  height: number,
  pad = 4,
): Plot {
  const known = points.map((p) => p.value).filter((v): v is number => v !== null && v !== undefined);
  const top = unit === "percent" ? 100 : Math.max(1, ...known);
  const step = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;
  const runs: [number, number][][] = [];
  let current: [number, number][] = [];
  let last: [number, number] | null = null;
  points.forEach((point, index) => {
    if (point.value === null || point.value === undefined) {
      if (current.length) runs.push(current);
      current = [];
      last = null;
      return;
    }
    const x = pad + index * step;
    const y = height - pad - (point.value / top) * (height - pad * 2);
    const at: [number, number] = [Number(x.toFixed(1)), Number(y.toFixed(1))];
    current.push(at);
    last = at;
  });
  if (current.length) runs.push(current);
  return { runs, last, gaps: points.length - known.length };
}

/** The words for a chart's label: "Messages received, 8 weeks from 3 Aug: 12, 15, no data, 20". */
export function seriesSummary(metric: Pick<ReportMetric, "label" | "unit" | "series">): string {
  const first = metric.series[0];
  const values = metric.series.map((p) => (p.value === null || p.value === undefined ? "no data" : formatMetric(metric.unit, p.value)));
  const from = first ? ` from ${dayLabel(first.week_start)}` : "";
  return `${metric.label}, ${metric.series.length} weeks${from}: ${values.join(", ")}`;
}
