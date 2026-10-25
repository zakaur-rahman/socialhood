/**
 * Presentation of the weekly report (GR-34). Every number and every change is the API's
 * (services/reports.py works them out, the digest email carries the same ones); these functions
 * only format them and lay a series out as a line. Pure, tested directly.
 */
import { DASH, formatCount, formatPercent, formatWait, formatWaitCompact, smallChange, type Trend } from "@/components/home/format";
import type { ReportMetric } from "@/lib/api/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MINUS = "−";
const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

/** A `?week=` value worth asking the API about: a plain date (the API checks it is a Monday). */
export function parseWeekParam(value: string | null | undefined): string | null {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** An `?account=` value worth asking the API about: an id (the API 404s one that isn't this workspace's). */
export function parseAccountParam(value: string | null | undefined): string | null {
  return value && UUID.test(value) ? value : null;
}

/** The report's address for a week and an account (both optional): what a link reproduces. */
export function reportHref(pathname: string, view: { week?: string | null; account?: string | null }): string {
  const query = new URLSearchParams();
  if (view.week) query.set("week", view.week);
  if (view.account) query.set("account", view.account);
  const text = query.toString();
  return text ? `${pathname}?${text}` : pathname;
}

/** Why an account's figure is missing, in words (the API's reason code). */
export function unavailableWords(reason: string | null | undefined): string {
  if (reason === "insights_not_granted") return "Not available: this account gives no insights";
  if (reason === "no_readings") return "No readings yet";
  return "Not available";
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
export function reportTrend(
  metric: Pick<ReportMetric, "direction" | "change_pct"> &
    Partial<Pick<ReportMetric, "change_points" | "lower_is_better" | "unit" | "value" | "previous">>,
): Trend | null {
  const { direction, change_pct: pct, change_points: points, lower_is_better: lower = false } = metric;
  if (!direction) return null;
  const good = direction === "flat" ? null : (direction === "up") !== lower;
  if (direction === "flat") {
    // Flat is the API's call for under half a percent (or point). Only exactly equal values are
    // "No change"; any other difference is written out.
    const unit = metric.unit ?? "count";
    const small = smallChange(metric.value, metric.previous, {
      points: unit === "percent",
      format: (n) => formatMetric(unit, n),
      period: "the week before",
    });
    return small ?? { direction, good: null, text: "No change", words: "no change from the week before" };
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
export function previousLine(metric: Pick<ReportMetric, "unit" | "previous">): string {
  return metric.previous === null || metric.previous === undefined
    ? "Week before: no data"
    : `Week before: ${formatMetric(metric.unit, metric.previous)}`;
}

/** The tooltip's change for a count compared with the week before: "+12%", "New" (a rise from none) or null. */
export function changeText(
  metric: Pick<ReportMetric, "direction" | "change_pct"> & Partial<Pick<ReportMetric, "unit" | "value" | "previous">>,
): string | null {
  return reportTrend(metric)?.text ?? null;
}

/** An axis label for a value: durations are compact ("28h", "1d 4h") so they stay on one line. */
export function formatAxis(unit: ReportMetric["unit"], value: number): string {
  return unit === "seconds" ? formatWaitCompact(value) : formatMetric(unit, value);
}

/**
 * The line under an insight's number: the week before and the days that have a reading, in one
 * sentence ("Week before: 1,056 · readings on 2 of 7 days (both weeks)"), or why there is nothing.
 */
export function insightLine(options: {
  unit: ReportMetric["unit"];
  previous: number | null | undefined;
  daysNow?: number | null;
  daysBefore?: number | null;
  daysTotal?: number | null;
  unavailable?: string | null;
}): string {
  const { unit, previous, daysNow, daysBefore, daysTotal, unavailable } = options;
  if (unavailable) return unavailableWords(unavailable);
  const before = previous === null || previous === undefined ? "Week before: no data" : `Week before: ${formatMetric(unit, previous)}`;
  if (!daysTotal || daysNow === null || daysNow === undefined) return before;
  const same = daysBefore === null || daysBefore === undefined || daysBefore === daysNow;
  const days = (n: number) => `${n} of ${daysTotal} days`;
  if (daysNow >= daysTotal && (same || daysBefore === daysTotal)) return before;
  return same ? `${before} · readings on ${days(daysNow)} (both weeks)` : `${before} · readings on ${days(daysNow)}, ${days(daysBefore ?? 0)} the week before`;
}

/**
 * A metric with nothing to draw over the weeks shown: no value at all, or (for a count) only zeros.
 * A rate or a time of 0 is a reading, so only a count can be idle by being zero.
 */
export function isIdle(unit: ReportMetric["unit"], series: { value?: number | null }[]): boolean {
  return series.every((p) => p.value === null || p.value === undefined || (unit === "count" && p.value === 0));
}

/** The note under a compact chart about weeks without a value: where the line starts, or how many. */
export function gapNote(series: { week_start: string; value?: number | null }[]): string | null {
  const missing = series.filter((p) => p.value === null || p.value === undefined).length;
  if (missing === 0) return null;
  const leading = series.findIndex((p) => p.value !== null && p.value !== undefined);
  if (leading > 0 && series.slice(0, leading).length === missing) return `No data before ${dayLabel(series[leading].week_start)}`;
  return missing === 1 ? "1 week without data" : `${missing} weeks without data`;
}
