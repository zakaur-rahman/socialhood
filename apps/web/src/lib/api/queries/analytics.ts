"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { AgeName, PostComparison, PostPerformance } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/**
 * FR-ANL-02: one post's figures at an age. Without an age, the latest window the post has
 * reached; the answer says which age it used.
 */
export function usePostPerformance(wid: string, postId: string, age: AgeName | null) {
  const api = useApi();
  return useQuery<PostPerformance>({
    queryKey: keys.postPerformance(wid, postId, age),
    // Another age keeps the figures on screen until its own arrive.
    placeholderData: keepPreviousData,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/analytics/posts/{post_id}/performance", {
          params: { path: { wid, post_id: postId }, query: { age: age ?? undefined } },
        }),
      ),
  });
}

/**
 * TR-AGT-05: the post against the account's previous posts of the same format at the same age
 * (the API's defaults: the previous 10). ``enough_history`` is false below 3 comparable posts.
 */
export function usePostComparison(wid: string, postId: string, age: AgeName | null) {
  const api = useApi();
  return useQuery<PostComparison>({
    queryKey: keys.postComparison(wid, postId, age),
    placeholderData: keepPreviousData,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/analytics/posts/{post_id}/compare", {
          params: { path: { wid, post_id: postId }, query: { age: age ?? undefined } },
        }),
      ),
  });
}
