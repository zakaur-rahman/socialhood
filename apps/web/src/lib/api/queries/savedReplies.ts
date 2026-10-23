"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { SavedReply, SavedReplyCreate, SavedReplyFilled, SavedReplyList, SavedReplyUpdate } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** GR-21: the workspace's saved replies by shortcut, with the workspace's limit. */
export function useSavedReplies(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<SavedReplyList>({
    queryKey: keys.savedReplies(wid),
    enabled,
    staleTime: 60_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/saved-replies", { params: { path: { wid } } })),
  });
}

export function useCreateSavedReply(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SavedReply, Error, SavedReplyCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/saved-replies", { params: { path: { wid } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.savedReplies(wid) }),
  });
}

export function useUpdateSavedReply(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SavedReply, Error, { id: string; body: SavedReplyUpdate }>({
    mutationFn: ({ id, body }) =>
      unwrap(api.PATCH("/v1/w/{wid}/saved-replies/{reply_id}", { params: { path: { wid, reply_id: id } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.savedReplies(wid) }),
  });
}

export function useDeleteSavedReply(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/saved-replies/{reply_id}", { params: { path: { wid, reply_id: id } } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.savedReplies(wid) }),
  });
}

/** The reply filled in for the conversation's contact (the server fills it, so the composer and a
 * flow read the same). */
export function useFillSavedReply(wid: string) {
  const api = useApi();
  return useMutation<SavedReplyFilled, Error, { id: string; conversationId: string }>({
    mutationFn: ({ id, conversationId }) =>
      unwrap(
        api.POST("/v1/w/{wid}/saved-replies/{reply_id}/fill", {
          params: { path: { wid, reply_id: id } },
          body: { conversation_id: conversationId },
        }),
      ),
  });
}
