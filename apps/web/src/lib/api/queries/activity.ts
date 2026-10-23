"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { ActivityItem, ActivityList } from "../types";
import { keys, type ActivityFilters } from "./keys";
import { unwrap } from "./unwrap";

const PAGE = 30;

export type ActivityPages = { pages: ActivityList[]; pageParams: (string | null)[] };

/** The Activity page (GR-05): failures first, newest first, in cursor pages. */
export function useActivity(wid: string, filters: ActivityFilters) {
  const api = useApi();
  return useInfiniteQuery<ActivityList, Error, ActivityPages, ReturnType<typeof keys.activity>, string | null>({
    queryKey: keys.activity(wid, filters),
    initialPageParam: null,
    // A new filter keeps the rows on screen until its results arrive.
    placeholderData: (previous) => previous,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/activity", {
          params: {
            path: { wid },
            query: {
              failures_only: filters.failuresOnly,
              kind: filters.kind ?? undefined,
              automation_id: filters.automationId ?? undefined,
              account_id: filters.accountId ?? undefined,
              cursor: pageParam ?? undefined,
              limit: PAGE,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/**
 * Retry one item where retrying is safe: a failed message goes through the message retry route
 * (the same row, one send), a failed webhook delivery through the replay route (a new delivery of
 * the same event). The list refreshes either way.
 */
export function useRetryActivity(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<void, Error, ActivityItem>({
    mutationFn: async (item) => {
      const retry = item.retry;
      if (!retry) return;
      if (retry.kind === "message") {
        await unwrap(
          api.POST("/v1/w/{wid}/messages/{message_id}/retry", {
            params: { path: { wid, message_id: retry.target_id } },
          }),
        );
      } else {
        await unwrap(
          api.POST("/v1/w/{wid}/webhook-deliveries/{delivery_id}/replay", {
            params: { path: { wid, delivery_id: retry.target_id } },
          }),
        );
      }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.activityLists(wid) }),
  });
}
