/**
 * Real-time events patch the query cache (TR-FE-04, TR-RT-03). Payloads carry the same
 * projections the REST endpoints return, so nothing is refetched except on resync.
 */
import type { QueryClient } from "@tanstack/react-query";

import { keys } from "@/lib/api/queries/keys";
import type {
  ConversationListItem,
  Message,
  MessageAnalysis,
  NotificationItem,
  NotificationList,
  ScheduledMessage,
  SocialAccount,
  Suggestion,
} from "@/lib/api/types";
import {
  applyConversation,
  applyMessage,
  applyScheduled,
  setLatestAnalysis,
  setPendingSuggestion,
} from "@/lib/inbox/cache";
import { useInboxStore } from "@/lib/inbox/store";

import type { SseEvent } from "./sse";

export type EventPayloads = {
  "message.created": { conversation_id: string; message: Message };
  "message.updated": { conversation_id: string; message: Message };
  "conversation.updated": { conversation: ConversationListItem };
  "analysis.created": { conversation_id: string; analysis: MessageAnalysis };
  "suggestion.created": { conversation_id: string; suggestion: Suggestion };
  "suggestion.updated": { conversation_id: string; suggestion: Suggestion };
  "scheduled_message.updated": { scheduled_message: ScheduledMessage };
  "social_account.updated": { social_account: SocialAccount };
  "notification.created": { notification: NotificationItem };
  /** Only the fact matters: the billing state is refetched. */
  "usage.updated": Record<string, unknown>;
  resync: Record<string, never>;
};

export type ApplyOptions = {
  /** The conversation on screen: it stays in its list even if it stops matching the filter. */
  openConversationId?: string | null;
};

/** Everything under ["w", wid]: after a resync, or a reconnect that could not resume. */
export function invalidateWorkspace(queryClient: QueryClient, wid: string): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: ["w", wid] });
}

function parse<T>(data: string): T | null {
  try {
    return (data ? JSON.parse(data) : {}) as T;
  } catch {
    return null;
  }
}

export function applyRealtimeEvent(
  queryClient: QueryClient,
  wid: string,
  event: SseEvent,
  options: ApplyOptions = {},
): void {
  switch (event.event) {
    case "message.created":
    case "message.updated": {
      const payload = parse<EventPayloads["message.created"]>(event.data);
      if (!payload?.message) return;
      const conversationId = payload.conversation_id ?? payload.message.conversation_id;
      applyMessage(queryClient, wid, conversationId, payload.message);
      // The server's copy replaces the optimistic bubble (TR-FE-05).
      if (payload.message.client_id) useInboxStore.getState().removeOutbox(payload.message.client_id);
      return;
    }
    case "conversation.updated": {
      const payload = parse<EventPayloads["conversation.updated"]>(event.data);
      if (!payload?.conversation) return;
      applyConversation(queryClient, wid, payload.conversation, { keepId: options.openConversationId });
      void queryClient.invalidateQueries({ queryKey: keys.inboxCounts(wid) });
      return;
    }
    case "analysis.created": {
      const payload = parse<EventPayloads["analysis.created"]>(event.data);
      if (!payload?.analysis) return;
      setLatestAnalysis(queryClient, wid, payload.conversation_id, payload.analysis);
      return;
    }
    case "suggestion.created":
    case "suggestion.updated": {
      const payload = parse<EventPayloads["suggestion.created"]>(event.data);
      if (!payload?.suggestion) return;
      const { suggestion } = payload;
      const conversationId = payload.conversation_id ?? suggestion.conversation_id;
      if (suggestion.status === "pending") setPendingSuggestion(queryClient, wid, conversationId, suggestion);
      else setPendingSuggestion(queryClient, wid, conversationId, null, suggestion.id);
      return;
    }
    case "usage.updated":
      // FR-AI-05: credits used or reset; the banner and meters read GET …/billing.
      void queryClient.invalidateQueries({ queryKey: keys.billing(wid) });
      return;
    case "scheduled_message.updated": {
      const payload = parse<EventPayloads["scheduled_message.updated"]>(event.data);
      if (!payload?.scheduled_message) return;
      applyScheduled(queryClient, wid, payload.scheduled_message);
      return;
    }
    case "social_account.updated": {
      const payload = parse<EventPayloads["social_account.updated"]>(event.data);
      if (!payload?.social_account) return;
      const account = payload.social_account;
      queryClient.setQueryData<SocialAccount[]>(keys.accounts(wid), (items) => {
        if (!items) return items;
        return items.some((item) => item.id === account.id)
          ? items.map((item) => (item.id === account.id ? account : item))
          : [...items, account];
      });
      return;
    }
    case "notification.created": {
      const payload = parse<EventPayloads["notification.created"]>(event.data);
      if (!payload?.notification) return;
      const { notification } = payload;
      queryClient.setQueryData<NotificationList>(keys.notifications(wid), (list) =>
        list && !list.items.some((item) => item.id === notification.id)
          ? {
              ...list,
              items: [notification, ...list.items],
              unread_count: list.unread_count + (notification.read_at ? 0 : 1),
            }
          : list,
      );
      return;
    }
    case "resync":
      void invalidateWorkspace(queryClient, wid);
      return;
    default:
      // Events for pages built in later phases (comments, posts) have no cache yet.
      return;
  }
}
