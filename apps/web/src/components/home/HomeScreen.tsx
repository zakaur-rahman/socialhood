"use client";

import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useMe, useOverview, useUpdateWorkspace } from "@/lib/api/queries";
import { errorMessage, greeting } from "@/lib/copy";
import { useStoredString } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AccountHealth } from "./AccountHealth";
import { Checklist } from "./Checklist";
import { formatSpan, RANGE_LABEL, RANGES, type OverviewRange } from "./format";
import { KnowledgeGapsRow } from "./KnowledgeGapsRow";
import { MetricTiles, MetricTilesSkeleton } from "./MetricTiles";
import { SentimentCard } from "./SentimentCard";
import { TopIntentsCard } from "./TopIntentsCard";
import { TopPostsCard } from "./TopPostsCard";

function isRange(value: string): value is OverviewRange {
  return (RANGES as string[]).includes(value);
}

/**
 * Home (UX-SCR-01, FR-HOME-01): greeting, the onboarding checklist until dismissed, the metric
 * tiles, sentiment, the most commented posts, what customers asked about, open questions and
 * account health, all from GET …/overview over 7 or 30 days (remembered on this device). Real
 * data only: a metric without data shows "—" and a hint.
 */
export function HomeScreen() {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const [stored, setRange] = useStoredString<OverviewRange>(`socialhood:home-range:${workspace.id}`, "7d");
  const range: OverviewRange = isRange(stored) ? stored : "7d";
  const overview = useOverview(workspace.id, range);
  const update = useUpdateWorkspace(workspace.id);

  const firstName = me.data?.name?.split(" ")[0];
  const title = me.data ? greeting(new Date(), firstName) : "Home";
  const canManage = workspace.role !== "agent";

  const dismiss = () =>
    update.mutate({ checklist_dismissed: true }, { onError: (error) => toast.error(errorMessage(error)) });

  if (overview.isPending) {
    return (
      <PageFrame title={title}>
        <div className="space-y-6" aria-busy="true">
          <Skeleton className="h-10 w-full max-w-sm rounded-lg bg-panel" />
          <MetricTilesSkeleton />
          <div className="grid gap-3 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-48 rounded-xl bg-panel" />
            ))}
          </div>
        </div>
      </PageFrame>
    );
  }
  if (overview.isError) {
    return (
      <PageFrame title={title}>
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      </PageFrame>
    );
  }

  const data = overview.data;
  const connected = data.checklist.steps.some((step) => step.key === "connect_account" && step.done);
  // While another range loads, the previous one stays on screen, dimmed.
  const switching = overview.isPlaceholderData;
  return (
    <PageFrame title={title}>
      <div className="space-y-6">
        {data.checklist.dismissed ? null : (
          <Checklist steps={data.checklist.steps} slug={workspace.slug} onDismiss={dismiss} dismissing={update.isPending} />
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-fg-secondary">
            Last {RANGE_LABEL[data.range]}
            <span className="tabular-nums"> · {formatSpan(data.current.since, data.current.until)}</span>
          </p>
          <ToggleGroup
            aria-label="Period"
            value={range}
            onValueChange={(value) => {
              if (isRange(value)) setRange(value);
            }}
            className="w-auto"
          >
            {RANGES.map((option) => (
              <ToggleGroupItem key={option} value={option} className="min-h-10 px-3 md:min-h-8">
                {RANGE_LABEL[option]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        <div
          aria-busy={switching}
          className={cn("space-y-6 transition-opacity", switching && "opacity-60")}
          data-testid="overview"
        >
          <MetricTiles overview={data} slug={workspace.slug} connected={connected} />

          <div className="grid gap-3 lg:grid-cols-3">
            <SentimentCard messages={data.message_sentiment} comments={data.comment_sentiment} range={data.range} />
            <TopPostsCard posts={data.top_posts} range={data.range} slug={workspace.slug} />
            <TopIntentsCard intents={data.top_intents} range={data.range} />
          </div>

          {canManage ? (
            <KnowledgeGapsRow
              count={data.knowledge_gaps_open}
              slug={workspace.slug}
              topics={data.top_questions.map((question) => question.topic)}
            />
          ) : null}
          <AccountHealth accounts={data.accounts_needing_attention} slug={workspace.slug} canManage={canManage} />
        </div>
      </div>
    </PageFrame>
  );
}
