"use client";

import type { Route } from "next";
import Link from "next/link";
import { useMemo } from "react";

import { PageFrame } from "@/components/shell/PageFrame";
import { AccountChoice, AllAccountsChoice } from "@/components/connections/AccountChoice";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCommentCounts, usePostGrid, useSocialAccounts } from "@/lib/api/queries";
import type { PostSort } from "@/lib/api/types";
import { accountLabel, commentAccounts } from "@/lib/automations/accounts";
import { flattenPosts } from "@/lib/comments/cache";
import { formatCount } from "@/lib/comments/format";
import { emptyStates } from "@/lib/copy";
import { useNow, useStoredString } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { PostCard } from "./PostCard";

const ALL = "all";

/** 2 columns on phones, 3 from 768 px, 4 from 1024 px (UX-SCR-05). */
export const GRID_CLASS = "grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6";

function GridSkeleton() {
  return (
    <ul className={GRID_CLASS} aria-busy="true" aria-label="Loading posts">
      {Array.from({ length: 8 }, (_, i) => (
        <Card asChild key={i} className="overflow-hidden p-0">
          <li>
            <Skeleton className="aspect-square w-full rounded-none" />
            <div className="space-y-2 p-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="h-1.5 w-full" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </li>
        </Card>
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
  const youtubeOn = (workspace.features ?? []).includes("youtube");
  const connectLabel = youtubeOn ? "Connect an account" : "Connect Instagram";
  const now = useNow();
  // Remembered per workspace, so opening a post and coming back keeps the account and the order.
  const [storedAccount, setStoredAccount] = useStoredString<string>(`socialhood:comments-account:${wid}`, ALL);
  const [storedSort, setSort] = useStoredString<PostSort>(`socialhood:comments-sort:${wid}`, "recent");
  const sort: PostSort = storedSort === "needs_reply" ? "needs_reply" : "recent";
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => commentAccounts(allAccounts.data ?? []), [allAccounts.data]);
  // A remembered account that was since disconnected falls back to all (once the list has loaded).
  const accountId =
    storedAccount === ALL || (allAccounts.data && !accounts.some((account) => account.id === storedAccount))
      ? null
      : storedAccount;
  const setAccountId = (id: string | null) => setStoredAccount(id ?? ALL);
  const posts = usePostGrid(wid, accountId, sort);
  const counts = useCommentCounts(wid);
  const waiting = counts.data?.needs_reply ?? 0;
  const items = flattenPosts(posts.data);
  const chosen = accounts.find((account) => account.id === accountId);

  let content;
  if (posts.isPending) content = <GridSkeleton />;
  else if (posts.isError) content = <ErrorState error={posts.error} onRetry={() => void posts.refetch()} />;
  else if (items.length === 0) {
    if (chosen) {
      content = (
        <Card>
          <EmptyState
            size="compact"
            title="No posts yet"
            body={`Posts from ${accountLabel(chosen)} and their comments appear here once they sync.`}
          />
        </Card>
      );
    } else if (allAccounts.isSuccess && accounts.length === 0) {
      content = (
        <Card>
          <EmptyState
            size="compact"
            title={emptyStates.comments.title}
            body={youtubeOn ? "Your Instagram, Facebook and YouTube posts and their comments appear here after you connect." : emptyStates.comments.body}
            action={
              <Button asChild size="sm">
                <Link href={`/w/${workspace.slug}/settings/connections` as Route}>{connectLabel}</Link>
              </Button>
            }
          />
        </Card>
      );
    } else {
      content = (
        <Card>
          <EmptyState
            size="compact"
            title={emptyStates.comments.title}
            body="Your posts and their comments appear here once they sync."
          />
        </Card>
      );
    }
  } else {
    content = (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <p className="text-sm text-fg-secondary" data-testid="needs-reply-total">
            {waiting > 0
              ? `${formatCount(waiting)} ${waiting === 1 ? "comment needs" : "comments need"} a reply. Open a post to answer.`
              : "No comments are waiting for a reply."}
          </p>
          <Select value={sort} onValueChange={(value) => setSort(value as PostSort)}>
            <SelectTrigger aria-label="Sort posts" size="lg" className="max-w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recent">Newest first</SelectItem>
              <SelectItem value="needs_reply">Most to reply to</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <ul className={GRID_CLASS} aria-label="Posts" data-testid="posts-grid">
          {items.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              account={allAccounts.data ? (allAccounts.data.find((a) => a.id === post.social_account_id) ?? null) : undefined}
              slug={workspace.slug}
              timeZone={workspace.timezone}
              now={now}
            />
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
        <>
          <Button asChild variant="secondary" size="lg">
            <Link href={`/w/${workspace.slug}/comments/mentions` as Route}>Story mentions</Link>
          </Button>
          {accounts.length > 1 ? (
          <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
            {/* A fixed width: an account's name changing the button's width would move the buttons beside it. */}
            <SelectTrigger aria-label="Account" size="lg" className="w-48 shrink-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL} check="highlight" textValue="All accounts">
                <AllAccountsChoice />
              </SelectItem>
              {accounts.map((account) => (
                <SelectItem key={account.id} value={account.id} textValue={accountLabel(account)} check="highlight">
                  <AccountChoice account={account} />
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          ) : null}
        </>
      }
    >
      {content}
    </PageFrame>
  );
}
