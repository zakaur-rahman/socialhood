"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { toApiError } from "./errors";
import { useApi } from "./provider";
import type { Me, Overview, Workspace, WorkspacePatch, WorkspaceSummary } from "./types";

/** Query keys (TR-FE-03): everything workspace-scoped starts with ["w", workspaceId]. */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (wid: string) => ["w", wid, "workspace"] as const,
  overview: (wid: string, range: "7d" | "30d") => ["w", wid, "overview", range] as const,
};

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return the data of an openapi-fetch call, or throw an ApiError (problem+json or network). */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (error) {
    throw toApiError(error);
  }
  if (result.error !== undefined || result.data === undefined) {
    throw toApiError(result.error, result.response.status);
  }
  return result.data;
}

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
