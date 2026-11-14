"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { SocialAccount, YouTubeChannelList } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** YouTube: returns Google's authorize URL; the caller navigates there. */
export function useStartYouTubeConnect(wid: string) {
  const api = useApi();
  return useMutation<string, Error, void>({
    mutationFn: async () =>
      (await unwrap(api.POST("/v1/w/{wid}/social-accounts/youtube/connect", { params: { path: { wid } } })))
        .authorize_url,
  });
}

/** Google's callback sends the browser back with ?youtube=<nonce>; this lists the channels of the Google account. */
export function useYouTubeChannels(wid: string) {
  const api = useApi();
  return useMutation<YouTubeChannelList, Error, string>({
    mutationFn: (nonce) =>
      unwrap(api.POST("/v1/w/{wid}/social-accounts/youtube/channels", { params: { path: { wid } }, body: { nonce } })),
  });
}

/** Connect the one channel the person picked. A 402 opens the upgrade dialog like any other. */
export function useConnectYouTubeChannels(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SocialAccount[], Error, { nonce: string; channelIds: string[] }>({
    mutationFn: async ({ nonce, channelIds }) =>
      (
        await unwrap(
          api.POST("/v1/w/{wid}/social-accounts/youtube/connect-channels", {
            params: { path: { wid } },
            body: { nonce, channel_ids: channelIds },
          }),
        )
      ).items,
    onSuccess: async (accounts) => {
      const ids = new Set(accounts.map((account) => account.id));
      queryClient.setQueryData<SocialAccount[]>(keys.accounts(wid), (items) =>
        items ? [...items.filter((item) => !ids.has(item.id)), ...accounts] : items,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.accounts(wid) }),
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}
