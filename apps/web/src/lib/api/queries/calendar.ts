"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";

import {
  patchCalendars,
  refreshSchedule,
  removeFromCalendars,
  restoreCalendars,
  snapshotCalendars,
  type CalendarSnapshot,
} from "@/lib/schedule/cache";

import type { Api } from "../client";
import { useApi } from "../provider";
import type {
  BulkScheduledPostRequest,
  BulkScheduledPostResult,
  Calendar,
  HashtagGroup,
  HashtagGroupCreate,
  HashtagGroupPatch,
  PostingSlot,
  PostingSlots,
  ScheduledPostDetail,
  ScheduledPostList,
  ScheduledPostSummary,
  ScheduledPostView,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export type ScheduledPostPages = InfiniteData<ScheduledPostList, string | null>;

// ---- reading

/**
 * FR-PUB-08: posts, scheduled DMs and free posting times for the days shown (dates in the
 * workspace time zone, both included). Every layer and account is read; the page filters, so
 * toggling an account or a layer is instant and the right rail keeps every account's figures.
 */
export function useCalendar(wid: string, from: string, to: string, enabled = true) {
  const api = useApi();
  return useQuery<Calendar>({
    queryKey: keys.calendar(wid, from, to),
    enabled,
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/calendar", { params: { path: { wid }, query: { from, to } } })),
    // Moving to the next week keeps the grid on screen until its posts arrive.
    placeholderData: (previous) => previous,
  });
}

/** The List view's tabs and the rail's Unscheduled drafts (UX-SCR-04). */
export function useScheduledPostList(wid: string, view: ScheduledPostView, accountIds: string[] | null = null) {
  const api = useApi();
  return useInfiniteQuery<
    ScheduledPostList,
    Error,
    ScheduledPostPages,
    ReturnType<typeof keys.scheduledPosts>,
    string | null
  >({
    queryKey: keys.scheduledPosts(wid, view, accountIds),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/scheduled-posts", {
          params: {
            path: { wid },
            query: { view, account_ids: accountIds ?? undefined, cursor: pageParam ?? undefined, limit: 50 },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

// ---- lifecycle (F-13)

/** New post: a draft, pre-filled with the time clicked on the calendar. */
export function useCreateScheduledPost(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPostDetail, Error, { publishAt?: string | null }>({
    mutationFn: ({ publishAt }) =>
      unwrap(
        api.POST("/v1/w/{wid}/scheduled-posts", {
          params: { path: { wid } },
          body: { caption: "", publish_at: publishAt ?? null },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.scheduledPostLists(wid) }),
  });
}

type MoveVars = { post: ScheduledPostSummary; publishAt: string };

/**
 * FR-PUB-08 calendar move or "Move to…": the card moves at once and goes back if the API refuses
 * (less than 5 minutes ahead, or publishing started).
 */
export function useReschedulePost(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPostDetail, Error, MoveVars, { snapshot: CalendarSnapshot }>({
    mutationFn: ({ post, publishAt }) =>
      unwrap(
        api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/reschedule", {
          params: { path: { wid, scheduled_post_id: post.id } },
          body: { publish_at: publishAt },
        }),
      ),
    onMutate: async ({ post, publishAt }) => {
      const snapshot = await snapshotCalendars(queryClient, wid);
      patchCalendars(queryClient, wid, { ...post, publish_at: publishAt });
      return { snapshot };
    },
    onError: (_error, _vars, context) => {
      if (context) restoreCalendars(queryClient, context.snapshot);
    },
    onSuccess: (post) => patchCalendars(queryClient, wid, post),
    onSettled: () => refreshSchedule(queryClient, wid),
  });
}

/** Schedule a draft at a time (a draft dropped on the calendar runs the Schedule checks). */
export function useSchedulePost(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPostDetail, Error, MoveVars>({
    mutationFn: ({ post, publishAt }) =>
      unwrap(
        api.POST("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/schedule", {
          params: { path: { wid, scheduled_post_id: post.id } },
          body: { publish_at: publishAt },
        }),
      ),
    onSuccess: (post) => {
      patchCalendars(queryClient, wid, post);
      void refreshSchedule(queryClient, wid);
    },
  });
}

function usePostAction(
  wid: string,
  path:
    | "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/queue"
    | "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/unschedule"
    | "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/duplicate",
) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ScheduledPostDetail, Error, ScheduledPostSummary>({
    mutationFn: (post) => unwrap(api.POST(path, { params: { path: { wid, scheduled_post_id: post.id } } })),
    onSuccess: (post) => {
      patchCalendars(queryClient, wid, post);
      void refreshSchedule(queryClient, wid);
    },
  });
}

/** FR-PUB-09 Add to queue: the earliest free posting time of every selected account. */
export function useQueuePost(wid: string) {
  return usePostAction(wid, "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/queue");
}

/** Back to draft, keeping its time (FR-PUB-04). */
export function useUnschedulePost(wid: string) {
  return usePostAction(wid, "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/unschedule");
}

/** FR-PUB-14: a copy as a new draft, without a time. */
export function useDuplicateScheduledPost(wid: string) {
  return usePostAction(wid, "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/duplicate");
}

export function useDeleteScheduledPost(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, ScheduledPostSummary>({
    mutationFn: (post) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/scheduled-posts/{scheduled_post_id}", {
          params: { path: { wid, scheduled_post_id: post.id } },
        }),
      ),
    onSuccess: (_, post) => {
      removeFromCalendars(queryClient, wid, post.id);
      void refreshSchedule(queryClient, wid);
    },
  });
}

/** FR-PUB-14: shift, unschedule or delete the posts selected in the List view. */
export function useBulkScheduledPosts(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<BulkScheduledPostResult, Error, BulkScheduledPostRequest>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/scheduled-posts/bulk", { params: { path: { wid } }, body })),
    onSuccess: (result) => {
      for (const post of result.updated) patchCalendars(queryClient, wid, post);
      for (const id of result.deleted_ids) removeFromCalendars(queryClient, wid, id);
      void refreshSchedule(queryClient, wid);
    },
  });
}

// ---- posting times (FR-PUB-09, UX-SCR-14)

function postingSlotsQuery(api: Api, wid: string, accountId: string) {
  return {
    queryKey: keys.postingSlots(wid, accountId),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/social-accounts/{account_id}/posting-slots", {
          params: { path: { wid, account_id: accountId } },
        }),
      ),
  };
}

export function usePostingSlots(wid: string, accountId: string | null) {
  const api = useApi();
  return useQuery<PostingSlots>({
    ...postingSlotsQuery(api, wid, accountId ?? ""),
    enabled: Boolean(accountId),
  });
}

/** The rail's "Posting times" line for each account. */
export function usePostingSlotsFor(wid: string, accountIds: string[]) {
  const api = useApi();
  return useQueries({
    queries: accountIds.map((id) => postingSlotsQuery(api, wid, id)),
  });
}

/** Replace an account's weekly times; posts already scheduled keep theirs. */
export function useReplacePostingSlots(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PostingSlots, Error, { accountId: string; slots: PostingSlot[] }>({
    mutationFn: ({ accountId, slots }) =>
      unwrap(
        api.PUT("/v1/w/{wid}/social-accounts/{account_id}/posting-slots", {
          params: { path: { wid, account_id: accountId } },
          body: { slots },
        }),
      ),
    onSuccess: (result) => {
      queryClient.setQueryData(keys.postingSlots(wid, result.social_account_id), result);
      // Free slots and the rail's next free time come from the calendar.
      void queryClient.invalidateQueries({ queryKey: keys.calendars(wid) });
    },
  });
}

// ---- hashtag groups (FR-PUB-12, UX-SCR-14)

export function useHashtagGroups(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<HashtagGroup[]>({
    queryKey: keys.hashtagGroups(wid),
    enabled,
    queryFn: async () =>
      (await unwrap(api.GET("/v1/w/{wid}/hashtag-groups", { params: { path: { wid } } }))).items,
  });
}

function byName(a: HashtagGroup, b: HashtagGroup): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
}

function useGroupsWriter(wid: string) {
  const queryClient = useQueryClient();
  return (update: (groups: HashtagGroup[]) => HashtagGroup[]) => {
    queryClient.setQueryData<HashtagGroup[]>(keys.hashtagGroups(wid), (groups) =>
      groups ? update(groups).sort(byName) : groups,
    );
    void queryClient.invalidateQueries({ queryKey: keys.hashtagGroups(wid) });
  };
}

export function useCreateHashtagGroup(wid: string) {
  const api = useApi();
  const write = useGroupsWriter(wid);
  return useMutation<HashtagGroup, Error, HashtagGroupCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/hashtag-groups", { params: { path: { wid } }, body })),
    onSuccess: (group) => write((groups) => [...groups.filter((g) => g.id !== group.id), group]),
  });
}

export function useUpdateHashtagGroup(wid: string) {
  const api = useApi();
  const write = useGroupsWriter(wid);
  return useMutation<HashtagGroup, Error, { id: string; patch: HashtagGroupPatch }>({
    mutationFn: ({ id, patch }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/hashtag-groups/{hashtag_group_id}", {
          params: { path: { wid, hashtag_group_id: id } },
          body: patch,
        }),
      ),
    onSuccess: (group) => write((groups) => groups.map((g) => (g.id === group.id ? group : g))),
  });
}

export function useDeleteHashtagGroup(wid: string) {
  const api = useApi();
  const write = useGroupsWriter(wid);
  return useMutation<void, Error, HashtagGroup>({
    mutationFn: (group) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/hashtag-groups/{hashtag_group_id}", {
          params: { path: { wid, hashtag_group_id: group.id } },
        }),
      ),
    onSuccess: (_, group) => write((groups) => groups.filter((g) => g.id !== group.id)),
  });
}
