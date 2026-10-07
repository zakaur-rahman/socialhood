"use client";

import { History, LoaderCircle, SquarePen } from "lucide-react";
import { Fragment, useMemo } from "react";

import { SELECTED_ROW } from "@/components/shell/sidebar-styles";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { groupThreads, isActive } from "@/lib/agent/format";
import { useAskStore } from "@/lib/agent/store";
import { useAgentThreads } from "@/lib/api/queries";
import type { AgentThread } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";
import { EYEBROW } from "@/styles/tokens";

const GROUP_LABEL = cn(EYEBROW, "px-2.5 pb-1");

function useThreadGroups(wid: string, now: Date) {
  const { timezone } = useCurrentWorkspace();
  const threads = useAgentThreads(wid);
  const items = useMemo(() => threads.data?.pages.flatMap((page) => page.items) ?? [], [threads.data]);
  const groups = useMemo(() => groupThreads(items, timezone, now), [items, timezone, now]);
  return { threads, items, groups };
}

/** One line: a spinner while it works, the title, the question count when more than one, the time. */
function ThreadLine({ thread, now }: { thread: AgentThread; now: Date }) {
  const time = relativeTime(thread.last_run_at, now);
  return (
    <>
      {isActive(thread.last_status) ? (
        <LoaderCircle className="size-3.5 shrink-0 text-brand-fg motion-safe:animate-spin" aria-label="Working" />
      ) : null}
      <span className="min-w-0 flex-1 truncate">{thread.title}</span>
      {/* The count takes the row's text colour: secondary text on its fill over a hovered or
          selected row would be under 4.5:1, and those rows turn their text to `fg`. */}
      {thread.run_count > 1 ? (
        <span className="shrink-0 rounded-full bg-hover px-1.5 text-2xs leading-5 tabular-nums">
          <span aria-hidden>{thread.run_count}</span>
          <span className="sr-only">{thread.run_count} questions</span>
        </span>
      ) : null}
      <span className="shrink-0 text-xs text-fg-secondary tabular-nums">{time}</span>
    </>
  );
}

/** Start a new thread: the next question begins a fresh conversation. */
export function NewThreadButton({
  wid,
  onStart,
  iconOnly = false,
}: {
  wid: string;
  onStart?: () => void;
  iconOnly?: boolean;
}) {
  const setThread = useAskStore((state) => state.setThread);
  const start = () => {
    setThread(wid, null);
    onStart?.();
  };
  if (iconOnly) {
    return (
      <Button variant="ghost" size="icon" className="text-fg-secondary" aria-label="New thread" onClick={start}>
        <SquarePen aria-hidden />
      </Button>
    );
  }
  return (
    <Button variant="secondary" size="xl" className="w-full justify-start gap-2 px-3" onClick={start}>
      <SquarePen aria-hidden /> New thread
    </Button>
  );
}

/** The panel's (and phones') thread picker: New thread, then recent threads grouped by day. */
export function ThreadMenu({ wid, now, onPick }: { wid: string; now: Date; onPick?: () => void }) {
  const current = useAskStore((state) => state.threads[wid] ?? null);
  const setThread = useAskStore((state) => state.setThread);
  const { threads, items, groups } = useThreadGroups(wid, now);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="text-fg-secondary" aria-label="Threads">
          <History aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      {/* A fixed width, so long titles truncate; the primitive caps it at the space beside the trigger. */}
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuItem
          onSelect={() => {
            setThread(wid, null);
            onPick?.();
          }}
          className="gap-2 font-medium"
        >
          <SquarePen aria-hidden /> New thread
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {threads.isPending ? (
          <div className="space-y-2 p-2" aria-busy="true" aria-label="Loading threads">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ) : threads.isError ? (
          <p className="p-2 text-xs text-danger-fg">Threads didn&apos;t load. Try again in a moment.</p>
        ) : items.length === 0 ? (
          <p className="p-2 text-xs text-fg-secondary">No threads yet. Your questions start one.</p>
        ) : (
          groups.map(({ group, items: groupItems }, index) => (
            <Fragment key={group}>
              {index > 0 ? <DropdownMenuSeparator /> : null}
              <DropdownMenuLabel className={cn(GROUP_LABEL, "pt-1.5")}>{group}</DropdownMenuLabel>
              {groupItems.slice(0, 20).map((thread) => {
                const selected = thread.id === current;
                return (
                  <DropdownMenuItem
                    key={thread.id}
                    onSelect={() => {
                      setThread(wid, thread.id);
                      onPick?.();
                    }}
                    aria-current={selected ? "true" : undefined}
                    className={cn("gap-2", selected && SELECTED_ROW)}
                  >
                    <ThreadLine thread={thread} now={now} />
                  </DropdownMenuItem>
                );
              })}
            </Fragment>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** The Ask page's thread history (≥ 1024 px): every thread, grouped by day, one line each. */
export function ThreadList({ wid, now }: { wid: string; now: Date }) {
  const current = useAskStore((state) => state.threads[wid] ?? null);
  const setThread = useAskStore((state) => state.setThread);
  const { threads, items, groups } = useThreadGroups(wid, now);

  if (threads.isPending) {
    return (
      <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading threads">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-3 w-4/5" />
        ))}
      </div>
    );
  }
  if (threads.isError) return <ErrorState error={threads.error} onRetry={() => void threads.refetch()} />;
  if (items.length === 0) {
    return <p className="px-4 py-3 text-sm text-fg-secondary">No threads yet. Your first question starts one.</p>;
  }
  return (
    <nav aria-label="Threads" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
      {groups.map(({ group, items: groupItems }) => (
        <div key={group} role="group" aria-label={group} className="pt-3">
          <h3 className={GROUP_LABEL} aria-hidden>
            {group}
          </h3>
          <ul className="space-y-0.5">
            {groupItems.map((thread) => {
              const selected = thread.id === current;
              return (
                <li key={thread.id}>
                  <button
                    type="button"
                    onClick={() => setThread(wid, thread.id)}
                    aria-current={selected ? "true" : undefined}
                    title={thread.title}
                    className={cn(
                      "relative flex min-h-9 w-full items-center gap-2 rounded-lg px-2.5 text-left text-sm text-fg-secondary hover:bg-hover hover:text-fg pointer-coarse:min-h-10",
                      selected && SELECTED_ROW,
                    )}
                  >
                    <ThreadLine thread={thread} now={now} />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {threads.hasNextPage ? (
        <div className="px-1 pt-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            disabled={threads.isFetchingNextPage}
            onClick={() => void threads.fetchNextPage()}
          >
            {threads.isFetchingNextPage ? "Loading…" : "Show older threads"}
          </Button>
        </div>
      ) : null}
    </nav>
  );
}
