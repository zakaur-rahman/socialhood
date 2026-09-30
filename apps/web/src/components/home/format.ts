/**
 * Presentation of Home's numbers (FR-HOME-01, UX-SCR-01). The numbers are the API's (GET
 * …/overview, whose definitions it shares with the weekly digest): these functions only format
 * them and compare a period with the one before it. Pure, tested directly.
 */
import type { Overview, Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";

/** A period's length in words: "1 day", "7 days", "12 days". */
export function periodLabel(days: number): string {
  return `${days} ${days === 1 ? "day" : "days"}`;
}

/** The header's period: "Last 7 days", "Last 30 days", or a custom range's length. */
export function rangeHeading(overview: Pick<Overview, "range" | "days">): string {
  return overview.range === "custom" ? periodLabel(overview.days) : `Last ${periodLabel(overview.days)}`;
}

/** For sentences: "the last 7 days", or "these 12 days" for a custom range. */
export function periodPhrase(overview: Pick<Overview, "range" | "days">): string {
  return `${overview.range === "custom" ? "these" : "the last"} ${periodLabel(overview.days)}`;
}

/** "Overview across Instagram & WhatsApp", from the connected accounts' platforms. */
export function channelsLine(platforms: Platform[]): string {
  if (platforms.length === 0) return "No channels connected yet";
  return `Overview across ${platforms.map((platform) => PLATFORM_LABEL[platform]).join(" & ")}`;
}

/** "2 channels connected" (active accounts). */
export function channelsConnected(count: number): string {
  if (count === 0) return "No channels connected";
  return `${count} ${count === 1 ? "channel" : "channels"} connected`;
}

const count = new Intl.NumberFormat("en-US");
const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const MINUS = "−";
export const DASH = "—";

export function formatCount(n: number): string {
  return count.format(n);
}

/** The API's 0-100 share: "62.5%", or "—" when there was nothing to divide. */
export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? DASH : `${oneDecimal.format(value)}%`;
}

/** A wait in seconds: "45 s", "7 min 45 s", "25 min", "1 h 5 min", "2 d 3 h", or "—". */
export function formatWait(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return DASH;
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  if (s < 600) {
    const rest = s % 60;
    return rest ? `${Math.floor(s / 60)} min ${rest} s` : `${s / 60} min`;
  }
  const minutes = Math.round(s / 60);
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 24 * 60) {
    const rest = minutes % 60;
    return rest ? `${Math.floor(minutes / 60)} h ${rest} min` : `${minutes / 60} h`;
  }
  const hours = Math.round(s / 3600);
  return hours % 24 ? `${Math.floor(hours / 24)} d ${hours % 24} h` : `${hours / 24} d`;
}

export type Trend = {
  direction: "up" | "down" | "flat";
  /** Whether the change is good news (more replies by AI, faster answers); null when neutral. */
  good: boolean | null;
  /** Short text beside the number: "+25%", "−3 pts", "No change". */
  text: string;
  /** For screen readers: "up 25% from the previous 7 days". */
  words: string;
};

type Better = "higher" | "lower" | "neither";

const UNIT = { percent: { short: "%", long: "%" }, points: { short: " pts", long: " points" } } as const;

function trend(delta: number, size: string, unit: keyof typeof UNIT, period: string, better: Better): Trend {
  const before = `from the previous ${period}`;
  if (size === "0") {
    return { direction: "flat", good: null, text: "No change", words: `no change ${before}` };
  }
  const direction = delta > 0 ? "up" : "down";
  const good = better === "neither" ? null : (direction === "up") === (better === "higher");
  return {
    direction,
    good,
    text: `${delta > 0 ? "+" : MINUS}${size}${UNIT[unit].short}`,
    words: `${direction} ${size}${UNIT[unit].long} ${before}`,
  };
}

/** A count against the period before: the relative change, none when there was nothing before.
 * `period` names the length of both ("7 days"). */
export function countTrend(
  current: number,
  previous: number,
  period: string,
  better: Better = "neither",
): Trend | null {
  if (previous <= 0) return null;
  const change = ((current - previous) / previous) * 100;
  return trend(change, count.format(Math.round(Math.abs(change))), "percent", period, better);
}

/** A share (0-100) against the period before, in percentage points. */
export function rateTrend(
  current: number | null | undefined,
  previous: number | null | undefined,
  period: string,
  better: Better = "higher",
): Trend | null {
  if (current === null || current === undefined || previous === null || previous === undefined) return null;
  const change = current - previous;
  return trend(change, oneDecimal.format(Math.abs(change)), "points", period, better);
}

/** A wait against the period before: the relative change; shorter is better. */
export function waitTrend(
  current: number | null | undefined,
  previous: number | null | undefined,
  period: string,
): Trend | null {
  if (current === null || current === undefined || !previous) return null;
  const change = ((current - previous) / previous) * 100;
  return trend(change, count.format(Math.round(Math.abs(change))), "percent", period, "lower");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "24–30 Sep", "30 Oct–5 Nov"; the API's dates are local days (YYYY-MM-DD). */
export function formatSpan(since: string, until: string): string {
  const [sy, sm, sd] = since.split("-").map(Number);
  const [uy, um, ud] = until.split("-").map(Number);
  const month = (m: number) => MONTHS[m - 1];
  if (sy === uy && sm === um) return `${sd}–${ud} ${month(um)}`;
  if (sy === uy) return `${sd} ${month(sm)}–${ud} ${month(um)}`;
  return `${sd} ${month(sm)} ${sy}–${ud} ${month(um)} ${uy}`;
}

/** "12m ago", "just now", "3d ago", "28 Sep": how long ago the customer wrote. */
export function agoLabel(relative: string): string {
  if (relative === "now") return "just now";
  return /^\d+[mhd]$/.test(relative) ? `${relative} ago` : relative;
}

/** Whole-number shares for a legend: "57%"; "—" when nothing was analysed. */
export function formatShare(value: number | null | undefined): string {
  return value === null || value === undefined ? DASH : `${Math.round(value)}%`;
}
