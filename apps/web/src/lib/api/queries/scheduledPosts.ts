"use client";

/**
 * The post composer's queries (T7.5: F-13, FR-PUB-01…04, FR-PUB-09…13, FR-AUT-18, UX-SCR-13):
 * one scheduled post and its lifecycle, hashtag groups, the media library, posting times for
 * Add to queue, AI caption and hashtags, and Add comment automation. The Schedule page's calendar
 * and list queries live in calendar.ts.
 */
import {
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";

import { toDefinition, toRequestBody, triggerPatch } from "@/lib/automations/definition";
import type {
  CaptionRequest,
  CaptionSuggestion,
  HashtagGroup,
  HashtagSuggestion,
  HashtagSuggestionRequest,
  MediaAssetList,
  PostingSlots,
  ScheduledPost,
  ScheduledPostDraft,
} from "@/lib/publishing/types";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type { Automation, AutomationDefinition } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** Filters of the media library (FR-PUB-13). Part of its query key. */
export type MediaLibraryFilters = {
  type: "image" | "video" | null;
  /** Upload dates in the workspace time zone, "2026-09-01", both included. */
  since: string | null;
  until: string | null;
};

export type MediaLibraryPages = InfiniteData<MediaAssetList, string | null>;

/** Query keys (TR-FE-03): everything under ["w", workspaceId]. */
export const composerKeys = {
  post: (wid: string, id: string) => ["w", wid, "scheduled-post", id] as const,
  /** Every list and calendar range that shows posts: refreshed after a change. */
  lists: (wid: string) => ["w", wid, "scheduled-posts"] as const,
  calendar: (wid: string) => ["w", wid, "calendar"] as const,
  hashtagGroups: (wid: string) => ["w", wid, "hashtag-groups"] as const,
  mediaLibrary: (wid: string, filters: MediaLibraryFilters) => ["w", wid, "media-library", filters] as const,
  mediaLibraries: (wid: string) => ["w", wid, "media-library"] as const,
  postingSlots: (wid: string, accountId: string) => ["w", wid, "posting-slots", accountId] as const,
};

/**
 * A post changed (a save, a lifecycle action, or scheduled_post.updated): the composer's copy is
 * replaced and the Schedule page's lists and calendar refetch.
 */
export function applyComposerPost(queryClient: QueryClient, wid: string, post: ScheduledPost): void {
  queryClient.setQueryData(composerKeys.post(wid, post.id), post);
  void queryClient.invalidateQueries({ queryKey: composerKeys.lists(wid) });
  void queryClient.invalidateQueries({ queryKey: composerKeys.calendar(wid) });
}

// ---- reading

/** GET …/scheduled-posts/{id}: the post with its checklist and linked automations. */
export function useComposerPost(wid: string, id: string) {
  const api = useApi();
  return useQuery<ScheduledPost>({
    queryKey: composerKeys.post(wid, id),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}", {
          params: { path: { wid, scheduled_post_id: id } },
        }),
      ),
  });
}

/** FR-PUB-12: the workspace's hashtag groups, by name. */
export function useComposerHashtagGroups(wid: string) {
  const api = useApi();
  return useQuery<HashtagGroup[]>({
    queryKey: composerKeys.hashtagGroups(wid),
    queryFn: async () =>
      (await unwrap(api.GET("/v1/w/{wid}/hashtag-groups", { params: { path: { wid } } }))).items,
  });
}

/** FR-PUB-13: post uploads, newest first, by type and upload date; 40 a page. */
export function useMediaLibrary(wid: string, filters: MediaLibraryFilters, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<
    MediaAssetList,
    Error,
    MediaLibraryPages,
    ReturnType<typeof composerKeys.mediaLibrary>,
    string | null
  >({
    queryKey: composerKeys.mediaLibrary(wid, filters),
    enabled,
    initialPageParam: null,
    placeholderData: (previous) => previous,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/media-assets", {
          params: {
            path: { wid },
            query: {
              type: filters.type ?? undefined,
              since: filters.since ?? undefined,
              until: filters.until ?? undefined,
              cursor: pageParam ?? undefined,
              limit: 40,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** FR-PUB-09: each selected account's posting times and next free times, for Add to queue. */
export function useComposerPostingSlots(wid: string, accountIds: string[], enabled = true) {
  const api = useApi();
  return useQueries({
    queries: accountIds.map((accountId) => ({
      queryKey: composerKeys.postingSlots(wid, accountId),
      enabled,
      queryFn: () =>
        unwrap(
          api.GET("/v1/w/{wid}/social-accounts/{account_id}/posting-slots", {
            params: { path: { wid, account_id: accountId } },
          }),
        ) as Promise<PostingSlots>,
    })),
  });
}

// ---- changing the post

/** New post (F-13): a draft, empty or with a time from a calendar click. The composer opens on it. */
export function useCreatePostDraft(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPost, Error, ScheduledPostDraft>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/scheduled-posts", { params: { path: { wid } }, body })),
    onSuccess: (post) => applyComposerPost(queryClient, wid, post),
  });
}

/** PUT: the autosave of a draft, Update schedule, and Edit and retry (a failed post becomes a draft). */
export function useSaveComposerPost(wid: string, id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPost, Error, ScheduledPostDraft>({
    mutationFn: (body) =>
      unwrap(
        api.PUT("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}", {
          params: { path: { wid, scheduled_post_id: id } },
          body,
        }),
      ),
    onSuccess: (post) => applyComposerPost(queryClient, wid, post),
  });
}

/** F-13 Schedule: 422 lists every failing field; 402 past the monthly limit. */
export function useComposerSchedule(wid: string, id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPost, Error, string>({
    mutationFn: (publishAt) =>
      unwrap(
        api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/schedule", {
          params: { path: { wid, scheduled_post_id: id } },
          body: { publish_at: publishAt },
        }),
      ),
    onSuccess: (post) => applyComposerPost(queryClient, wid, post),
  });
}

type BodylessAction = "queue" | "publish-now" | "unschedule";

function usePostAction(wid: string, id: string, action: BodylessAction) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPost, Error, void>({
    mutationFn: () => {
      const params = { path: { wid, scheduled_post_id: id } };
      switch (action) {
        case "queue":
          return unwrap(api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/queue", { params }));
        case "publish-now":
          return unwrap(api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/publish-now", { params }));
        case "unschedule":
          return unwrap(api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/unschedule", { params }));
      }
    },
    onSuccess: (post) => applyComposerPost(queryClient, wid, post),
  });
}

/** FR-PUB-09 Add to queue: the first posting time free for every selected account. */
export function useComposerQueue(wid: string, id: string) {
  return usePostAction(wid, id, "queue");
}

/** F-13 Publish now (202): scheduled_post.updated follows each step. */
export function useComposerPublishNow(wid: string, id: string) {
  return usePostAction(wid, id, "publish-now");
}

/** Back to draft, keeping the time (FR-PUB-04). */
export function useComposerUnschedule(wid: string, id: string) {
  return usePostAction(wid, id, "unschedule");
}

/** FR-PUB-14: a new draft with the same accounts, captions, media and first comment. */
export function useComposerDuplicate(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPost, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/duplicate", {
          params: { path: { wid, scheduled_post_id: id } },
        }),
      ),
    onSuccess: (post) => applyComposerPost(queryClient, wid, post),
  });
}

export function useComposerDelete(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}", {
          params: { path: { wid, scheduled_post_id: id } },
        }),
      ),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: composerKeys.post(wid, id) });
      void queryClient.invalidateQueries({ queryKey: composerKeys.lists(wid) });
      void queryClient.invalidateQueries({ queryKey: composerKeys.calendar(wid) });
    },
  });
}

// ---- AI (FR-PUB-02): nothing is stored; the result goes into the caption. Credits are used.

export function useGenerateCaption(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<CaptionSuggestion, Error, CaptionRequest>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/ai/caption", { params: { path: { wid } }, body })),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: keys.billing(wid) }),
    // The caption box says why beside the field, with Upgrade (CaptionEditor).
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useSuggestHashtags(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<HashtagSuggestion, Error, HashtagSuggestionRequest>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/ai/hashtags", { params: { path: { wid } }, body })),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: keys.billing(wid) }),
    meta: INLINE_PLAN_LIMITS,
  });
}

// ---- Add comment automation (FR-AUT-18)

/** The definition that points a new automation at this scheduled post (and only it). */
export function linkedDefinition(automation: Automation, scheduledPostId: string): AutomationDefinition {
  const definition = toDefinition(automation);
  // A blank automation has no trigger yet: a post's automation answers comment keywords.
  const trigger = definition.trigger === "comment_any" ? "comment_any" : "comment_keyword";
  const withTrigger =
    definition.trigger === trigger ? definition : { ...definition, ...triggerPatch(definition, trigger) };
  return toRequestBody({
    ...withTrigger,
    post_scope: "selected",
    media_item_ids: [],
    scheduled_post_ids: [scheduledPostId],
  });
}

export type AddCommentAutomation = {
  /** A template key, or null for Start from blank. */
  templateKey: string | null;
  accountId: string;
  name?: string;
};

/**
 * "Add comment automation" in the composer: create the automation from a template for one of
 * the post's accounts, then scope it to this scheduled post. It links itself to the published
 * post when it goes live (FR-AUT-18). The editor opens on it next.
 */
export function useAddCommentAutomation(wid: string, scheduledPostId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Automation, Error, AddCommentAutomation>({
    mutationFn: async ({ templateKey, accountId, name }) => {
      const created = await unwrap(
        api.POST("/v1/w/{wid}/automations", {
          params: { path: { wid } },
          body: templateKey ? { template_key: templateKey, social_account_id: accountId } : { name, social_account_id: accountId },
        }),
      );
      return unwrap(
        api.PUT("/v1/w/{wid}/automations/{automation_id}", {
          params: { path: { wid, automation_id: created.id } },
          body: linkedDefinition(created, scheduledPostId),
        }),
      );
    },
    onSuccess: (automation) => {
      queryClient.setQueryData(keys.automation(wid, automation.id), automation);
      void queryClient.invalidateQueries({ queryKey: keys.automationLists(wid) });
      void queryClient.invalidateQueries({ queryKey: composerKeys.post(wid, scheduledPostId) });
    },
  });
}
