"use client";

import { Lightbulb, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRefreshSummary } from "@/lib/api/queries";
import type { Conversation } from "@/lib/api/types";
import { toastError } from "@/lib/toast-error";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";
import { EYEBROW } from "@/styles/tokens";

/** How long a requested summary is awaited before the panel says it didn't come. */
export const SUMMARY_WAIT_MS = 30_000;

const NONE = "none";

/** "Updated just now", "Updated 5m ago", "Updated 12 Mar". */
export function updatedLabel(iso: string, now: Date): string {
  const when = relativeTime(iso, now);
  if (when === "now") return "Updated just now";
  return /^\d+[mhd]$/.test(when) ? `Updated ${when} ago` : `Updated ${when}`;
}

/**
 * FR-AI-03 in the details panel: up to three sentences and a next step, refreshed after 8 new
 * messages or on request (202; conversation.updated brings the new one).
 */
export function SummarySection({ conversation, now }: { conversation: Conversation; now: Date }) {
  const workspace = useCurrentWorkspace();
  const refresh = useRefreshSummary(workspace.id, conversation.id);
  const summary = conversation.summary ?? null;
  const current = summary?.updated_at ?? NONE;
  // The summary's version when the refresh was asked for; a different one means it arrived.
  const [requested, setRequested] = useState<string | null>(null);
  const waiting = requested !== null && requested === current;
  const currentRef = useRef(current);
  useEffect(() => {
    currentRef.current = current;
  });

  useEffect(() => {
    if (requested === null) return;
    const timer = window.setTimeout(() => {
      if (currentRef.current === requested) toast.error("The summary didn't update. Try again.");
      setRequested(null);
    }, SUMMARY_WAIT_MS);
    return () => window.clearTimeout(timer);
  }, [requested]);

  const ask = () => {
    setRequested(current);
    refresh.mutate(undefined, {
      onError: (error) => {
        setRequested(null);
        toastError(error); // out of credits (402): the upgrade dialog says so
      },
    });
  };

  return (
    <div className="space-y-2">
      {waiting ? (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <p role="status" className="text-xs text-fg-secondary">
            Updating the summary…
          </p>
        </div>
      ) : summary ? (
        <>
          <p className="text-sm leading-relaxed">{summary.text}</p>
          {summary.next_step ? (
            // summary.v2 (C-063): one concrete suggestion from the conversation and knowledge.
            <div role="note" aria-label="Next step" className="rounded-lg border border-brand-line bg-brand-soft px-3 py-2">
              <p className={cn(EYEBROW, "flex items-center gap-1 text-brand-fg")}>
                <Lightbulb className="size-3" aria-hidden /> Next step
              </p>
              <p className="mt-0.5 text-sm leading-relaxed">{summary.next_step}</p>
            </div>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-fg-secondary">No summary yet. It appears after a few messages, or ask for one now.</p>
      )}
      <p className="text-xs text-fg-secondary">{summary && !waiting ? updatedLabel(summary.updated_at, now) : ""}</p>
      <Button
        variant="secondary"
        size="sm"
        className="w-full"
        disabled={waiting || refresh.isPending}
        onClick={ask}
      >
        <RefreshCw aria-hidden /> {summary ? "Refresh" : "Summarize"}
      </Button>
    </div>
  );
}
