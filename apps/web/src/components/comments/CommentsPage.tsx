"use client";

import type { Route } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { usePostGrid, useSocialAccounts } from "@/lib/api/queries";
import { accountLabel, instagramAccounts } from "@/lib/automations/accounts";
import { flattenPosts } from "@/lib/comments/cache";
import { emptyStates } from "@/lib/copy";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { PostCard } from "./PostCard";

const ALL = "all";

/** 2 columns on phones, 3 from 768 px, 4 from 1024 px (UX-SCR-05). */
export const GRID_CLASS = "grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4";

function GridSkeleton() {
  return (
    <ul className={GRID_CLASS} aria-busy="true" aria-label="Loading posts">
      {Array.from({ length: 8 }, (_, i) => (
        <li key={i} className="overflow-hidden rounded-xl border border-line bg-panel">
          <Skeleton className="aspect-square w-full rounded-none" />
          <div className="space-y-2 p-3">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-1.5 w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * UX-SCR-05 / FR-CMT-03: the posts grid with each post's comment count, sentiment split and spam
 * count, filtered by account. Cards update live from post.updated (F-12).
 */
export function CommentsPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const now = useNow();
  const [accountId, setAccountId] = useState<string | null>(null);
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);
  const posts = usePostGrid(wid, accountId);
  const items = flattenPosts(posts.data);
  const chosen = accounts.find((account) => account.id === accountId);

  let content;
  if (posts.isPending) content = <GridSkeleton />;
  else if (posts.isError) content = <ErrorState error={posts.error} onRetry={() => void posts.refetch()} />;
  else if (items.length === 0) {
    if (chosen) {
      content = (
        <EmptyState
          className="rounded-xl border border-line bg-panel"
          title="No posts yet"
          body={`Posts from ${accountLabel(chosen)} and their comments appear here once they sync.`}
        />
      );
    } else if (allAccounts.isSuccess && accounts.length === 0) {
      content = (
        <EmptyState
          className="rounded-xl border border-line bg-panel"
          {...emptyStates.comments}
          action={
            <Button asChild>
              <Link href={`/w/${workspace.slug}/settings/connections` as Route}>Connect Instagram</Link>
            </Button>
          }
        />
      );
    } else {
      content = (
        <EmptyState
          className="rounded-xl border border-line bg-panel"
          title={emptyStates.comments.title}
          body="Your Instagram posts and their comments appear here once they sync."
        />
      );
    }
  } else {
    content = (
      <div className="space-y-4">
        <ul className={GRID_CLASS} aria-label="Posts" data-testid="posts-grid">
          {items.map((post) => (
            <PostCard key={post.id} post={post} slug={workspace.slug} timeZone={workspace.timezone} now={now} />
          ))}
        </ul>
        {posts.hasNextPage ? (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              onClick={() => void posts.fetchNextPage()}
              disabled={posts.isFetchingNextPage}
            >
              {posts.isFetchingNextPage ? "Loading…" : "Show more posts"}
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <PageFrame
      title="Comments"
      actions={
        accounts.length > 1 ? (
          <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
            <SelectTrigger aria-label="Account" size="lg" className="max-w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All accounts</SelectItem>
              {accounts.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {accountLabel(account)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null
      }
    >
      {content}
    </PageFrame>
  );
}
