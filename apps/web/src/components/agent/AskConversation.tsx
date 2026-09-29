"use client";

import { ArrowDown, BarChart3, Inbox, MessageSquare, Sparkles, Zap, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { BILLING_HREF } from "@/components/shell/nav";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { threadRunsOldestFirst } from "@/lib/agent/cache";
import { isActive, SUGGESTED_PROMPTS, type PromptArea } from "@/lib/agent/format";
import { useAskStore } from "@/lib/agent/store";
import { ApiError } from "@/lib/api/errors";
import { exhaustedAiCredits, useAskAgent, useBilling, useCancelAgentRun, useThreadRuns } from "@/lib/api/queries";
import { aiCreditsExhausted, errorMessage } from "@/lib/copy";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AskComposer } from "./AskComposer";
import { RunView, type RunContext } from "./RunView";

/** Within this distance of the bottom the conversation follows new content. */
const NEAR_BOTTOM_PX = 96;

const AREA_ICON: Record<PromptArea, LucideIcon> = {
  inbox: Inbox,
  comments: MessageSquare,
  posts: BarChart3,
  automations: Zap,
};

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/**
 * A thread of Ask Social Hood (FR-AGT-01), laid out like a modern assistant chat: questions and
 * answers oldest first in one readable column (centred on the page, the panel's width in the
 * panel), a welcome with suggested questions for a new thread, and the question box below. The
 * view follows new content only while the member is near the bottom; otherwise "Jump to latest"
 * appears. The thread in view lives in the Ask store, so the panel and the page show the same one.
 */
export function AskConversation({
  composerId,
  onNavigate,
  variant = "panel",
}: {
  /** The question box's id, for labels and the shortcut's focus. */
  composerId: string;
  /** Following a citation or action card: the panel closes. */
  onNavigate?: () => void;
  variant?: "panel" | "page";
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const now = useNow();
  const threadId = useAskStore((state) => state.threads[wid] ?? null);
  const setThread = useAskStore((state) => state.setThread);
  const draft = useAskStore((state) => state.drafts[wid] ?? "");
  const setDraft = useAskStore((state) => state.setDraft);
  const runs = useThreadRuns(wid, threadId);
  const items = useMemo(() => threadRunsOldestFirst(runs.data), [runs.data]);
  const ask = useAskAgent(wid);
  const cancel = useCancelAgentRun(wid);
  const billing = useBilling(wid);
  const [error, setError] = useState<unknown>(null);

  const latest = items[items.length - 1];
  const working = Boolean(latest && isActive(latest.status));
  const credits = exhaustedAiCredits(billing.data);
  const outOfCredits = error instanceof ApiError && error.code === "quota_exceeded";

  // ---- scrolling: follow new content only while near the bottom
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const [away, setAway] = useState(false);

  const toBottom = useCallback((smooth = false) => {
    const el = scroller.current;
    if (!el) return;
    if (smooth && typeof el.scrollTo === "function" && !prefersReducedMotion()) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else el.scrollTop = el.scrollHeight;
  }, []);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    stick.current = near;
    setAway(!near);
  };

  // Steps, answers and new questions change the height: follow them if the member is at the end.
  useEffect(() => {
    const el = content.current;
    if (!el) return;
    const follow = () => {
      if (stick.current) toBottom();
    };
    follow();
    const observer = new ResizeObserver(follow);
    observer.observe(el);
    return () => observer.disconnect();
  }, [toBottom, threadId]);
  const latestKey = latest ? `${latest.id}:${latest.status}` : "";
  useEffect(() => {
    if (stick.current) toBottom();
  }, [items.length, latestKey, toBottom]);

  // A different thread opens at its end.
  useEffect(() => {
    stick.current = true;
    toBottom();
  }, [threadId, toBottom]);

  const send = (request: string) => {
    setError(null);
    stick.current = true;
    setAway(false);
    ask.mutate(threadId ? { request, thread_id: threadId } : { request }, {
      onSuccess: (run) => {
        setThread(wid, run.thread_id);
        setDraft(wid, "");
      },
      onError: (caught) => setError(caught),
    });
  };

  const stop = () => {
    if (!latest) return;
    cancel.mutate(latest.id, { onError: (caught) => toast.error(errorMessage(caught)) });
  };

  const context: RunContext = {
    wid,
    slug: workspace.slug,
    timeZone: workspace.timezone,
    role: workspace.role,
    now,
    onNavigate,
    onAsk: (request) => send(request),
    busy: ask.isPending || working,
  };

  let body;
  if (!threadId) {
    body = <Welcome variant={variant} onPick={send} disabled={ask.isPending || Boolean(credits)} />;
  } else if (runs.isPending) {
    body = (
      <div className="space-y-6" aria-busy="true" aria-label="Loading the thread">
        <Skeleton className="ml-auto h-11 w-2/3 rounded-2xl bg-raised" />
        <div className="flex gap-3">
          <Skeleton className="size-7 shrink-0 rounded-full bg-raised" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-5/6 bg-raised" />
            <Skeleton className="h-3 w-2/3 bg-raised" />
          </div>
        </div>
      </div>
    );
  } else if (runs.isError) {
    body = (
      <div className="space-y-2">
        <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
        <div className="flex justify-center">
          <Button variant="ghost" size="sm" onClick={() => setThread(wid, null)}>
            Start a new thread
          </Button>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="space-y-8">
        {runs.hasNextPage ? (
          <div className="flex justify-center">
            <Button variant="ghost" size="sm" disabled={runs.isFetchingNextPage} onClick={() => void runs.fetchNextPage()}>
              {runs.isFetchingNextPage ? "Loading…" : "Show earlier questions"}
            </Button>
          </div>
        ) : null}
        {items.map((run) => (
          <RunView key={run.id} run={run} context={context} latest={run === latest} />
        ))}
      </div>
    );
  }

  const blockedReason =
    credits && credits.limit !== null && credits.limit !== undefined
      ? aiCreditsExhausted(credits.limit, credits.period_end, now)
      : null;
  const column = variant === "page" ? "mx-auto w-full max-w-3xl px-4 md:px-6" : "w-full px-4";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          ref={scroller}
          onScroll={onScroll}
          role="log"
          aria-label="Conversation with Social Hood"
          className="min-h-0 flex-1 overflow-y-auto"
          data-testid="ask-conversation"
        >
          <div ref={content} className={cn(column, "flex min-h-full flex-col py-6")}>
            {body}
          </div>
        </div>
        {away && items.length > 0 ? (
          <button
            type="button"
            onClick={() => {
              stick.current = true;
              setAway(false);
              toBottom(true);
            }}
            className="absolute bottom-3 left-1/2 inline-flex min-h-10 -translate-x-1/2 items-center gap-1.5 rounded-full border border-line bg-panel px-3.5 text-sm shadow-xl hover:bg-raised md:min-h-8"
          >
            <ArrowDown className="size-4" aria-hidden /> Jump to latest
          </button>
        ) : null}
      </div>
      <div
        className={cn(
          column,
          "shrink-0 pt-1",
          variant === "page" ? "pb-4" : "pb-[calc(env(safe-area-inset-bottom)+0.75rem)]",
        )}
      >
        {error ? (
          <div role="alert" className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg px-1 text-sm">
            <p className={cn("min-w-0 flex-1", outOfCredits ? "text-warning" : "text-danger-fg")}>
              {askError(error, credits, now)}
            </p>
            {outOfCredits && workspace.role !== "agent" ? (
              <Button asChild size="sm" className="bg-brand-gradient min-h-10 text-white md:min-h-7">
                <Link href={BILLING_HREF(workspace.slug)} onClick={onNavigate}>
                  Upgrade
                </Link>
              </Button>
            ) : null}
          </div>
        ) : null}
        <AskComposer
          id={composerId}
          value={draft}
          onChange={(text) => {
            setDraft(wid, text);
            if (error) setError(null);
          }}
          onSubmit={send}
          sending={ask.isPending}
          working={working}
          onStop={stop}
          stopping={cancel.isPending}
          blockedReason={blockedReason}
        />
      </div>
    </div>
  );
}

/** quota_exceeded names the limit and when it resets (§4.7); anything else, the usual copy. */
function askError(error: unknown, credits: ReturnType<typeof exhaustedAiCredits>, now: Date): string {
  if (error instanceof ApiError && error.code === "quota_exceeded") {
    if (credits && credits.limit !== null && credits.limit !== undefined) {
      return aiCreditsExhausted(credits.limit, credits.period_end, now);
    }
    return error.detail || "You've used all your AI credits for this month.";
  }
  return errorMessage(error);
}

/** A new thread: what Social Hood can do and a question to start from in each area. */
function Welcome({
  variant,
  onPick,
  disabled,
}: {
  variant: "panel" | "page";
  onPick: (prompt: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-6 text-center" data-testid="ask-welcome">
      <span className="grid size-12 place-items-center rounded-2xl bg-brand-soft text-brand-fg" aria-hidden>
        <Sparkles className="size-6" />
      </span>
      <div className="max-w-md space-y-1.5">
        <h2 className="text-xl font-semibold tracking-tight">What would you like to know?</h2>
        <p className="text-sm text-fg-secondary">
          Ask about your posts, comments, conversations and automations. Answers show the numbers they used and
          link to them; Social Hood can prepare a reply for you to finish, but doesn&apos;t change anything itself.
        </p>
      </div>
      <ul
        aria-label="Suggested questions"
        className={cn("w-full text-left", variant === "page" ? "grid max-w-2xl gap-3 sm:grid-cols-2" : "flex flex-col gap-2")}
      >
        {SUGGESTED_PROMPTS.map(({ area, text }) => {
          const Icon = AREA_ICON[area];
          return (
            <li key={text}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(text)}
                className={cn(
                  "flex min-h-10 w-full items-start gap-3 rounded-xl border border-line bg-white/5 text-sm text-fg hover:border-line-strong hover:bg-white/10 disabled:opacity-50",
                  variant === "page" ? "h-full px-4 py-3.5" : "px-3.5 py-2.5",
                )}
              >
                <Icon className="mt-0.5 size-4 shrink-0 text-brand-fg" aria-hidden />
                <span>{text}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
