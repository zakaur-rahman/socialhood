"use client";

import { History, LoaderCircle, SquarePen } from "lucide-react";
import { useMemo } from "react";

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
import { isActive } from "@/lib/agent/format";
import { useAskStore } from "@/lib/agent/store";
import { useAgentThreads } from "@/lib/api/queries";
import type { AgentThread } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

function useThreadItems(wid: string, enabled = true) {
  const threads = useAgentThreads(wid, enabled);
  const items = useMemo(() => threads.data?.pages.flatMap((page) => page.items) ?? [], [threads.data]);
  return { threads, items };
}

function ThreadMeta({ thread, now }: { thread: AgentThread; now: Date }) {
  const questions = thread.run_count === 1 ? "1 question" : `${thread.run_count} questions`;
  const time = relativeTime(thread.last_run_at, now);
  return (
    <span className="flex items-center gap-1.5 text-xs text-fg-secondary">
      {isActive(thread.last_status) ? (
        <LoaderCircle className="size-3 text-brand-fg motion-safe:animate-spin" aria-label="Working" />
      ) : null}
      {questions} · {time === "now" ? "just now" : time}
    </span>
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
      <Button
        variant="ghost"
        size="icon"
        className="size-10 text-fg-secondary md:size-8"
        aria-label="New thread"
        onClick={start}
      >
        <SquarePen aria-hidden />
      </Button>
    );
  }
  return (
    <Button variant="secondary" className="min-h-10 md:min-h-8" onClick={start}>
      <SquarePen aria-hidden /> New thread
    </Button>
  );
}

/** The panel's (and phones') thread picker: recent threads in a menu. */
export function ThreadMenu({ wid, now, onPick }: { wid: string; now: Date; onPick?: () => void }) {
  const current = useAskStore((state) => state.threads[wid] ?? null);
  const setThread = useAskStore((state) => state.setThread);
  const { threads, items } = useThreadItems(wid);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-10 text-fg-secondary md:size-8" aria-label="Threads">
          <History aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 max-w-[calc(100vw-2rem)] border-line bg-panel">
        <DropdownMenuLabel className="text-xs text-fg-secondary">Recent threads</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {threads.isPending ? (
          <div className="space-y-2 p-2" aria-busy="true" aria-label="Loading threads">
            <Skeleton className="h-3 w-3/4 bg-raised" />
            <Skeleton className="h-3 w-1/2 bg-raised" />
          </div>
        ) : threads.isError ? (
          <p className="p-2 text-xs text-danger-fg">Threads didn&apos;t load. Try again in a moment.</p>
        ) : items.length === 0 ? (
          <p className="p-2 text-xs text-fg-secondary">No threads yet. Your questions start one.</p>
        ) : (
          items.slice(0, 15).map((thread) => (
            <DropdownMenuItem
              key={thread.id}
              onSelect={() => {
                setThread(wid, thread.id);
                onPick?.();
              }}
              className={cn("flex-col items-start gap-0.5", thread.id === current && "bg-raised")}
              aria-current={thread.id === current ? "true" : undefined}
            >
              <span className="line-clamp-2 text-sm break-words">{thread.title}</span>
              <ThreadMeta thread={thread} now={now} />
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** The Ask page's thread history (≥ 1024 px): every thread, most recent activity first. */
export function ThreadList({ wid, now }: { wid: string; now: Date }) {
  const current = useAskStore((state) => state.threads[wid] ?? null);
  const setThread = useAskStore((state) => state.setThread);
  const { threads, items } = useThreadItems(wid);

  if (threads.isPending) {
    return (
      <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading threads">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="space-y-1.5">
            <Skeleton className="h-3 w-4/5 bg-raised" />
            <Skeleton className="h-3 w-1/3 bg-raised" />
          </div>
        ))}
      </div>
    );
  }
  if (threads.isError) return <ErrorState error={threads.error} onRetry={() => void threads.refetch()} />;
  if (items.length === 0) {
    return <p className="p-4 text-sm text-fg-secondary">No threads yet. Your first question starts one.</p>;
  }
  return (
    <nav aria-label="Threads" className="min-h-0 flex-1 overflow-y-auto p-2">
      <ul className="space-y-0.5">
        {items.map((thread) => {
          const selected = thread.id === current;
          return (
            <li key={thread.id}>
              <button
                type="button"
                onClick={() => setThread(wid, thread.id)}
                aria-current={selected ? "true" : undefined}
                className={cn(
                  "flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left hover:bg-white/5",
                  selected && "bg-raised hover:bg-raised",
                )}
              >
                <span className="line-clamp-2 text-sm break-words">{thread.title}</span>
                <ThreadMeta thread={thread} now={now} />
              </button>
            </li>
          );
        })}
      </ul>
      {threads.hasNextPage ? (
        <div className="p-2">
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
