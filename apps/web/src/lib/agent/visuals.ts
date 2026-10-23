/**
 * Presentation of the visual answers (GR-38). The numbers are the API's: every figure and every
 * change was worked out by the analytics service (`MetricDelta.change_pct`), so nothing here
 * derives a number; these functions only format them. Pure, tested directly.
 */
import type { Trend } from "@/components/home/format";
import type { MetricDelta } from "@/lib/api/types";

const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const MINUS = "−";
export const NONE = "—";

/** A figure: "11,800", "6.1%", or "—" when it isn't available. */
export function formatValue(format: "count" | "percent", value: number | null | undefined): string {
  if (value === null || value === undefined) return NONE;
  return format === "percent" ? `${whole.format(value)}%` : whole.format(value);
}

/**
 * The change chip of a card: "+18.4%", "−9%", "No change", or "New" against a previous zero; null
 * when the API gave no direction (a side is unknown, or the periods differ in length). The tone is
 * the API's rule for the metric (more unfollows is bad news).
 */
export function deltaTrend(delta: Pick<MetricDelta, "change_pct" | "direction" | "tone">, previous: string): Trend | null {
  const { direction, change_pct: pct, tone } = delta;
  if (!direction) return null;
  const good = tone === "good" ? true : tone === "bad" ? false : null;
  if (direction === "flat") return { direction, good: null, text: "No change", words: `no change from ${previous}` };
  if (pct === null || pct === undefined) {
    return { direction, good, text: "New", words: `${direction} from none in ${previous}` };
  }
  const size = whole.format(Math.abs(pct));
  return {
    direction,
    good,
    text: `${pct > 0 ? "+" : MINUS}${size}%`,
    words: `${direction} ${size}% from ${previous}`,
  };
}

/**
 * The lines under a card's number: why it isn't available, the previous figure, and the days behind
 * a figure that has gaps.
 */
export function deltaHints(delta: MetricDelta, previousLabel: string): string[] {
  const lines: string[] = [];
  const { current, previous } = delta;
  if (delta.unavailable) lines.push(delta.unavailable);
  else if (current === null || current === undefined) lines.push("Not available.");
  if (previous !== null && previous !== undefined) lines.push(`${previousLabel}: ${formatValue(delta.format, previous)}`);
  else if (!delta.unavailable && current !== null && current !== undefined) lines.push(`${previousLabel}: not available`);
  if (delta.current_coverage) lines.push(`This period: ${delta.current_coverage}`);
  if (delta.previous_coverage) lines.push(`${previousLabel}: ${delta.previous_coverage}`);
  return lines;
}

/** The insight metrics the API adds up day by day; followers is the latest reading. */
const DAILY_TOTALS = new Set(["reach", "views", "accounts_engaged", "interactions", "follows", "unfollows", "profile_link_taps"]);

/** One line under a comparison that explains how the figures were added up; null when none apply. */
export function totalsNote(metrics: Pick<MetricDelta, "key">[]): string | null {
  const daily = metrics.some((m) => DAILY_TOTALS.has(m.key));
  const followers = metrics.some((m) => m.key === "followers");
  if (daily && followers) return "Reach, views and similar figures add up each day's figure. Followers is the latest count.";
  if (daily) return "Reach, views and similar figures add up each day's figure, so someone reached on two days counts twice.";
  return null;
}

/** A picture address from the API, only if it is a plain https URL (the API checks too). */
export function httpsOnly(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}
