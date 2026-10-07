"use client";

import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutomationRuns } from "@/lib/api/queries";
import type { AutomationRun, RunResult } from "@/lib/api/types";
import { RESULT_LABEL, runMarkers } from "@/lib/automations/format";
import { emptyStates } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import { Badge } from "@/components/ui/badge";
import { CardInset } from "@/components/ui/card";
import type { Tone } from "@/lib/ui/tone";

const RESULTS = Object.keys(RESULT_LABEL) as RunResult[];
const ALL = "all";

const RESULT_TONE: Record<RunResult, Tone> = {
  sent: "success",
  queued: "brand",
  partial: "warning",
  failed: "danger",
  skipped_cooldown: "neutral",
  skipped_expired: "neutral",
  escalated: "warning",
  awaiting_reply: "brand",
  skipped_read_only: "neutral",
};

function contactLabel(run: AutomationRun): string {
  const contact = run.contact;
  if (!contact) return "Someone";
  return contact.display_name?.trim() || (contact.username ? `@${contact.username}` : "Someone");
}

/**
 * UX-SCR-12 runs: time, contact, what they wrote, the result ("Waiting for tap" under tap first)
 * and the tap and follow markers; a row opens the conversation.
 */
export function RunsPane({
  wid,
  slug,
  automationId,
  timeZone,
}: {
  wid: string;
  slug: string;
  automationId: string;
  timeZone: string;
}) {
  const [result, setResult] = useState<RunResult | null>(null);
  const runs = useAutomationRuns(wid, automationId, result);
  const items = runs.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-3">
      <Select value={result ?? ALL} onValueChange={(value) => setResult(value === ALL ? null : (value as RunResult))}>
        <SelectTrigger aria-label="Result" size="lg" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All results</SelectItem>
          {RESULTS.map((value) => (
            <SelectItem key={value} value={value}>
              {RESULT_LABEL[value]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {runs.isPending ? (
        <div aria-busy="true" aria-label="Loading runs" className="space-y-2">
          {Array.from({ length: 4 }, (_, i) => (
            <CardInset key={i} padding="compact" className="space-y-2">
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-3/4" />
            </CardInset>
          ))}
        </div>
      ) : runs.isError ? (
        <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
      ) : items.length === 0 ? (
        result ? (
          <EmptyState title="No runs with this result" body="Choose another result or All results." />
        ) : (
          <EmptyState {...emptyStates.automationRuns} />
        )
      ) : (
        <ul className="space-y-2" aria-label="Runs">
          {items.map((run) => (
            <li key={run.id}>
              <RunRow run={run} timeZone={timeZone} href={run.conversation_id ? (`/w/${slug}/inbox/${run.conversation_id}` as Route) : null} />
            </li>
          ))}
        </ul>
      )}
      {runs.hasNextPage ? (
        <Button variant="secondary" size="sm" className="w-full" onClick={() => void runs.fetchNextPage()} disabled={runs.isFetchingNextPage}>
          Show older runs
        </Button>
      ) : null}
    </div>
  );
}

function RunRow({ run, timeZone, href }: { run: AutomationRun; timeZone: string; href: Route | null }) {
  const markers = runMarkers(run, timeZone);
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium">{contactLabel(run)}</span>
        <Badge tone={RESULT_TONE[run.result]}>{RESULT_LABEL[run.result]}</Badge>
      </div>
      {run.trigger_text ? <p className="mt-1 line-clamp-2 text-sm text-fg-secondary">{run.trigger_text}</p> : null}
      {run.error ? <p className="mt-1 text-xs text-danger-fg">{run.error.message}</p> : null}
      <p className="mt-1 text-xs text-fg-secondary">
        {formatDayTime(run.created_at, timeZone)} · {run.trigger_kind === "dm" ? "DM" : "Comment"}
        {run.matched_keyword ? <> · &ldquo;{run.matched_keyword}&rdquo;</> : null}
      </p>
      {markers.length > 0 ? (
        <p data-testid="run-markers" className="mt-1.5 flex flex-wrap gap-1">
          {markers.map((marker) => (
            <Badge key={marker} className="tabular-nums">
              {marker}
            </Badge>
          ))}
        </p>
      ) : null}
    </>
  );
  return href ? (
    <CardInset asChild padding="compact" className="block hover:bg-hover">
      <Link href={href}>{body}</Link>
    </CardInset>
  ) : (
    <CardInset padding="compact">{body}</CardInset>
  );
}
