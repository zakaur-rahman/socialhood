"use client";

import { RotateCw } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { usePostComparison, usePostPerformance } from "@/lib/api/queries";
import type { AgeName, MetricComparison, PostComparison, PostPerformance, SocialAccount } from "@/lib/api/types";
import {
  AGE_LABEL,
  AGES,
  atAge,
  baselineText,
  diffTone,
  diffWords,
  formatDiff,
  formatMetric,
  METRIC_LABEL,
  METRICS,
  notEnoughHistory,
  youngerNote,
} from "@/lib/analytics/format";
import { accountLabel } from "@/lib/automations/accounts";
import { errorMessage } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

const TONE_TEXT = {
  up: "text-success",
  down: "text-danger-fg",
  flat: "text-fg-secondary",
  none: "text-fg-secondary",
} as const;

function InlineError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div role="alert" className="space-y-2 text-sm">
      <p className="text-fg-secondary">{errorMessage(error)}</p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RotateCw aria-hidden /> Try again
      </Button>
    </div>
  );
}

function Figures({
  performance,
  account,
  slug,
  timeZone,
  now,
}: {
  performance: PostPerformance;
  account: SocialAccount | undefined;
  slug: string;
  timeZone: string;
  now: Date;
}) {
  const { metrics } = performance;
  const younger = youngerNote(performance, "figures");
  const anyMissing = METRICS.some((metric) => metrics[metric] == null);
  const handle = account ? accountLabel(account) : "This account";

  return (
    <div className="space-y-3" data-testid="post-figures">
      {!performance.insights_granted ? (
        <div className="rounded-lg border border-warning/40 bg-warning-soft p-3 text-xs" data-testid="insights-unavailable">
          <p>
            {handle} didn&apos;t give Social Hood permission to read insights, so reach, views, shares and saves
            aren&apos;t available. Reconnect to allow it.
          </p>
          <Link
            href={`/w/${slug}/settings/connections` as Route}
            className="mt-1 inline-flex items-center font-medium text-brand-fg hover:underline pointer-coarse:min-h-10"
          >
            Reconnect
          </Link>
        </div>
      ) : null}

      {performance.captured_at ? (
        <>
          <p className="text-xs text-fg-secondary" data-testid="figures-age">
            {performance.age === "lifetime" ? "Lifetime figures" : `Figures ${atAge(performance.age)} after posting`} · Read{" "}
            <time dateTime={performance.captured_at}>{formatDayTime(performance.captured_at, timeZone, now)}</time>
          </p>
          {younger ? <p className="text-xs text-brand-fg">{younger}</p> : null}
          <dl className="grid grid-cols-2 gap-2">
            {METRICS.map((metric) => (
              <div
                key={metric}
                className={cn("rounded-lg bg-field px-3 py-2", metric === "engagement_rate" && "col-span-2")}
                data-metric={metric}
              >
                <dt className="text-xs text-fg-secondary">{METRIC_LABEL[metric]}</dt>
                <dd className="text-lg font-semibold tabular-nums">{formatMetric(metric, metrics[metric])}</dd>
              </div>
            ))}
          </dl>
          {performance.insights_granted && !performance.insights_final && metrics.reach != null ? (
            <p className="text-xs text-fg-secondary">Instagram can take up to 48 h to settle these numbers.</p>
          ) : null}
          {anyMissing && performance.insights_granted ? (
            <p className="text-xs text-fg-secondary">— means Instagram has no figure for this post at this age.</p>
          ) : null}
        </>
      ) : (
        <div className="space-y-1 text-sm" data-testid="no-figures">
          <p className="font-medium">No figures yet</p>
          <p className="text-xs text-fg-secondary">
            Social Hood reads a post&apos;s figures 1 h, 6 h, 24 h, 72 h, 7 days and 30 days after it&apos;s published.
            Posts published before you connected have figures only from then on.
          </p>
        </div>
      )}
    </div>
  );
}

function MetricRow({ row, baselineSize }: { row: MetricComparison; baselineSize: number }) {
  const tone = diffTone(row.diff_pct);
  return (
    <li className="flex items-start justify-between gap-3 py-2" data-metric={row.metric}>
      <div className="min-w-0">
        <p className="text-sm">{METRIC_LABEL[row.metric]}</p>
        <p className="text-xs text-fg-secondary">
          {formatMetric(row.metric, row.value)} vs median {formatMetric(row.metric, row.baseline_median)}
          {row.sample_size !== baselineSize ? ` of ${row.sample_size} ${row.sample_size === 1 ? "post" : "posts"}` : ""}
        </p>
      </div>
      <p className={cn("shrink-0 text-sm font-medium tabular-nums", TONE_TEXT[tone])} data-tone={tone}>
        <span aria-hidden>{formatDiff(row.diff_pct)}</span>
        <span className="sr-only">{diffWords(row.diff_pct)}</span>
      </p>
    </li>
  );
}

function Comparison({ comparison }: { comparison: PostComparison }) {
  if (!comparison.enough_history) {
    return (
      <div className="space-y-1" data-testid="not-enough-history">
        <p className="text-sm font-medium">Not enough history</p>
        <p className="text-xs text-fg-secondary">{notEnoughHistory(comparison)}</p>
        <p className="text-xs text-fg-secondary">
          Posts published before you connected have no early figures, so comparisons fill in as you post.
        </p>
      </div>
    );
  }
  const younger = youngerNote(comparison.post, "comparison");
  return (
    <div className="space-y-2" data-testid="comparison">
      <p className="text-xs text-fg-secondary" data-testid="baseline">
        {baselineText(comparison)}
      </p>
      {younger ? <p className="text-xs text-brand-fg">{younger}</p> : null}
      <ul className="divide-y divide-line-subtle" aria-label="Difference from the median">
        {comparison.metrics.map((row) => (
          <MetricRow key={row.metric} row={row} baselineSize={comparison.baseline_size} />
        ))}
      </ul>
    </div>
  );
}

/**
 * FR-ANL-02 on the post detail: the post's figures at an age (the age used is always stated), and
 * the comparison with the account's earlier posts at the same age (agent-architecture §6: baseline
 * size, "not enough history" below 3, per-metric difference). Numbers are shown as the API gives
 * them; nothing is computed here.
 */
export function PostPerformanceCard({
  wid,
  postId,
  account,
  slug,
  timeZone,
  now,
}: {
  wid: string;
  postId: string;
  account: SocialAccount | undefined;
  slug: string;
  timeZone: string;
  now: Date;
}) {
  const [age, setAge] = useState<AgeName | null>(null);
  const performance = usePostPerformance(wid, postId, age);
  const comparison = usePostComparison(wid, postId, age);
  // Without a choice, the API picks the latest window the post has reached and says which.
  const shown = age ?? performance.data?.age ?? null;

  return (
    <section aria-labelledby="post-performance-heading" className="space-y-4 rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 id="post-performance-heading" className={EYEBROW}>
          Performance
        </h2>
        <Select value={shown ?? ""} onValueChange={(value) => setAge(value as AgeName)}>
          <SelectTrigger aria-label="Age after posting" className="min-w-28">
            <SelectValue placeholder="Latest" />
          </SelectTrigger>
          <SelectContent>
            {AGES.map((value) => (
              <SelectItem key={value} value={value}>
                {value === "lifetime" ? AGE_LABEL[value] : `At ${AGE_LABEL[value]}`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div aria-busy={performance.isFetching || undefined} className={cn(performance.isPlaceholderData && "opacity-60")}>
        {performance.isPending ? (
          <div className="grid grid-cols-2 gap-2" aria-label="Loading figures">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
        ) : performance.isError ? (
          <InlineError error={performance.error} onRetry={() => void performance.refetch()} />
        ) : (
          <Figures performance={performance.data} account={account} slug={slug} timeZone={timeZone} now={now} />
        )}
      </div>

      <div className="space-y-2 border-t border-line pt-4">
        <h3 className="text-sm font-semibold">Compared with earlier posts</h3>
        <div className={cn(comparison.isPlaceholderData && "opacity-60")} aria-busy={comparison.isFetching || undefined}>
          {comparison.isPending ? (
            <div className="space-y-2" aria-label="Loading the comparison">
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </div>
          ) : comparison.isError ? (
            <InlineError error={comparison.error} onRetry={() => void comparison.refetch()} />
          ) : (
            <Comparison comparison={comparison.data} />
          )}
        </div>
      </div>
    </section>
  );
}
