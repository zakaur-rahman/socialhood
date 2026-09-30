"use client";

import type { components } from "@socialhood/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

export type WorkspaceDeletion = components["schemas"]["WorkspaceDeletion"];

/**
 * FR-ACC-05 / F-16: DELETE /v1/w/{wid} with the name the owner typed (the API checks it too).
 * On 202 the workspace answers 404 everywhere, so its cached data and the user's workspace list
 * are dropped: /app then loads the fresh list and lands in the next workspace (a new one when
 * this was the last).
 */
export function useDeleteWorkspace(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<WorkspaceDeletion, Error, string>({
    mutationFn: (confirmName) =>
      unwrap(api.DELETE("/v1/w/{wid}", { params: { path: { wid }, query: { confirm_name: confirmName } } })),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: keys.me });
      queryClient.removeQueries({ queryKey: keys.workspaces });
      queryClient.removeQueries({ queryKey: ["w", wid] });
    },
  });
}
