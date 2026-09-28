"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyScheduled, removeScheduled, type ScheduledPages } from "@/lib/inbox/cache";
import { uuid } from "@/lib/uuid";

import { useApi } from "../provider";
import type { ScheduledMessage, ScheduledMessageCreate, ScheduledMessageList, ScheduledMessagePatch } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** The inbox's Scheduled tab (FR-SMS-02, UX-INB-10): pending first, then recent outcomes. */
export function useScheduledMessages(wid: string) {
  const api = useApi();
  return useInfiniteQuery<ScheduledMessageList, Error, ScheduledPages, ReturnType<typeof keys.scheduled>, string | null>({
    queryKey: keys.scheduled(wid),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/scheduled-messages", {
          params: { path: { wid }, query: { cursor: pageParam ?? undefined, limit: 50 } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

export function useConversationScheduled(wid: string, conversationId: string, enabled = true) {
  const api = useApi();
  return useQuery<ScheduledMessageList>({
    queryKey: keys.scheduledFor(wid, conversationId),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/conversations/{conversation_id}/scheduled-messages", {
          params: { path: { wid, conversation_id: conversationId } },
        }),
      ),
  });
}

function useAfterScheduleChange(wid: string) {
  const queryClient = useQueryClient();
  return (scheduled: ScheduledMessage) => {
    applyScheduled(queryClient, wid, scheduled);
    // scheduled_count on the conversation detail.
    void queryClient.invalidateQueries({ queryKey: keys.conversation(wid, scheduled.conversation_id), exact: true });
  };
}

/** F-10: schedule a reply inside the window. */
export function useCreateScheduled(wid: string, conversationId: string) {
  const api = useApi();
  const after = useAfterScheduleChange(wid);
  return useMutation<ScheduledMessage, Error, ScheduledMessageCreate & { idempotencyKey?: string }>({
    mutationFn: ({ idempotencyKey, ...body }) =>
      unwrap(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/scheduled-messages", {
          params: { path: { wid, conversation_id: conversationId } },
          // TR-API-05 asks for a key on scheduling; the contract does not declare it yet.
          headers: { "Idempotency-Key": idempotencyKey ?? uuid() },
          body,
        }),
      ),
    onSuccess: after,
  });
}

export function useUpdateScheduled(wid: string) {
  const api = useApi();
  const after = useAfterScheduleChange(wid);
  return useMutation<ScheduledMessage, Error, { id: string; patch: ScheduledMessagePatch }>({
    mutationFn: ({ id, patch }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/scheduled-messages/{scheduled_message_id}", {
          params: { path: { wid, scheduled_message_id: id } },
          body: patch,
        }),
      ),
    onSuccess: after,
  });
}

export function useCancelScheduled(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, ScheduledMessage>({
    mutationFn: (scheduled) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/scheduled-messages/{scheduled_message_id}", {
          params: { path: { wid, scheduled_message_id: scheduled.id } },
        }),
      ),
    onSuccess: (_, scheduled) => {
      removeScheduled(queryClient, wid, scheduled);
      void queryClient.invalidateQueries({ queryKey: keys.conversation(wid, scheduled.conversation_id), exact: true });
    },
  });
}
