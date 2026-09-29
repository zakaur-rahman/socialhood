"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { BILLING_HREF } from "@/components/shell/nav";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { threadRunsOldestFirst } from "@/lib/agent/cache";
import { isActive, SUGGESTED_PROMPTS } from "@/lib/agent/format";
import { useAskStore } from "@/lib/agent/store";
import { ApiError } from "@/lib/api/errors";
import { exhaustedAiCredits, useAskAgent, useBilling, useThreadRuns } from "@/lib/api/queries";
import { aiCreditsExhausted, errorMessage } from "@/lib/copy";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AskComposer } from "./AskComposer";
import { RunView, type RunContext } from "./RunView";

/**
 * A thread of Ask Social Hood (FR-AGT-01): its questions and answers oldest first, suggested
 * prompts for a new thread, and the question box. The panel and the /ask page both show it; the
 * thread in view lives in the Ask store, so both show the same one.
 */
export function AskConversation({
  composerId,
  onNavigate,
}: {
  /** The question box's id, for labels and the shortcut's focus. */
  composerId: string;
  /** Following a citation or action card: the panel closes. */
  onNavigate?: () => void;
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
  const billing = useBilling(wid);
  const [error, setError] = useState<unknown>(null);

  const latest = items[items.length - 1];
  const working = Boolean(latest && isActive(latest.status));
  const credits = exhaustedAiCredits(billing.data);
  const outOfCredits = error instanceof ApiError && error.code === "quota_exceeded";

  const send = (request: string) => {
    setError(null);
    ask.mutate(
      threadId ? { request, thread_id: threadId } : { request },
      {
        onSuccess: (run) => {
          setThread(wid, run.thread_id);
          setDraft(wid, "");
        },
        onError: (caught) => setError(caught),
      },
    );
  };

  // Keep the newest exchange in view as questions, steps and answers arrive.
  const scroller = useRef<HTMLDivElement>(null);
  const latestKey = latest ? `${latest.id}:${latest.status}` : "";
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items.length, latestKey]);

  const context: RunContext = {
    wid,
    slug: workspace.slug,
    timeZone: workspace.timezone,
    role: workspace.role,
    now,
    onNavigate,
    onAskAgain: (request) => send(request),
    busy: ask.isPending || working,
  };

  let body;
  if (!threadId) {
    body = <Welcome onPick={send} disabled={ask.isPending || Boolean(credits)} />;
  } else if (runs.isPending) {
    body = (
      <div className="space-y-4" aria-busy="true" aria-label="Loading the thread">
        <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl bg-raised" />
        <Skeleton className="h-24 w-full rounded-xl bg-panel" />
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
      <>
        {runs.hasNextPage ? (
          <div className="flex justify-center">
            <Button
              variant="ghost"
              size="sm"
              disabled={runs.isFetchingNextPage}
              onClick={() => void runs.fetchNextPage()}
            >
              {runs.isFetchingNextPage ? "Loading…" : "Show earlier questions"}
            </Button>
          </div>
        ) : null}
        {items.map((run) => (
          <RunView key={run.id} run={run} context={context} />
        ))}
      </>
    );
  }

  let blockedReason: string | null = null;
  if (credits && credits.limit !== null && credits.limit !== undefined) {
    blockedReason = aiCreditsExhausted(credits.limit, credits.period_end, now);
  } else if (working) {
    blockedReason = "Social Hood is still working on your last question. Wait for it, or cancel it.";
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scroller}
        role="log"
        aria-label="Conversation with Social Hood"
        className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-canvas px-4 py-4"
        data-testid="ask-conversation"
      >
        {body}
      </div>
      {error ? (
        <div role="alert" className="shrink-0 space-y-2 border-t border-line bg-panel px-4 pt-3 text-sm">
          <p className={outOfCredits ? "text-warning" : "text-danger-fg"}>{askError(error, credits, now)}</p>
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
        blockedReason={blockedReason}
      />
    </div>
  );
}

/** quota_exceeded names the limit and when it resets (§4.7); anything else, the usual copy. */
function askError(
  error: unknown,
  credits: ReturnType<typeof exhaustedAiCredits>,
  now: Date,
): string {
  if (error instanceof ApiError && error.code === "quota_exceeded") {
    if (credits && credits.limit !== null && credits.limit !== undefined) {
      return aiCreditsExhausted(credits.limit, credits.period_end, now);
    }
    return error.detail || "You've used all your AI credits for this month.";
  }
  return errorMessage(error);
}

function Welcome({ onPick, disabled }: { onPick: (prompt: string) => void; disabled: boolean }) {
  return (
    <div className="space-y-4 py-2">
      <div className="space-y-1.5">
        <p className="flex items-center gap-2 text-base font-semibold">
          <Sparkles className="size-4 text-brand-fg" aria-hidden /> Ask about your business
        </p>
        <p className="text-sm text-fg-secondary">
          Posts, comments, conversations, automations and what you&apos;ve scheduled. Answers show the numbers,
          time range and posts they used, and link to them. Social Hood can prepare a message or reply for you to
          finish; it doesn&apos;t change anything itself.
        </p>
      </div>
      <div>
        <p className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Try asking</p>
        <ul className="flex flex-col items-start gap-2" aria-label="Suggested questions">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <li key={prompt}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(prompt)}
                className="min-h-10 rounded-full border border-brand-line bg-brand-soft px-3.5 py-2 text-left text-sm text-brand-fg hover:bg-brand-line disabled:opacity-50 md:min-h-8 md:py-1.5"
              >
                {prompt}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
