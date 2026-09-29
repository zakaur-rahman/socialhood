"use client";

import type { Route } from "next";
import Link from "next/link";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { usePost, useSocialAccounts } from "@/lib/api/queries";
import { mediaTypeLabel } from "@/lib/comments/format";
import { formatDay } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { CommentsColumn } from "./CommentsColumn";
import { PostPanel } from "./PostPanel";
import { PostPerformanceCard } from "./PostPerformanceCard";
import { PostSummaryCard } from "./PostSummaryCard";
import { TopicsCard } from "./TopicsCard";

/** A 340 px left column from 1024 px; one column on phones and tablets (UX-SCR-05). */
export const DETAIL_GRID_CLASS = "grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-6";

function DetailSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1200px] p-4 md:p-6" aria-busy="true" aria-label="Loading the post">
      <Skeleton className="mb-6 h-8 w-56 bg-raised" />
      <div className={DETAIL_GRID_CLASS}>
        <div className="space-y-4">
          <Skeleton className="aspect-square w-full rounded-xl bg-panel" />
          <Skeleton className="h-28 w-full rounded-xl bg-panel" />
        </div>
        <div className="space-y-3 rounded-xl border border-line bg-panel p-4">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="flex gap-3">
              <Skeleton className="size-8 rounded-full bg-raised" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-1/3 bg-raised" />
                <Skeleton className="h-3 w-2/3 bg-raised" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * UX-SCR-05 / FR-CMT-04 / FR-ANL-02: a post's comments page. Left: the post, its counts and
 * sentiment, the summary, topics and performance at an age compared with earlier posts. Main: the
 * filter chips and comment rows with their actions. post.updated and comment.* keep it live.
 */
export function PostDetailPage({ postId }: { postId: string }) {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const post = usePost(workspace.id, postId);
  const accounts = useSocialAccounts(workspace.id);
  const back = { href: `/w/${workspace.slug}/comments` as Route, label: "Comments" };

  if (post.isPending) return <DetailSkeleton />;
  if (post.isError) {
    if (post.error instanceof ApiError && post.error.status === 404) {
      return (
        <EmptyState
          className="min-h-[60vh]"
          title="Post not found"
          body="It may have been deleted on Instagram, or it belongs to another workspace."
          action={
            <Link href={back.href} className="text-sm text-brand-fg underline-offset-4 hover:underline">
              Back to Comments
            </Link>
          }
        />
      );
    }
    return <ErrorState error={post.error} onRetry={() => void post.refetch()} />;
  }

  const data = post.data;
  const account = accounts.data?.find((item) => item.id === data.social_account_id);
  const title = `${mediaTypeLabel(data.media_type)} from ${formatDay(data.posted_at, workspace.timezone, now)}`;

  return (
    <PageFrame title={title} back={back}>
      <div className={DETAIL_GRID_CLASS} data-testid="post-detail">
        <div className="min-w-0 space-y-4" data-testid="post-side">
          <PostPanel post={data} account={account} slug={workspace.slug} timeZone={workspace.timezone} now={now} />
          <PostSummaryCard post={data} now={now} />
          <TopicsCard topics={data.topics} analysed={data.stats.analysed} />
          <PostPerformanceCard
            wid={workspace.id}
            postId={data.id}
            account={account}
            slug={workspace.slug}
            timeZone={workspace.timezone}
            now={now}
          />
        </div>
        <CommentsColumn post={data} now={now} accountUsername={account?.username} />
      </div>
    </PageFrame>
  );
}
