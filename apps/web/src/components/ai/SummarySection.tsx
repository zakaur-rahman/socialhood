"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRefreshSummary } from "@/lib/api/queries";
import type { Conversation } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { relativeTime } from "@/lib/time";
import { useCurrentWorkspace } from "@/lib/workspace";

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
        toast.error(errorMessage(error));
      },
    });
  };

  return (
    <div className="space-y-2">
      {waiting ? (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-3 w-full bg-raised" />
          <Skeleton className="h-3 w-5/6 bg-raised" />
          <p role="status" className="text-xs text-fg-secondary">
            Updating the summary…
          </p>
        </div>
      ) : summary ? (
        <>
          <p className="text-sm leading-relaxed">{summary.text}</p>
          {summary.next_step ? (
            <p className="text-sm">
              <span className="font-medium text-brand-fg">Next step: </span>
              {summary.next_step}
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-fg-secondary">No summary yet. It appears after a few messages, or ask for one now.</p>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-fg-secondary">{summary && !waiting ? updatedLabel(summary.updated_at, now) : ""}</span>
        <Button variant="ghost" size="xs" className="text-brand-fg" disabled={waiting || refresh.isPending} onClick={ask}>
          <RefreshCw aria-hidden /> {summary ? "Refresh" : "Summarize"}
        </Button>
      </div>
    </div>
  );
}
