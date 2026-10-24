"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { ApiKey, ApiKeyCreate, ApiKeyList, ApiKeyWithKey } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** A workspace's API keys, newest first, and the scopes a key can carry (GR-25). */
export function useApiKeys(wid: string) {
  const api = useApi();
  return useQuery<ApiKeyList>({
    queryKey: keys.apiKeys(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/api-keys", { params: { path: { wid } } })),
  });
}

/** Make a key. The response carries the key itself, this once. */
export function useCreateApiKey(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<ApiKeyWithKey, Error, ApiKeyCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/api-keys", { params: { path: { wid } }, body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.apiKeys(wid) }),
  });
}

export function useRevokeApiKey(wid: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<ApiKey, Error, string>({
    mutationFn: (id) =>
      unwrap(api.DELETE("/v1/w/{wid}/api-keys/{key_id}", { params: { path: { wid, key_id: id } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.apiKeys(wid) }),
  });
}
