"use client";

import {
  CalendarClock,
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  Info,
  Layers,
  Lock,
  MessageSquareText,
  Reply,
  Search,
  ShieldCheck,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { SectionLabel, SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { creditsText, MODE_LABEL } from "@/lib/agent/format";
import { askHref } from "@/lib/agent/routes";
import { useAgentPolicy, useAgentRun, useAgentRunHistory, useBilling, usageMeter } from "@/lib/api/queries";
import type { AgentPermissions, AgentRun, AgentRunStatus } from "@/lib/api/types";
import { shortDate } from "@/lib/copy";
import { relativeTime } from "@/lib/time";
import { formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { RunStatusChip, RunTrace, RunTraceSkeleton } from "./RunTrace";
import { useReturnFocus } from "./use-return-focus";

/** Each write capability of the agent policy (schemas/agent.py AgentPermissions), in words. */
const CAPABILITIES: Record<keyof AgentPermissions, { label: string; hint: string; icon: ReactNode }> = {
  send_replies: { label: "Send replies", hint: "Reply to messages and comments", icon: <Reply /> },
  schedule_messages: { label: "Schedule messages", hint: "Schedule messages to customers", icon: <CalendarClock /> },
  schedule_posts: { label: "Schedule posts", hint: "Schedule and publish posts", icon: <CalendarPlus /> },
  create_automations: { label: "Create automations", hint: "Create and turn on automations", icon: <Workflow /> },
  delete_automations: { label: "Delete automations", hint: "Remove automations", icon: <Trash2 /> },
  bulk_actions: { label: "Bulk actions", hint: "Change many items at once", icon: <Layers /> },
};

/**
 * The run history's chips (C-066) as run statuses: Answered is a full or partial answer, Action
 * needed a run waiting for someone's approval (R2), Failed a run that failed or expired. All
 * also lists runs still working and cancelled ones.
 */
export const RUN_FILTERS: readonly { value: string; label: string; statuses: readonly AgentRunStatus[] }[] = [
  { value: "all", label: "All", statuses: [] },
  { value: "answered", label: "Answered", statuses: ["succeeded", "partial"] },
  { value: "action", label: "Action needed", statuses: ["awaiting_approval"] },
  { value: "failed", label: "Failed", statuses: ["failed", "expired"] },
];

/**
 * Settings → Agent (agent-architecture.html §12, C-066): what Ask Social Hood may do (read only
 * in this release, every write capability off and locked) and the run history, where owners and
 * admins search, filter and open any run's trace (FR-AGT-07).
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
    <SettingsFrame
      header={
        <SettingsPageHeader
          variant="card"
          label="Assistant"
          title="Ask Social Hood"
          description="What the assistant may do in this workspace, and every question it has answered: its steps, tools, results and credits."
          actions={<CreditsStat />}
        />
      }
    >
      <PolicyCard />
      <RunHistory />
    </SettingsFrame>
  );
}

/** This period's AI credits, which every run uses (GET …/billing). Nothing until it loads. */
function CreditsStat() {
  const workspace = useCurrentWorkspace();
  const billing = useBilling(workspace.id);
  const credits = usageMeter(billing.data, "ai_credits");
  if (!credits || typeof credits.limit !== "number") return null;
  const count = new Intl.NumberFormat("en-US");
  return (
    <div className="rounded-xl border border-line-subtle bg-field/60 px-4 py-2.5 text-right">
      <p className="text-[11px] font-semibold tracking-[0.12em] text-fg-secondary uppercase">AI credits</p>
      <p className="text-sm tabular-nums">
        <span className="text-lg font-semibold text-brand-fg">{count.format(credits.used)}</span>
        <span className="text-fg-secondary"> / {count.format(credits.limit)}</span>
      </p>
      {credits.period_end ? (
        <p className="text-xs text-fg-secondary">Resets on {shortDate(credits.period_end)}</p>
      ) : null}
    </div>
  );
}

function PolicyCard() {
  const workspace = useCurrentWorkspace();
  const policy = useAgentPolicy(workspace.id);
  const mode = policy.data?.mode;
  return (
    <SettingsCard
      id="agent-mode"
      icon={<ShieldCheck />}
      title="Capabilities & permissions"
      description="What Ask Social Hood can do on its own. Writes arrive in a later release."
      aside={
        mode ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
            <ShieldCheck className="size-3.5" aria-hidden />
            Mode: <span>{MODE_LABEL[mode]}</span>
          </span>
        ) : null
      }
    >
      {policy.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Loading the agent's mode">
          <Skeleton className="h-3 w-1/3 bg-raised" />
          <Skeleton className="h-3 w-2/3 bg-raised" />
        </div>
      ) : policy.isError ? (
        <ErrorState error={policy.error} onRetry={() => void policy.refetch()} />
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-line-subtle bg-field/60 p-4">
            <SectionLabel className="flex items-center gap-1.5 text-brand-fg">
              <Info className="size-3.5" aria-hidden />
              Operational bounds
            </SectionLabel>
            <p className="mt-2 text-sm">
              {policy.data.mode === "read_only"
                ? "Ask Social Hood reads your posts, comments, conversations, automations and knowledge to answer. It can prepare a message, reply or automation for someone to finish, but it doesn't send, schedule or change anything itself."
                : "Writes follow the switches below and the member's role."}
            </p>
          </div>
          <ul className="grid gap-2 md:grid-cols-2" aria-label="Agent permissions">
            {(Object.keys(CAPABILITIES) as (keyof AgentPermissions)[]).map((key) => {
              const on = policy.data.permissions[key];
              const capability = CAPABILITIES[key];
              return (
                <li key={key} className="flex min-h-14 items-center gap-3 rounded-xl border border-line-subtle bg-field/60 p-3">
                  <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-lg bg-raised text-fg-secondary [&_svg]:size-4">
                    {capability.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{capability.label}</p>
                    <p className="text-xs text-fg-secondary">{capability.hint}</p>
                  </div>
                  {on ? (
                    <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">On</span>
                  ) : (
                    <span className="flex shrink-0 flex-col items-end gap-0.5">
                      <span className="inline-flex items-center gap-1 rounded-full bg-raised px-2 py-0.5 text-xs font-medium text-fg-secondary">
                        <Lock className="size-3" aria-hidden />
                        <span>Off</span>
                      </span>
                      {policy.data.mode === "read_only" ? (
                        <span className="text-[11px] text-fg-secondary">Coming later</span>
                      ) : null}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </SettingsCard>
  );
}

/** The search box's text once typing pauses, so each keystroke isn't a request. */
function useDebounced(value: string, ms = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

/**
 * FR-AGT-07: every run, newest first; a row opens the run's full trace. C-066: search the
 * requests, filter by outcome (both in the API: GET …/agent/runs?status&q), page through.
 */
export function RunHistory() {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const [filter, setFilter] = useState("all");
  const [text, setText] = useState("");
  const q = useDebounced(text).trim();
  const statuses = RUN_FILTERS.find((option) => option.value === filter)?.statuses ?? [];
  const history = useAgentRunHistory(workspace.id, true, { statuses, q });
  const items = useMemo(() => history.data?.pages.flatMap((page) => page.items) ?? [], [history.data]);
  // A new search or filter starts again from its first page.
  const view = `${filter}|${q}`;
  const [paging, setPaging] = useState({ view, page: 0 });
  const page = paging.view === view ? paging.page : 0;
  const setPage = (update: (current: number) => number) => setPaging({ view, page: update(page) });
  const [openId, setOpenId] = useState<string | null>(null);
  const narrowed = filter !== "all" || q !== "";

  // A page here is a page of the API (10 runs); Next reads the next one when it isn't loaded yet.
  const pages = history.data?.pages ?? [];
  const shown = pages[page]?.items ?? [];
  const start = pages.slice(0, page).reduce((sum, loaded) => sum + loaded.items.length, 0);
  const hasNext = page + 1 < pages.length || Boolean(history.hasNextPage);
  const next = async () => {
    if (page + 1 >= pages.length) await history.fetchNextPage();
    setPage((current) => current + 1);
  };

  let content;
  if (history.isPending) {
    content = (
      <ul aria-busy="true" aria-label="Loading runs" className="space-y-2">
        {Array.from({ length: 4 }, (_, i) => (
          <li key={i} className="space-y-2 rounded-xl border border-line-subtle p-4">
            <Skeleton className="h-3 w-2/3 bg-raised" />
            <Skeleton className="h-3 w-1/3 bg-raised" />
          </li>
        ))}
      </ul>
    );
  } else if (history.isError) {
    content = <ErrorState error={history.error} onRetry={() => void history.refetch()} />;
  } else if (items.length === 0) {
    content = narrowed ? (
      <EmptyState
        title="No runs match"
        body="Try other words or another filter."
        action={
          <Button
            variant="secondary"
            className="min-h-10"
            onClick={() => {
              setText("");
              setFilter("all");
            }}
          >
            Show all runs
          </Button>
        }
      />
    ) : (
      <EmptyState
        title="No questions yet"
        body="When someone asks Social Hood a question, the run shows here with every step it took."
      />
    );
  } else {
    content = (
      <>
        <ul aria-label="Runs" data-testid="run-history" className="space-y-2">
          {shown.map((run) => (
            <li key={run.id}>
              <RunRow run={run} now={now} onOpen={() => setOpenId(run.id)} />
            </li>
          ))}
        </ul>
        <nav aria-label="Run history pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-fg-secondary tabular-nums">
            Showing {start + 1}–{start + shown.length}
            {history.hasNextPage ? "" : ` of ${items.length}`} · Page {page + 1}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="min-h-10 md:min-h-9"
              aria-label="Previous page"
              disabled={page === 0}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              <ChevronLeft aria-hidden /> Previous
            </Button>
            <Button
              variant="secondary"
              className="min-h-10 md:min-h-9"
              aria-label="Next page"
              disabled={!hasNext || history.isFetchingNextPage}
              onClick={() => void next()}
            >
              {history.isFetchingNextPage ? "Loading…" : "Next"} <ChevronRight aria-hidden />
            </Button>
          </div>
        </nav>
      </>
    );
  }

  return (
    <SettingsCard
      id="run-history"
      icon={<MessageSquareText />}
      title="Run history"
      description="Every question asked in this workspace: its steps, tools, results and credits."
    >
      <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary" aria-hidden />
          <Input
            type="search"
            aria-label="Search runs"
            placeholder="Search questions"
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-h-10 pl-9"
          />
        </div>
        <ToggleGroup value={filter} onValueChange={setFilter} aria-label="Filter runs" size="sm" className="overflow-x-auto lg:w-auto">
          {RUN_FILTERS.map((option) => (
            <ToggleGroupItem key={option.value} value={option.value} className="shrink-0">
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      {content}
      <RunDetailSheet runId={openId} onClose={() => setOpenId(null)} />
    </SettingsCard>
  );
}

function RunRow({ run, now, onOpen }: { run: AgentRun; now: Date; onOpen: () => void }) {
  const workspace = useCurrentWorkspace();
  const time = relativeTime(run.created_at, now);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex min-h-14 w-full items-center gap-3 rounded-xl border border-line-subtle bg-field/60 px-4 py-3 text-left outline-none hover:bg-raised focus-visible:ring-2 focus-visible:ring-brand"
      aria-label={`Open the run: ${run.request}`}
    >
      <span aria-hidden className="hidden size-9 shrink-0 place-items-center rounded-lg bg-raised text-fg-secondary sm:grid">
        <MessageSquareText className="size-4" />
      </span>
      <span className="min-w-0 flex-1 space-y-1">
        <span className="line-clamp-2 block text-sm font-medium break-words">{run.request}</span>
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-secondary">
          <RunStatusChip status={run.status} />
          <span>{run.requested_by?.name ?? "Former member"}</span>
          <span aria-hidden>·</span>
          <time dateTime={run.created_at} title={formatDayTime(run.created_at, workspace.timezone, now)}>
            {time === "now" ? "just now" : time}
          </time>
        </span>
      </span>
      <span className="shrink-0 rounded-md bg-raised px-2 py-0.5 text-xs text-fg-secondary tabular-nums">
        {creditsText(run.credits)}
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
