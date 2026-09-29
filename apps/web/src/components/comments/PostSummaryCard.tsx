"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { SUMMARY_WAIT_MS, updatedLabel } from "@/components/ai/SummarySection";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useRefreshPostSummary } from "@/lib/api/queries";
import type { PostDetail } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

const NONE = "none";

export const NOTHING_TO_SUMMARIZE = "There are no analysed comments to summarize yet.";

/**
 * UX-SCR-05 summary card (FR-CMT-04, TR-AI-11): two or three sentences about what people say.
 * Refresh answers 202 and the card waits for the post.updated that carries a newer summary.
 */
export function PostSummaryCard({ post, now }: { post: PostDetail; now: Date }) {
  const workspace = useCurrentWorkspace();
  const refresh = useRefreshPostSummary(workspace.id, post.id);
  const summary = post.summary?.trim() || null;
  const current = post.summary_updated_at ?? NONE;
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
        toast.error(error instanceof ApiError && error.code === "conflict" ? NOTHING_TO_SUMMARIZE : errorMessage(error));
      },
    });
  };

  return (
    <section aria-labelledby="post-summary-heading" className="space-y-2 rounded-xl border border-line bg-panel p-4">
      <h2 id="post-summary-heading" className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">
        Summary
      </h2>
      {waiting ? (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-3 w-full bg-raised" />
          <Skeleton className="h-3 w-5/6 bg-raised" />
          <p role="status" className="text-xs text-fg-secondary">
            Updating the summary…
          </p>
        </div>
      ) : summary ? (
        <p className="text-sm leading-relaxed">{summary}</p>
      ) : (
        <p className="text-sm text-fg-secondary">
          {post.stats.analysed > 0
            ? "No summary yet. It appears as comments come in, or ask for one now."
            : "No summary yet. It appears once comments are analysed."}
        </p>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-fg-secondary">
          {summary && post.summary_updated_at && !waiting ? updatedLabel(post.summary_updated_at, now) : ""}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="min-h-10 text-brand-fg md:min-h-7"
          disabled={waiting || refresh.isPending}
          onClick={ask}
        >
          <RefreshCw aria-hidden /> {summary ? "Refresh" : "Summarize"}
        </Button>
      </div>
    </section>
  );
}
