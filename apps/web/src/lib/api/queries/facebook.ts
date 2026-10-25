"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { FacebookPageList, SocialAccount } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** GR-29: returns Facebook's authorize URL; the caller navigates there. */
export function useStartFacebookConnect(wid: string) {
  const api = useApi();
  return useMutation<string, Error, void>({
    mutationFn: async () =>
      (await unwrap(api.POST("/v1/w/{wid}/social-accounts/facebook/connect", { params: { path: { wid } } })))
        .authorize_url,
  });
}

/**
 * GR-29, X-1: Facebook's callback sends the browser back with ?facebook=<nonce>; this lists the
 * Pages the person who started the connect manages. Only that member can read it (403 otherwise),
 * within 10 minutes (404 after). Asking again with the same nonce returns the same list.
 */
export function useFacebookPages(wid: string) {
  const api = useApi();
  return useMutation<FacebookPageList, Error, string>({
    mutationFn: (nonce) =>
      unwrap(api.POST("/v1/w/{wid}/social-accounts/facebook/pages", { params: { path: { wid } }, body: { nonce } })),
  });
}

/** GR-29: connect the Pages the person picked. A 402 opens the upgrade dialog like any other. */
export function useConnectFacebookPages(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SocialAccount[], Error, { nonce: string; pageIds: string[] }>({
    mutationFn: async ({ nonce, pageIds }) =>
      (
        await unwrap(
          api.POST("/v1/w/{wid}/social-accounts/facebook/connect-pages", {
            params: { path: { wid } },
            body: { nonce, page_ids: pageIds },
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
