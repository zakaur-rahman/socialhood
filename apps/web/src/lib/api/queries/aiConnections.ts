"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  AiConnectionActivity,
  AiConnectionList,
  AiConnectionsMode,
  AiConnectionsSettings,
  ConnectApproval,
  ConnectRedirect,
  ConnectRequest,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** C-165: what AI apps may do in the workspace (owners and admins). */
export function useAiConnectionsSettings(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<AiConnectionsSettings>({
    queryKey: keys.aiConnectionsSettings(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/ai-connections/settings", { params: { path: { wid } } })),
    enabled,
  });
}

export function useUpdateAiConnectionsMode(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<AiConnectionsSettings, Error, AiConnectionsMode>({
    mutationFn: (mode) =>
      unwrap(api.PUT("/v1/w/{wid}/ai-connections/settings", { params: { path: { wid } }, body: { mode } })),
    onSuccess: (data) => qc.setQueryData(keys.aiConnectionsSettings(wid), data),
  });
}

/** C-165 phase C: the live OAuth connections (everyone's for owners and admins, else your own). */
export function useAiConnections(wid: string) {
  const api = useApi();
  return useQuery<AiConnectionList>({
    queryKey: keys.aiConnections(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/ai-connections", { params: { path: { wid } } })),
  });
}

export function useAiConnectionActivity(wid: string, id: string, enabled: boolean) {
  const api = useApi();
  return useQuery<AiConnectionActivity>({
    queryKey: keys.aiConnectionActivity(wid, id),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/ai-connections/{connection_id}/activity", {
          params: { path: { wid, connection_id: id } },
        }),
      ),
    enabled,
  });
}

export function useRevokeAiConnection(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/ai-connections/{connection_id}", { params: { path: { wid, connection_id: id } } }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.aiConnections(wid) }),
  });
}

export function useRevokeAllAiConnections(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<{ revoked: number }, Error, void>({
    mutationFn: () => unwrap(api.POST("/v1/w/{wid}/ai-connections/revoke-all", { params: { path: { wid } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.aiConnections(wid) }),
  });
}

/** The consent page: the waiting authorization request (it lives 10 minutes, decided once). */
export function useConnectRequest(id: string) {
  const api = useApi();
  return useQuery<ConnectRequest>({
    queryKey: keys.connectRequest(id),
    queryFn: () =>
      unwrap(api.GET("/v1/connect/requests/{request_id}", { params: { path: { request_id: id } } })),
    enabled: Boolean(id),
    retry: false,
    staleTime: Infinity,
  });
}

export function useApproveConnect(id: string) {
  const api = useApi();
  return useMutation<ConnectRedirect, Error, ConnectApproval>({
    mutationFn: (body) =>
      unwrap(api.POST("/v1/connect/requests/{request_id}/approve", { params: { path: { request_id: id } }, body })),
  });
}

export function useDenyConnect(id: string) {
  const api = useApi();
  return useMutation<ConnectRedirect, Error, void>({
    mutationFn: () =>
      unwrap(api.POST("/v1/connect/requests/{request_id}/deny", { params: { path: { request_id: id } } })),
  });
}
