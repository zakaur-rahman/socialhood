"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { IceBreakerList, IceBreakersUpdate } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** An Instagram account's conversation starters and how the last sync went (GR-11). */
export function useIceBreakers(wid: string, accountId: string | null) {
  const api = useApi();
  return useQuery<IceBreakerList>({
    queryKey: keys.iceBreakers(wid, accountId ?? ""),
    enabled: Boolean(accountId),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/social-accounts/{account_id}/ice-breakers", {
          params: { path: { wid, account_id: accountId ?? "" } },
        }),
      ),
  });
}

/** Save the whole list; the API pushes it to Instagram and reports a failed push in the list. */
export function useSaveIceBreakers(wid: string, accountId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<IceBreakerList, Error, IceBreakersUpdate>({
    mutationFn: (body) =>
      unwrap(
        api.PUT("/v1/w/{wid}/social-accounts/{account_id}/ice-breakers", {
          params: { path: { wid, account_id: accountId } },
          body,
        }),
      ),
    onSuccess: (list) => queryClient.setQueryData(keys.iceBreakers(wid, accountId), list),
  });
}

/** Push the saved list to Instagram again. */
export function useSyncIceBreakers(wid: string, accountId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<IceBreakerList, Error, void>({
    mutationFn: () =>
      unwrap(
        api.POST("/v1/w/{wid}/social-accounts/{account_id}/ice-breakers/sync", {
          params: { path: { wid, account_id: accountId } },
        }),
      ),
    onSuccess: (list) => queryClient.setQueryData(keys.iceBreakers(wid, accountId), list),
  });
}
