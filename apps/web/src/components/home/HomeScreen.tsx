"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { SourceSheet, type SourceSheetMode } from "@/components/knowledge/SourceSheet";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, useOverview, useUpdateWorkspace, type OverviewQuery } from "@/lib/api/queries";
import type { Overview } from "@/lib/api/types";
import { errorMessage, greeting } from "@/lib/copy";
import { gapPrefill } from "@/lib/knowledge/prefill";
import { toastError } from "@/lib/toast-error";
import { dayKey } from "@/lib/tz";
import { useNow, useStoredString } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AccountHealth } from "./AccountHealth";
import { Checklist } from "./Checklist";
import { channelsConnected, channelsLine, formatSpan, periodLabel, periodPhrase, rangeHeading } from "./format";
import { KnowledgeGapBanner } from "./KnowledgeGapBanner";
import { MetricTiles, MetricTilesSkeleton } from "./MetricTiles";
import { PriorityQueue, PriorityQueueSkeleton } from "./PriorityQueue";
import { parseStoredRange, storedRange } from "./range";
import { RangeControl } from "./RangeControl";
import { SentimentCard } from "./SentimentCard";
import { TopIntentsCard } from "./TopIntentsCard";
import { TopPostsCard } from "./TopPostsCard";

/**
 * Home (UX-SCR-01, FR-HOME-01; redesigned, C-065): the greeting with the channels and the period,
 * the channels pill, 7 days / 30 days / Custom (remembered on this device) and refresh; the
 * onboarding checklist until dismissed; accounts to fix; the metric tiles with their Attention and
 * Fast labels; sentiment, the most commented posts and what customers asked about; open questions
 * with View thread and Train AI; and the Live Priority Queue. All from GET …/overview. Real data
 * only: a metric without data shows "—" and a hint, and nothing is shown that the API didn't count.
 */
export function HomeScreen() {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const now = useNow();
  const today = dayKey(now, workspace.timezone);
  const [stored, setStored] = useStoredString<string>(`socialhood:home-range:${workspace.id}`, "7d");
  const query = parseStoredRange(stored, today);
  const overview = useOverview(workspace.id, query);
  const update = useUpdateWorkspace(workspace.id);
  const [sheet, setSheet] = useState<SourceSheetMode | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const firstName = me.data?.name?.split(" ")[0];
  const title = me.data ? greeting(new Date(), firstName) : "Home";
  const canManage = workspace.role !== "agent";
  const data = overview.data;

  const dismiss = () =>
    update.mutate({ checklist_dismissed: true }, { onError: (error) => toastError(error) });

  const refresh = () => {
    setRefreshing(true);
    void overview.refetch().finally(() => setRefreshing(false));
  };

  const header = (
    <header className="mb-6 flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {data ? (
          <p className="mt-1 text-sm text-fg-secondary" data-testid="home-subtitle">
            {channelsLine(data.platforms_connected)}
            <span aria-hidden> · </span>
            <span className="text-brand-fg tabular-nums">
              {rangeHeading(data)} · {formatSpan(data.current.since, data.current.until)}
            </span>
          </p>
        ) : (
          <Skeleton className="mt-2 h-4 w-72 max-w-full" />
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {data ? (
          <span
            data-testid="channels-pill"
            className="inline-flex min-h-8 items-center gap-2 rounded-full border border-line px-3 text-xs font-medium pointer-coarse:min-h-10"
          >
            <span
              className={cn("size-2 rounded-full", data.accounts_connected > 0 ? "bg-success" : "bg-fg-secondary")}
              aria-hidden
            />
            {channelsConnected(data.accounts_connected)}
          </span>
        ) : null}
        <RangeControl value={query} today={today} onChange={(next: OverviewQuery) => setStored(storedRange(next))} />
        <Button
          variant="outline"
          size="icon"
          aria-label="Refresh"
          aria-busy={refreshing}
          disabled={refreshing || overview.isPending}
          onClick={refresh}
        >
          <RefreshCw className={cn(refreshing && "motion-safe:animate-spin")} aria-hidden />
        </Button>
      </div>
    </header>
  );

  return (
    <div className="mx-auto w-full max-w-[1200px] p-4 md:p-6">
      {header}
      {overview.isPending ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading Home">
          <MetricTilesSkeleton />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-56 rounded-xl" />
            ))}
          </div>
          <PriorityQueueSkeleton />
        </div>
      ) : !data ? (
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      ) : (
        <Body
          data={data}
          slug={workspace.slug}
          canManage={canManage}
          now={now}
          // While another range loads, the previous one stays on screen, dimmed.
          switching={overview.isPlaceholderData}
          staleError={overview.isError ? overview.error : null}
          onRetry={refresh}
          onDismissChecklist={dismiss}
          dismissing={update.isPending}
          onTrain={(gap) => setSheet(gapPrefill(gap))}
        />
      )}
      <SourceSheet mode={sheet} onOpenChange={(open) => (open ? undefined : setSheet(null))} />
    </div>
  );
}

function Body({
  data,
  slug,
  canManage,
  now,
  switching,
  staleError,
  onRetry,
  onDismissChecklist,
  dismissing,
  onTrain,
}: {
  data: Overview;
  slug: string;
  canManage: boolean;
  now: Date;
  switching: boolean;
  staleError: unknown;
  onRetry: () => void;
  onDismissChecklist: () => void;
  dismissing: boolean;
  onTrain: (gap: NonNullable<Overview["latest_gap"]>) => void;
}) {
  const connected = data.checklist.steps.some((step) => step.key === "connect_account" && step.done);
  const period = periodLabel(data.days);
  const within = periodPhrase(data);
  return (
    <div className="space-y-6">
      {staleError ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
          <p className="flex-1">Couldn&apos;t refresh: {errorMessage(staleError)} These are the last numbers that loaded.</p>
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
      {data.checklist.dismissed ? null : (
        <Checklist steps={data.checklist.steps} slug={slug} onDismiss={onDismissChecklist} dismissing={dismissing} />
      )}
      <AccountHealth accounts={data.accounts_needing_attention} slug={slug} canManage={canManage} />

      <div
        aria-busy={switching}
        className={cn("space-y-6 motion-safe:transition-opacity", switching && "opacity-60")}
        data-testid="overview"
      >
        <MetricTiles overview={data} slug={slug} connected={connected} now={now} />

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <SentimentCard messages={data.message_sentiment} comments={data.comment_sentiment} period={period} within={within} />
          <TopPostsCard posts={data.top_posts} engagement={data.top_posts_engagement} period={period} within={within} slug={slug} />
          <TopIntentsCard intents={data.top_intents} period={period} within={within} />
        </div>

        <KnowledgeGapBanner
          count={data.knowledge_gaps_open}
          topics={data.top_questions.map((question) => question.topic)}
          latest={data.latest_gap}
          slug={slug}
          canManage={canManage}
          onTrain={onTrain}
        />

        <PriorityQueue items={data.priority_queue} needsReply={data.needs_reply} slug={slug} now={now} />
      </div>
    </div>
  );
}
