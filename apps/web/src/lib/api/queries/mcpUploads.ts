"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { McpUploadTicket } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** An upload ticket an AI app asked for (C-165), with the signed fields while it waits. */
export function useMcpUpload(wid: string, id: string) {
  const api = useApi();
  return useQuery<McpUploadTicket>({
    queryKey: keys.mcpUpload(wid, id),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/mcp-uploads/{upload_id}", { params: { path: { wid, upload_id: id } } })),
    refetchOnWindowFocus: false,
  });
}

/** After the file reached storage: add it to the media library under the ticket. */
export function useCompleteMcpUpload(wid: string, id: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<McpUploadTicket, Error, string>({
    mutationFn: (public_id) =>
      unwrap(
        api.POST("/v1/w/{wid}/mcp-uploads/{upload_id}/complete", {
          params: { path: { wid, upload_id: id } },
          body: { public_id },
        }),
      ),
    onSuccess: (ticket) => qc.setQueryData(keys.mcpUpload(wid, id), ticket),
  });
}
