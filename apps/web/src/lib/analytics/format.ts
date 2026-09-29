/**
 * Presentation of post analytics (FR-ANL-02; agent-architecture §6). The numbers are the API's:
 * these functions only format them, never derive new ones. Pure, tested directly.
 */
import type { AgeName, MetricName, PostComparison, PostPerformance } from "@/lib/api/types";
import { formatPlural } from "@/lib/comments/format";

/** The age selector's options, youngest first. */
export const AGES: AgeName[] = ["1h", "6h", "24h", "72h", "7d", "30d", "lifetime"];

export const AGE_LABEL: Record<AgeName, string> = {
  "1h": "1 h",
  "6h": "6 h",
  "24h": "24 h",
  "72h": "72 h",
  "7d": "7 d",
  "30d": "30 d",
  lifetime: "Lifetime",
};

/** "at 24 h" or "lifetime", for sentences. */
export function atAge(age: AgeName): string {
  return age === "lifetime" ? "lifetime" : `at ${AGE_LABEL[age]}`;
}

/** The figures in the order the API lists them (MetricName). */
export const METRICS: MetricName[] = ["reach", "views", "likes", "comments", "shares", "saves", "engagement_rate"];

export const METRIC_LABEL: Record<MetricName, string> = {
  reach: "Reach",
  views: "Views",
  likes: "Likes",
  comments: "Comments",
  shares: "Shares",
  saves: "Saves",
  engagement_rate: "Engagement rate",
};

const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const MINUS = "−";

/** A figure as the API gave it: "1,204", "6.1%" (engagement rate is already a percentage), "—". */
export function formatMetric(metric: MetricName, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return metric === "engagement_rate" ? `${whole.format(value)}%` : whole.format(value);
}

/** The API's diff_pct: "+18.4%", "−7%", "0%", or "—" when there is no median to compare with. */
export function formatDiff(diffPct: number | null | undefined): string {
  if (diffPct === null || diffPct === undefined) return "—";
  const text = whole.format(Math.abs(diffPct));
  if (text === "0") return "0%";
  return `${diffPct > 0 ? "+" : MINUS}${text}%`;
}

export type DiffTone = "up" | "down" | "flat" | "none";

export function diffTone(diffPct: number | null | undefined): DiffTone {
  if (diffPct === null || diffPct === undefined) return "none";
  if (whole.format(Math.abs(diffPct)) === "0") return "flat";
  return diffPct > 0 ? "up" : "down";
}

/** Screen-reader words for a difference: "18.4% above the median". */
export function diffWords(diffPct: number | null | undefined): string {
  const tone = diffTone(diffPct);
  if (tone === "none") return "no median to compare with";
  if (tone === "flat") return "the same as the median";
  return `${whole.format(Math.abs(diffPct as number))}% ${tone === "up" ? "above" : "below"} the median`;
}

/**
 * The note when the figures are at a younger age than asked for (the API's requested_age differs
 * from age): "This post hasn't reached 7 d yet, so these are its figures at 24 h."
 */
export function youngerNote(
  performance: Pick<PostPerformance, "requested_age" | "age">,
  what: "figures" | "comparison",
): string | null {
  const requested = performance.requested_age;
  if (!requested || requested === performance.age) return null;
  return what === "figures"
    ? `This post hasn't reached ${AGE_LABEL[requested]} yet, so these are its figures ${atAge(performance.age)}.`
    : `This post hasn't reached ${AGE_LABEL[requested]} yet, so it's compared ${atAge(performance.age)}.`;
}

/** "Compared with 8 earlier Reels at 24 h" (agent-architecture §6: the answer states the baseline size). */
export function baselineText(comparison: Pick<PostComparison, "age" | "baseline" | "baseline_size" | "post">): string {
  const { baseline, baseline_size: size } = comparison;
  const what = baseline.same_format ? formatPlural(comparison.post.media_type) : "posts";
  const noun = size === 1 ? singular(what) : what;
  const scope = baseline.kind === "previous" && baseline.n ? ` (of the last ${baseline.n})` : "";
  const when = comparison.age === "lifetime" ? ", on lifetime figures" : ` ${atAge(comparison.age)}`;
  return `Compared with ${size} earlier ${noun}${scope}${when}`;
}

/** "figures at 24 h" or "lifetime figures". */
function figuresAt(age: AgeName): string {
  return age === "lifetime" ? "lifetime figures" : `figures ${atAge(age)}`;
}

function singular(what: string): string {
  if (what === "Reels") return "Reel";
  if (what === "feed posts") return "feed post";
  return "post";
}

/** TR-AGT-05: fewer than 3 comparable posts. No conclusion is drawn. */
export function notEnoughHistory(comparison: Pick<PostComparison, "age" | "baseline_size" | "baseline" | "post">): string {
  const what = comparison.baseline.same_format ? formatPlural(comparison.post.media_type) : "posts";
  const size = comparison.baseline_size;
  const have =
    size === 0
      ? `No earlier ${what} have ${figuresAt(comparison.age)} yet`
      : `Only ${size} earlier ${size === 1 ? singular(what) : what} ${size === 1 ? "has" : "have"} ${figuresAt(comparison.age)}`;
  return `${have}. Comparisons need at least 3.`;
}
