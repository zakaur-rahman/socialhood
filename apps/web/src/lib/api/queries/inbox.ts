"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  applyConversation,
  patchConversationEverywhere,
  type ConversationPages,
  type MessagePages,
} from "@/lib/inbox/cache";

import { useApi } from "../provider";
import type { Conversation, ConversationList, ConversationPatch, InboxCounts, MessageList } from "../types";
import { keys, type ConversationFilters } from "./keys";
import { expectOk, unwrap } from "./unwrap";

const PAGE = 30;

/** FR-INB-01: server-side filters and search, cursor pages (TR-API-04). */
export function useConversations(wid: string, filters: ConversationFilters) {
  const api = useApi();
  return useInfiniteQuery<ConversationList, Error, ConversationPages, ReturnType<typeof keys.conversations>, string | null>({
    queryKey: keys.conversations(wid, filters),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/conversations", {
          params: {
            path: { wid },
            query: {
              view: filters.view,
              platform: filters.platform ?? undefined,
              account_id: filters.accountId ?? undefined,
              q: filters.q.trim() || undefined,
              cursor: pageParam ?? undefined,
              limit: PAGE,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** The Inbox nav badge (FR-INB-04); kept fresh by conversation.updated. */
export function useInboxCounts(wid: string) {
  const api = useApi();
  return useQuery<InboxCounts>({
    queryKey: keys.inboxCounts(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/conversations/counts", { params: { path: { wid } } })),
  });
}

export function useConversation(wid: string, id: string | null) {
  const api = useApi();
  return useQuery<Conversation>({
    queryKey: keys.conversation(wid, id ?? ""),
    enabled: Boolean(id),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/conversations/{conversation_id}", {
          params: { path: { wid, conversation_id: id ?? "" } },
        }),
      ),
  });
}

const MESSAGE_PAGE = 50;

/** Newest page first; the next page holds older messages (upward infinite scroll). */
export function useMessages(wid: string, conversationId: string) {
  const api = useApi();
  return useInfiniteQuery<MessageList, Error, MessagePages, ReturnType<typeof keys.messages>, string | null>({
    queryKey: keys.messages(wid, conversationId),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/conversations/{conversation_id}/messages", {
          params: {
            path: { wid, conversation_id: conversationId },
            query: { cursor: pageParam ?? undefined, limit: MESSAGE_PAGE },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** FR-INB-04: opening a conversation marks it read. The badge follows. */
export function useMarkRead(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.POST("/v1/w/{wid}/conversations/{conversation_id}/read", { params: { path: { wid, conversation_id: id } } })),
    onMutate: (id) => patchConversationEverywhere(queryClient, wid, id, { unread_count: 0 }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.inboxCounts(wid) }),
  });
}

export function useMarkUnread(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/unread", { params: { path: { wid, conversation_id: id } } }),
      ),
    onMutate: (id) => patchConversationEverywhere(queryClient, wid, id, { unread_count: 1 }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.inboxCounts(wid) }),
  });
}

/** Archive or unarchive (FR-INB-05); the response updates every list and the detail. */
export function useUpdateConversation(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Conversation, Error, { id: string; patch: Partial<ConversationPatch> }>({
    mutationFn: ({ id, patch }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/conversations/{conversation_id}", {
          params: { path: { wid, conversation_id: id } },
          body: { clear_ai_mode_override: false, resume_ai: false, ...patch },
        }),
      ),
    onSuccess: (conversation) => {
      queryClient.setQueryData(keys.conversation(wid, conversation.id), conversation);
      applyConversation(queryClient, wid, conversation);
      void queryClient.invalidateQueries({ queryKey: keys.inboxCounts(wid) });
    },
  });
}
