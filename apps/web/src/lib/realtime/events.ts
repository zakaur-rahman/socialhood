/**
 * Real-time events patch the query cache (TR-FE-04, TR-RT-03). Payloads carry the same
 * projections the REST endpoints return, so nothing is refetched except on resync.
 */
import type { QueryClient } from "@tanstack/react-query";

import { applyAgentRunEvent, applyAgentStepEvent } from "@/lib/agent/cache";
import { keys } from "@/lib/api/queries/keys";
import { applyComposerPost } from "@/lib/api/queries/scheduledPosts";
import type {
  AgentRunEvent,
  AgentStepEvent,
  ConversationListItem,
  Message,
  MessageAnalysis,
  NotificationItem,
  NotificationList,
  PostComment,
  PostDetail,
  ScheduledMessage,
  ScheduledPostDetail,
  SocialAccount,
  Suggestion,
} from "@/lib/api/types";
import { applyComment, applyPost } from "@/lib/comments/cache";
import {
  applyConversation,
  applyMessage,
  applyScheduled,
  setLatestAnalysis,
  setPendingSuggestion,
} from "@/lib/inbox/cache";
import { useInboxStore } from "@/lib/inbox/store";
import { applyCalendarMessage, applyScheduledPost } from "@/lib/schedule/cache";

import type { SseEvent } from "./sse";

export type EventPayloads = {
  "message.created": { conversation_id: string; message: Message };
  "message.updated": { conversation_id: string; message: Message };
  "conversation.updated": { conversation: ConversationListItem };
  "analysis.created": { conversation_id: string; analysis: MessageAnalysis };
  "suggestion.created": { conversation_id: string; suggestion: Suggestion };
  "suggestion.updated": { conversation_id: string; suggestion: Suggestion };
  "scheduled_message.updated": { scheduled_message: ScheduledMessage };
  /** P7: a post was saved, scheduled, moved, or went through a publishing step. */
  "scheduled_post.updated": { scheduled_post: ScheduledPostDetail };
  "social_account.updated": { social_account: SocialAccount };
  "notification.created": { notification: NotificationItem };
  /** F-12: a comment arrived, or its analysis, reply, hidden state or deletion changed. */
  "comment.created": { comment: PostComment };
  "comment.updated": { comment: PostComment };
  /** F-12: a post's counts, sentiment split, summary or topics changed. */
  "post.updated": { post: PostDetail };
  /** PA: a run's status or progress changed; agent.completed when it reached a final status. */
  "agent.run.updated": { run: AgentRunEvent };
  "agent.completed": { run: AgentRunEvent };
  /** PA: a step started (running) or ended, in plain words. */
  "agent.step": AgentStepEvent;
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
      applyCalendarMessage(queryClient, wid, payload.scheduled_message);
      return;
    }
    case "scheduled_post.updated": {
      const payload = parse<EventPayloads["scheduled_post.updated"]>(event.data);
      if (!payload?.scheduled_post) return;
      applyScheduledPost(queryClient, wid, payload.scheduled_post); // calendar and lists
      applyComposerPost(queryClient, wid, payload.scheduled_post); // an open composer
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
    case "comment.created":
    case "comment.updated": {
      const payload = parse<EventPayloads["comment.updated"]>(event.data);
      if (!payload?.comment) return;
      applyComment(queryClient, wid, payload.comment);
      void queryClient.invalidateQueries({ queryKey: keys.commentCounts(wid) });
      return;
    }
    case "post.updated": {
      const payload = parse<EventPayloads["post.updated"]>(event.data);
      if (!payload?.post) return;
      applyPost(queryClient, wid, payload.post);
      return;
    }
    case "agent.run.updated":
    case "agent.completed": {
      const payload = parse<EventPayloads["agent.run.updated"]>(event.data);
      if (!payload?.run?.id) return;
      applyAgentRunEvent(queryClient, wid, payload.run, event.event === "agent.completed");
      return;
    }
    case "agent.step": {
      const payload = parse<EventPayloads["agent.step"]>(event.data);
      if (!payload?.run_id || !payload.step?.id) return;
      applyAgentStepEvent(queryClient, wid, payload);
      return;
    }
    case "resync":
      void invalidateWorkspace(queryClient, wid);
      return;
    default:
      return;
  }
}
