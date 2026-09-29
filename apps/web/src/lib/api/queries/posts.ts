"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyComment, removeComment, type CommentPages, type PostPages } from "@/lib/comments/cache";

import type { Api } from "../client";
import { useApi } from "../provider";
import type { CommentFilter, CommentList, PostComment, PostDetail, PostList } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export type { CommentPages, PostPages };

/** Both the picker and the grid read 24 posts a page (divisible by the grid's 2, 3 and 4 columns). */
const POSTS_PAGE = 24;

function postsQuery(api: Api, wid: string, accountId: string | null, q: string) {
  return {
    queryKey: keys.posts(wid, accountId, q.trim()),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }: { pageParam: string | null }) =>
      unwrap(
        api.GET("/v1/w/{wid}/posts", {
          params: {
            path: { wid },
            query: {
              account_id: accountId ?? undefined,
              q: q.trim() || undefined,
              cursor: pageParam ?? undefined,
              limit: POSTS_PAGE,
            },
          },
        }),
      ),
    getNextPageParam: (last: PostList) => last.next_cursor ?? null,
  };
}

// ---- reading

/** The automation post picker (UX-SCR-03): one account's synced posts, newest first, searchable. */
export function usePosts(wid: string, accountId: string | null, q: string, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<PostList, Error, PostPages, ReturnType<typeof keys.posts>, string | null>({
    ...postsQuery(api, wid, accountId, q),
    enabled: enabled && Boolean(accountId),
  });
}

/** The Comments grid (FR-CMT-03): every account's posts, or one account's, newest first. */
export function usePostGrid(wid: string, accountId: string | null) {
  const api = useApi();
  return useInfiniteQuery<PostList, Error, PostPages, ReturnType<typeof keys.posts>, string | null>({
    ...postsQuery(api, wid, accountId, ""),
    // Switching accounts keeps the cards on screen until the other account's arrive.
    placeholderData: (previous) => previous,
  });
}

/** FR-CMT-04: the post with its counts, sentiment split, summary and topics. post.updated patches it. */
export function usePost(wid: string, postId: string) {
  const api = useApi();
  return useQuery<PostDetail>({
    queryKey: keys.post(wid, postId),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/posts/{post_id}", { params: { path: { wid, post_id: postId } } })),
  });
}

/** UX-SCR-05: the post's comments, newest first, narrowed by one filter chip. */
export function usePostComments(wid: string, postId: string, filter: CommentFilter) {
  const api = useApi();
  return useInfiniteQuery<CommentList, Error, CommentPages, ReturnType<typeof keys.postComments>, string | null>({
    queryKey: keys.postComments(wid, postId, filter),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/posts/{post_id}/comments", {
          params: {
            path: { wid, post_id: postId },
            query: { filter, cursor: pageParam ?? undefined, limit: 30 },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

// ---- changing

/** The summary card's Refresh (202): post.updated brings the new summary and topics. */
export function useRefreshPostSummary(wid: string, postId: string) {
  const api = useApi();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(api.POST("/v1/w/{wid}/posts/{post_id}/summary", { params: { path: { wid, post_id: postId } } })),
  });
}

export type CommentReply = { comment: PostComment; text: string; idempotencyKey: string };

/** A public reply under the comment (200 once Instagram accepts it). */
export function useReplyToComment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PostComment, Error, CommentReply>({
    mutationFn: ({ comment, text, idempotencyKey }) =>
      unwrap(
        api.POST("/v1/w/{wid}/comments/{comment_id}/reply", {
          params: { path: { wid, comment_id: comment.id }, header: { "Idempotency-Key": idempotencyKey } },
          body: { text },
        }),
      ),
    onSuccess: (comment) => applyComment(queryClient, wid, comment),
  });
}

/**
 * The one private reply Instagram allows per comment (202: the DM is queued in the commenter's
 * conversation). A second one is 409 conflict.
 */
export function usePrivateReply(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PostComment, Error, CommentReply>({
    mutationFn: ({ comment, text, idempotencyKey }) =>
      unwrap(
        api.POST("/v1/w/{wid}/comments/{comment_id}/private-reply", {
          params: { path: { wid, comment_id: comment.id }, header: { "Idempotency-Key": idempotencyKey } },
          body: { text },
        }),
      ),
    onSuccess: (comment) => applyComment(queryClient, wid, comment),
  });
}

/** Hide or show again on Instagram; the answer is the comment as it now is. */
export function useSetCommentHidden(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PostComment, Error, { comment: PostComment; hidden: boolean }>({
    mutationFn: ({ comment, hidden }) =>
      unwrap(
        hidden
          ? api.POST("/v1/w/{wid}/comments/{comment_id}/hide", { params: { path: { wid, comment_id: comment.id } } })
          : api.POST("/v1/w/{wid}/comments/{comment_id}/unhide", { params: { path: { wid, comment_id: comment.id } } }),
      ),
    onSuccess: (comment) => applyComment(queryClient, wid, comment),
  });
}

/** Admins: delete on Instagram (204). The row leaves every list; post.updated brings the counts. */
export function useDeleteComment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, PostComment>({
    mutationFn: (comment) =>
      expectOk(api.DELETE("/v1/w/{wid}/comments/{comment_id}", { params: { path: { wid, comment_id: comment.id } } })),
    onSuccess: (_, comment) => removeComment(queryClient, wid, comment.post_id, comment.id),
  });
}
