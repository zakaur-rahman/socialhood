"use client";

import { ChevronRight, X } from "lucide-react";
import Link from "next/link";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useMemo, useState } from "react";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { creditsText, MODE_LABEL } from "@/lib/agent/format";
import { askHref } from "@/lib/agent/routes";
import { useAgentPolicy, useAgentRun, useAgentRunHistory } from "@/lib/api/queries";
import type { AgentPermissions, AgentRun } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { RunStatusChip, RunTrace, RunTraceSkeleton } from "./RunTrace";
import { useReturnFocus } from "./use-return-focus";

const PERMISSION_LABEL: Record<keyof AgentPermissions, string> = {
  send_replies: "Send replies",
  schedule_messages: "Schedule messages",
  schedule_posts: "Schedule posts",
  create_automations: "Create automations",
  delete_automations: "Delete automations",
  bulk_actions: "Bulk actions",
};

/**
 * Settings → Agent (agent-architecture.html §12): the agent's mode (read only in this release)
 * and the run history, where owners and admins open any run (FR-AGT-07).
 */
export function AgentSettingsPage() {
  const workspace = useCurrentWorkspace();
  if (workspace.role === "agent") {
    return (
      <EmptyState
        className="min-h-[60vh]"
        title="Run history is for owners and admins"
        body="Your own questions and answers are in Ask Social Hood."
        action={
          <Link href={askHref(workspace.slug)} className="text-sm text-brand-fg underline-offset-4 hover:underline">
            Open Ask Social Hood
          </Link>
        }
      />
    );
  }
  return (
    <PageFrame title="Ask Social Hood">
      <div className="max-w-3xl space-y-6">
        <PolicyCard />
        <RunHistory />
      </div>
    </PageFrame>
  );
}

function PolicyCard() {
  const workspace = useCurrentWorkspace();
  const policy = useAgentPolicy(workspace.id);
  return (
    <section aria-labelledby="agent-mode-heading" className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <h2 id="agent-mode-heading" className="text-base font-semibold">
        What it can do
      </h2>
      {policy.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Loading the agent's mode">
          <Skeleton className="h-3 w-1/3 bg-raised" />
          <Skeleton className="h-3 w-2/3 bg-raised" />
        </div>
      ) : policy.isError ? (
        <ErrorState error={policy.error} onRetry={() => void policy.refetch()} />
      ) : (
        <>
          <p className="text-sm">
            Mode: <span className="font-medium">{MODE_LABEL[policy.data.mode]}</span>
          </p>
          <p className="text-sm text-fg-secondary">
            {policy.data.mode === "read_only"
              ? "Ask Social Hood reads your posts, comments, conversations, automations and knowledge to answer. It can prepare a message, reply or automation for someone to finish, but it doesn't send, schedule or change anything itself."
              : "Writes follow the switches below and the member's role."}
          </p>
          <ul className="grid gap-x-4 gap-y-1 sm:grid-cols-2" aria-label="Agent permissions">
            {(Object.keys(PERMISSION_LABEL) as (keyof AgentPermissions)[]).map((key) => (
              <li key={key} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-fg-secondary">{PERMISSION_LABEL[key]}</span>
                <span className={policy.data.permissions[key] ? "text-success" : "text-fg-secondary"}>
                  {policy.data.permissions[key] ? "On" : "Off"}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** FR-AGT-07: every run, newest first; a row opens the run's full trace. */
export function RunHistory() {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const history = useAgentRunHistory(workspace.id);
  const items = useMemo(() => history.data?.pages.flatMap((page) => page.items) ?? [], [history.data]);
  const [openId, setOpenId] = useState<string | null>(null);

  let content;
  if (history.isPending) {
    content = (
      <ul aria-busy="true" aria-label="Loading runs">
        {Array.from({ length: 4 }, (_, i) => (
          <li key={i} className="space-y-2 border-t border-line-subtle px-4 py-3 first:border-t-0">
            <Skeleton className="h-3 w-2/3 bg-raised" />
            <Skeleton className="h-3 w-1/3 bg-raised" />
          </li>
        ))}
      </ul>
    );
  } else if (history.isError) {
    content = <ErrorState error={history.error} onRetry={() => void history.refetch()} />;
  } else if (items.length === 0) {
    content = (
      <EmptyState
        title="No questions yet"
        body="When someone asks Social Hood a question, the run shows here with every step it took."
      />
    );
  } else {
    content = (
      <>
        <ul aria-label="Runs" data-testid="run-history">
          {items.map((run) => (
            <li key={run.id} className="border-t border-line-subtle first:border-t-0">
              <RunRow run={run} now={now} onOpen={() => setOpenId(run.id)} />
            </li>
          ))}
        </ul>
        {history.hasNextPage ? (
          <div className="flex justify-center border-t border-line-subtle p-3">
            <Button
              variant="secondary"
              className="min-h-10 md:min-h-8"
              disabled={history.isFetchingNextPage}
              onClick={() => void history.fetchNextPage()}
            >
              {history.isFetchingNextPage ? "Loading…" : "Show older runs"}
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <section aria-labelledby="run-history-heading" className="rounded-xl border border-line bg-panel">
      <div className="border-b border-line p-4">
        <h2 id="run-history-heading" className="text-base font-semibold">
          Run history
        </h2>
        <p className="text-sm text-fg-secondary">Every question asked in this workspace: its steps, tools, results and credits.</p>
      </div>
      {content}
      <RunDetailSheet runId={openId} onClose={() => setOpenId(null)} />
    </section>
  );
}

function RunRow({ run, now, onOpen }: { run: AgentRun; now: Date; onOpen: () => void }) {
  const workspace = useCurrentWorkspace();
  const time = relativeTime(run.created_at, now);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-white/5"
      aria-label={`Open the run: ${run.request}`}
    >
      <span className="min-w-0 flex-1 space-y-1">
        <span className="line-clamp-2 block text-sm break-words">{run.request}</span>
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-secondary">
          <RunStatusChip status={run.status} />
          <span>{run.requested_by?.name ?? "Former member"}</span>
          <span aria-hidden>·</span>
          <time dateTime={run.created_at} title={formatDayTime(run.created_at, workspace.timezone, now)}>
            {time === "now" ? "just now" : time}
          </time>
          <span aria-hidden>·</span>
          <span className="tabular-nums">{creditsText(run.credits)}</span>
        </span>
      </span>
      <ChevronRight className="size-4 shrink-0 text-fg-secondary" aria-hidden />
    </button>
  );
}

/** One run's trace in a side sheet (full screen on phones). */
function RunDetailSheet({ runId, onClose }: { runId: string | null; onClose: () => void }) {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const run = useAgentRun(workspace.id, runId, runId !== null);
  const returnFocus = useReturnFocus();
  return (
    <DialogPrimitive.Root open={runId !== null} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 duration-200 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 motion-reduce:animate-none" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onOpenAutoFocus={returnFocus.onOpenAutoFocus}
          onCloseAutoFocus={returnFocus.onCloseAutoFocus}
          className="fixed inset-0 z-50 flex flex-col bg-panel shadow-xl outline-none duration-200 data-open:animate-in data-open:slide-in-from-right-10 data-closed:animate-out data-closed:slide-out-to-right-10 motion-reduce:animate-none md:inset-y-0 md:right-0 md:left-auto md:w-[560px] md:border-l md:border-line"
          data-testid="run-detail"
        >
          <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line pr-2 pl-4">
            <DialogPrimitive.Title className="min-w-0 flex-1 truncate text-base font-semibold">Run</DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="icon" className="size-10 text-fg-secondary md:size-8" aria-label="Close">
                <X aria-hidden />
              </Button>
            </DialogPrimitive.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {run.isPending ? (
              <RunTraceSkeleton />
            ) : run.isError ? (
              <ErrorState error={run.error} onRetry={() => void run.refetch()} />
            ) : (
              <RunTrace run={run.data} slug={workspace.slug} timeZone={workspace.timezone} now={now} onNavigate={onClose} />
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
