"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { BusinessHours, BusinessHoursOverview, BusinessHoursUpdate } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** GR-22: the workspace's schedule and each account's own, in the workspace time zone. */
export function useBusinessHours(wid: string) {
  const api = useApi();
  return useQuery<BusinessHoursOverview>({
    queryKey: keys.businessHours(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/business-hours", { params: { path: { wid } } })),
  });
}

/** Save the workspace's schedule, or (with an account id) that account's own. */
export function useSaveBusinessHours(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<BusinessHours, Error, { accountId: string | null; body: BusinessHoursUpdate }>({
    mutationFn: ({ accountId, body }) =>
      accountId
        ? unwrap(
            api.PUT("/v1/w/{wid}/social-accounts/{account_id}/business-hours", {
              params: { path: { wid, account_id: accountId } },
              body,
            }),
          )
        : unwrap(api.PUT("/v1/w/{wid}/business-hours", { params: { path: { wid } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.businessHours(wid) }),
  });
}

/** The account goes back to the workspace's schedule. */
export function useRemoveAccountHours(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (accountId) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/social-accounts/{account_id}/business-hours", {
          params: { path: { wid, account_id: accountId } },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.businessHours(wid) }),
  });
}
