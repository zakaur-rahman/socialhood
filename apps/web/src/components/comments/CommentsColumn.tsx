"use client";

import { useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePostComments } from "@/lib/api/queries";
import type { CommentFilter, PostDetail } from "@/lib/api/types";
import { flattenComments } from "@/lib/comments/cache";
import { COMMENT_FILTERS, filterEmpty, isAnalysing } from "@/lib/comments/format";
import { useCurrentWorkspace } from "@/lib/workspace";

import { CommentRow } from "./CommentRow";

function RowSkeletons() {
  return (
    <ul aria-busy="true" aria-label="Loading comments">
      {Array.from({ length: 5 }, (_, i) => (
        <li key={i} className="flex gap-3 border-b border-line-subtle px-4 py-3 last:border-b-0">
          <Skeleton className="size-8 rounded-full bg-raised" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3 bg-raised" />
            <Skeleton className="h-3 w-2/3 bg-raised" />
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * UX-SCR-05 main column: the filter chips (All, Positive, Neutral, Negative, Questions, Buying
 * signals, Spam, Hidden) and the comment rows, newest first. comment.created and comment.updated
 * patch the loaded lists (F-12).
 */
export function CommentsColumn({
  post,
  now,
  accountUsername,
}: {
  post: PostDetail;
  now: Date;
  accountUsername?: string | null;
}) {
  const workspace = useCurrentWorkspace();
  const [filter, setFilter] = useState<CommentFilter>("all");
  const comments = usePostComments(workspace.id, post.id, filter);
  const items = flattenComments(comments.data);
  const canDelete = workspace.role === "owner" || workspace.role === "admin";

  let content;
  if (comments.isPending) content = <RowSkeletons />;
  else if (comments.isError) content = <ErrorState error={comments.error} onRetry={() => void comments.refetch()} />;
  else if (items.length === 0) {
    content = (
      <EmptyState
        {...filterEmpty(filter, isAnalysing(post.stats))}
        action={
          filter === "all" ? undefined : (
            <Button variant="secondary" className="min-h-10 md:min-h-8" onClick={() => setFilter("all")}>
              Show all
            </Button>
          )
        }
      />
    );
  } else {
    content = (
      <>
        <ul aria-label="Comments" data-testid="comment-list">
          {items.map((comment) => (
            <CommentRow
              key={comment.id}
              comment={comment}
              wid={workspace.id}
              slug={workspace.slug}
              timeZone={workspace.timezone}
              now={now}
              canDelete={canDelete}
              accountUsername={accountUsername}
            />
          ))}
        </ul>
        {comments.hasNextPage ? (
          <div className="flex justify-center border-t border-line-subtle p-3">
            <Button
              variant="secondary"
              className="min-h-10 md:min-h-8"
              onClick={() => void comments.fetchNextPage()}
              disabled={comments.isFetchingNextPage}
            >
              {comments.isFetchingNextPage ? "Loading…" : "Show more comments"}
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <section aria-labelledby="post-comments-heading" className="min-w-0 rounded-xl border border-line bg-panel">
      <div className="space-y-3 border-b border-line p-4">
        <h2 id="post-comments-heading" className="text-base font-semibold">
          Comments
        </h2>
        <ToggleGroup
          aria-label="Filter comments"
          value={filter}
          onValueChange={(value) => setFilter(value as CommentFilter)}
          className="flex-wrap bg-transparent p-0"
          data-testid="comment-filters"
        >
          {COMMENT_FILTERS.map((option) => (
            <ToggleGroupItem
              key={option.value}
              value={option.value}
              className="min-h-10 flex-none rounded-full border border-line bg-field px-3 py-1 text-xs data-[state=on]:border-brand-line data-[state=on]:bg-brand-soft md:min-h-8"
            >
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      {content}
    </section>
  );
}
