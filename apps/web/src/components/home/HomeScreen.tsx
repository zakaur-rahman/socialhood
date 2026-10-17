"use client";

import { PAGE_TITLE } from "@/styles/tokens";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Suspense, useEffect, useState } from "react";

import { ProTrialOffer } from "@/components/billing/ProTrialOffer";
import { SourceSheet, type SourceSheetMode } from "@/components/knowledge/SourceSheet";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { markAllSetShown, useAllSetPhase } from "./checklist-state";
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
 * onboarding checklist until dismissed (once complete, for one session only); accounts to fix; the
 * metric tiles with their Attention and Fast labels; sentiment, the most commented posts and what customers asked about; open questions
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

  const dismiss = () => update.mutate({ checklist_dismissed: true }, { onError: (error) => toastError(error) });

  const refresh = () => {
    setRefreshing(true);
    void overview.refetch().finally(() => setRefreshing(false));
  };

  const header = (
    <header className="mb-6 flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <h1 className={PAGE_TITLE}>{title}</h1>
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
          <Badge data-testid="channels-pill" size="md" className="gap-2">
            <span
              className={cn("size-2 rounded-full", data.accounts_connected > 0 ? "bg-success" : "bg-fg-secondary")}
              aria-hidden
            />
            {channelsConnected(data.accounts_connected)}
          </Badge>
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
      {/* `?plan=pro` from the pricing page opens the upgrade dialog once (UI-063). */}
      <Suspense fallback={null}>
        <ProTrialOffer />
      </Suspense>
      {header}
      {overview.isPending ? (
        <div role="status" className="space-y-6" aria-busy="true" aria-label="Loading Home">
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
          workspaceId={workspace.id}
          canManage={canManage}
          now={now}
          // While another range loads, the previous one stays on screen: busy, its numbers in the
          // secondary colour (no opacity on text).
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
  workspaceId,
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
  workspaceId: string;
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
  // A finished checklist says "You're all set" for this session, then goes (UI-058); Show setup
  // checklist in the workspace menu brings it back.
  const allDone = data.checklist.steps.every((step) => step.done);
  const phase = useAllSetPhase(workspaceId);
  const showAllSet = allDone && !data.checklist.dismissed;
  useEffect(() => {
    if (showAllSet && phase === "fresh") markAllSetShown(workspaceId);
  }, [showAllSet, phase, workspaceId]);
  const showChecklist = !data.checklist.dismissed && !(allDone && phase === "past");
  return (
    <div className="space-y-6">
      {staleError ? (
        <Alert
          tone="warning"
          icon={<AlertTriangle />}
          action={<AlertAction onClick={onRetry}>Try again</AlertAction>}
          data-testid="stale-numbers"
        >
          Couldn&apos;t refresh: {errorMessage(staleError)} These are the last numbers that loaded.
        </Alert>
      ) : null}
      {showChecklist ? (
        <Checklist steps={data.checklist.steps} slug={slug} onDismiss={onDismissChecklist} dismissing={dismissing} />
      ) : null}
      <AccountHealth accounts={data.accounts_needing_attention} slug={slug} canManage={canManage} />

      <div aria-busy={switching} className="group/overview space-y-6" data-testid="overview">
        {switching ? (
          <p role="status" className="sr-only">
            Loading the new period
          </p>
        ) : null}
        <MetricTiles overview={data} slug={slug} connected={connected} now={now} />

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <SentimentCard
            messages={data.message_sentiment}
            comments={data.comment_sentiment}
            period={period}
            within={within}
          />
          <TopPostsCard
            posts={data.top_posts}
            engagement={data.top_posts_engagement}
            period={period}
            within={within}
            slug={slug}
          />
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
