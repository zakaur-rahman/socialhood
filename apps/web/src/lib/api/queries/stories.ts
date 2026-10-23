"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { Story, StoryList, StoryMentionList } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

const MENTIONS_PAGE = 30;

/**
 * The story picker (GR-06): the account's live stories, read from Instagram, newest first. Stories
 * last 24 hours, so a minute is as stale as the list should get while the picker is open.
 */
export function useStories(wid: string, accountId: string | null, enabled = true) {
  const api = useApi();
  return useQuery<StoryList, Error, Story[]>({
    queryKey: keys.stories(wid, accountId),
    enabled: enabled && Boolean(accountId),
    staleTime: 60_000,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/stories", { params: { path: { wid }, query: { account_id: accountId ?? "" } } }),
      ),
    select: (list) => list.items,
  });
}

/** The Mentions list (GR-07), newest first, one account's or every account's. */
export function useStoryMentions(wid: string, accountId: string | null) {
  const api = useApi();
  return useInfiniteQuery<
    StoryMentionList,
    Error,
    { pages: StoryMentionList[]; pageParams: (string | null)[] },
    ReturnType<typeof keys.storyMentions>,
    string | null
  >({
    queryKey: keys.storyMentions(wid, accountId),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/story-mentions", {
          params: {
            path: { wid },
            query: { account_id: accountId ?? undefined, cursor: pageParam ?? undefined, limit: MENTIONS_PAGE },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}
