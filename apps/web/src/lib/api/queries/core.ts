"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { toApiError } from "../errors";
import { useApi } from "../provider";
import type {
  Me,
  NotificationList,
  Overview,
  SocialAccount,
  SocialAccountPatch,
  Workspace,
  WorkspacePatch,
  WorkspaceSummary,
} from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

export function useMe() {
  const api = useApi();
  return useQuery<Me>({ queryKey: keys.me, queryFn: () => unwrap(api.GET("/v1/me")) });
}

export function useWorkspaces() {
  const api = useApi();
  return useQuery<WorkspaceSummary[]>({
    queryKey: keys.workspaces,
    queryFn: async () => (await unwrap(api.GET("/v1/workspaces"))).items,
  });
}

export function useWorkspace(wid: string) {
  const api = useApi();
  return useQuery<Workspace>({
    queryKey: keys.workspace(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}", { params: { path: { wid } } })),
  });
}

export function useOverview(wid: string, range: "7d" | "30d" = "7d") {
  const api = useApi();
  return useQuery<Overview>({
    queryKey: keys.overview(wid, range),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/overview", { params: { path: { wid }, query: { range } } })),
  });
}

export function useUpdateWorkspace(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Workspace, Error, WorkspacePatch>({
    mutationFn: (body) => unwrap(api.PATCH("/v1/w/{wid}", { params: { path: { wid } }, body })),
    onSuccess: async (workspace) => {
      queryClient.setQueryData(keys.workspace(wid), workspace);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.workspaces }),
        queryClient.invalidateQueries({ queryKey: keys.me }),
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}

// ---- connected accounts (FR-CON-01…06)

export function useSocialAccounts(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<SocialAccount[]>({
    queryKey: keys.accounts(wid),
    enabled,
    queryFn: async () =>
      (await unwrap(api.GET("/v1/w/{wid}/social-accounts", { params: { path: { wid } } }))).items,
  });
}

/** F-03: returns Instagram's authorize URL; the caller navigates there. */
export function useStartInstagramConnect(wid: string) {
  const api = useApi();
  return useMutation<string, Error, void>({
    mutationFn: async () =>
      (
        await unwrap(
          api.POST("/v1/w/{wid}/social-accounts/instagram/connect", { params: { path: { wid } } }),
        )
      ).authorize_url,
  });
}

function useAccountMutation<TVars>(
  wid: string,
  call: (vars: TVars) => Promise<SocialAccount | null>,
) {
  const queryClient = useQueryClient();
  return useMutation<SocialAccount | null, Error, TVars>({
    mutationFn: call,
    onSuccess: async (account) => {
      if (account) {
        queryClient.setQueryData<SocialAccount[]>(keys.accounts(wid), (items) =>
          items?.map((item) => (item.id === account.id ? account : item)),
        );
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.accounts(wid) }),
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}

export function useUpdateAccount(wid: string) {
  const api = useApi();
  return useAccountMutation(wid, ({ id, patch }: { id: string; patch: SocialAccountPatch }) =>
    unwrap(
      api.PATCH("/v1/w/{wid}/social-accounts/{account_id}", {
        params: { path: { wid, account_id: id } },
        body: patch,
      }),
    ),
  );
}

export function useResubscribeAccount(wid: string) {
  const api = useApi();
  return useAccountMutation(wid, (id: string) =>
    unwrap(
      api.POST("/v1/w/{wid}/social-accounts/{account_id}/resubscribe", {
        params: { path: { wid, account_id: id } },
      }),
    ),
  );
}

export function useDisconnectAccount(wid: string) {
  const api = useApi();
  return useAccountMutation(wid, async ({ id, deleteData }: { id: string; deleteData: boolean }) => {
    const { error, response } = await api.DELETE("/v1/w/{wid}/social-accounts/{account_id}", {
      params: { path: { wid, account_id: id }, query: { delete_data: deleteData } },
    });
    if (!response.ok) throw toApiError(error, response.status);
    return null;
  });
}

/** TR-PL-07: a fake Instagram account for local development (404 unless the API enables it). */
export function useCreateSandboxAccount(wid: string) {
  const api = useApi();
  return useAccountMutation(wid, () =>
    unwrap(api.POST("/v1/w/{wid}/dev/sandbox/accounts", { params: { path: { wid } } })),
  );
}

// ---- notifications (FR-NOT-01)

export function useNotifications(wid: string) {
  const api = useApi();
  return useQuery<NotificationList>({
    queryKey: keys.notifications(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/notifications", { params: { path: { wid } } })),
    refetchInterval: 60_000, // real-time events arrive in P3 (TR-RT-01)
  });
}

export function useMarkNotificationsRead(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, { ids?: string[]; all?: boolean }>({
    mutationFn: async ({ ids, all = false }) => {
      const { error, response } = await api.POST("/v1/w/{wid}/notifications/read", {
        params: { path: { wid } },
        body: { ids, all },
      });
      if (!response.ok) throw toApiError(error, response.status);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.notifications(wid) }),
  });
}
