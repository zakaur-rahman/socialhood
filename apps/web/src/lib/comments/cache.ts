/**
 * Cache patching for the Comments pages (TR-FE-04, F-12). post.updated, comment.created and
 * comment.updated, and the comment actions' answers, all go through these functions, so a card or
 * row looks the same whichever arrived first. They only touch caches that are already loaded.
 */
import type { InfiniteData, QueryClient, QueryKey } from "@tanstack/react-query";

import { keys } from "@/lib/api/queries/keys";
import type { CommentFilter, CommentList, PostComment, PostDetail, PostList, PostSummary } from "@/lib/api/types";

import { compareComments, matchesFilter } from "./format";

export type PostPages = InfiniteData<PostList, string | null>;
export type CommentPages = InfiniteData<CommentList, string | null>;

// ---- posts

/** The grid's projection of a post.updated payload. */
export function toSummary(post: PostDetail | PostSummary): PostSummary {
  return {
    id: post.id,
    social_account_id: post.social_account_id,
    platform_media_id: post.platform_media_id,
    media_type: post.media_type,
    caption: post.caption ?? null,
    media_url: post.media_url ?? null,
    thumbnail_url: post.thumbnail_url ?? null,
    permalink: post.permalink ?? null,
    posted_at: post.posted_at,
    like_count: post.like_count ?? null,
    comments_count: post.comments_count ?? null,
    stats: post.stats,
  };
}

function time(iso: string): number {
  return new Date(iso).getTime();
}

/**
 * Put a post into one list: replace it where it is; add a post the list does not have yet only
 * when the list is not a search, its account filter matches, and it falls among the loaded pages
 * (newest first), so a later page never duplicates it.
 */
function upsertPost(data: PostPages, key: QueryKey, post: PostSummary): PostPages {
  const found = data.pages.some((page) => page.items.some((item) => item.id === post.id));
  if (found) {
    return {
      ...data,
      pages: data.pages.map((page) => ({
        ...page,
        items: page.items.map((item) => (item.id === post.id ? post : item)),
      })),
    };
  }
  const [, , , accountId, q] = key as readonly unknown[];
  if (post.media_type === "story") return data;
  if (typeof q === "string" && q.trim()) return data;
  if (accountId && accountId !== post.social_account_id) return data;
  const last = data.pages[data.pages.length - 1];
  const loaded = data.pages.flatMap((page) => page.items);
  const oldest = loaded[loaded.length - 1];
  if (last?.next_cursor && oldest && time(post.posted_at) < time(oldest.posted_at)) return data;
  // Insert into the page whose items it belongs among.
  let placed = false;
  const pages = data.pages.map((page, index) => {
    if (placed) return page;
    const at = page.items.findIndex((item) => time(item.posted_at) < time(post.posted_at));
    if (at === -1 && index < data.pages.length - 1) return page;
    placed = true;
    const items = [...page.items];
    items.splice(at === -1 ? items.length : at, 0, post);
    return { ...page, items };
  });
  return placed ? { ...data, pages } : data;
}

/** post.updated (F-12): the card's counts and sentiment bar, and the open post detail. */
export function applyPost(queryClient: QueryClient, wid: string, post: PostDetail): void {
  queryClient.setQueryData<PostDetail>(keys.post(wid, post.id), (current) => (current ? post : current));
  const summary = toSummary(post);
  for (const [key, data] of queryClient.getQueriesData<PostPages>({ queryKey: keys.postLists(wid) })) {
    if (!data?.pages) continue;
    const next = upsertPost(data, key, summary);
    if (next !== data) queryClient.setQueryData(key, next);
  }
}

// ---- comments

function upsertComment(data: CommentPages, filter: CommentFilter, comment: PostComment): CommentPages {
  const present = data.pages.some((page) => page.items.some((item) => item.id === comment.id));
  const belongs = matchesFilter(comment, filter);
  if (present) {
    return {
      ...data,
      pages: data.pages.map((page) => ({
        ...page,
        items: belongs
          ? page.items.map((item) => (item.id === comment.id ? comment : item))
          : page.items.filter((item) => item.id !== comment.id),
      })),
    };
  }
  if (!belongs) return data;
  const loaded = data.pages.flatMap((page) => page.items);
  const oldest = loaded[loaded.length - 1];
  const last = data.pages[data.pages.length - 1];
  if (last?.next_cursor && oldest && compareComments(comment, oldest) > 0) return data;
  let placed = false;
  const pages = data.pages.map((page, index) => {
    if (placed) return page;
    const at = page.items.findIndex((item) => compareComments(comment, item) < 0);
    if (at === -1 && index < data.pages.length - 1) return page;
    placed = true;
    const items = [...page.items];
    items.splice(at === -1 ? items.length : at, 0, comment);
    return { ...page, items };
  });
  return placed ? { ...data, pages } : data;
}

/**
 * comment.created / comment.updated and the actions' answers: each loaded list of the post gets
 * the comment if it matches its filter, loses it if it no longer does, and drops it once deleted.
 */
export function applyComment(queryClient: QueryClient, wid: string, comment: PostComment): void {
  const lists = queryClient.getQueriesData<CommentPages>({ queryKey: keys.postCommentLists(wid, comment.post_id) });
  for (const [key, data] of lists) {
    if (!data?.pages) continue;
    const filter = (key as readonly unknown[])[4] as CommentFilter;
    const next = upsertComment(data, filter, comment);
    if (next !== data) queryClient.setQueryData(key, next);
  }
}

/** Delete answered 204: drop the row from every list of the post. */
export function removeComment(queryClient: QueryClient, wid: string, postId: string, commentId: string): void {
  queryClient.setQueriesData<CommentPages>({ queryKey: keys.postCommentLists(wid, postId) }, (data) =>
    data?.pages
      ? { ...data, pages: data.pages.map((page) => ({ ...page, items: page.items.filter((item) => item.id !== commentId) })) }
      : data,
  );
}

export function flattenComments(data: CommentPages | undefined): PostComment[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

export function flattenPosts(data: PostPages | undefined): PostSummary[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}
