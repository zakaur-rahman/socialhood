/**
 * Cache patching for the inbox (TR-FE-04). Real-time events and mutations both go through these
 * functions, so a conversation or message looks the same whichever arrived first. They only
 * touch caches that are already loaded; they never create a list from nothing.
 */
import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import { keys, type ConversationFilters } from "@/lib/api/queries/keys";
import type {
  Conversation,
  ConversationList,
  ConversationListItem,
  Message,
  MessageList,
  ScheduledMessage,
  ScheduledMessageList,
} from "@/lib/api/types";

export type ConversationPages = InfiniteData<ConversationList, string | null>;
export type MessagePages = InfiniteData<MessageList, string | null>;
export type ScheduledPages = InfiniteData<ScheduledMessageList, string | null>;

/** FR-INB-01 "Leads" threshold, as the API's LEAD_SCORE. */
export const LEAD_SCORE = 60;

// ---- conversation lists

/**
 * Whether an item belongs in a list with these filters: true, false, or null when only the
 * server can tell (search, "AI handled").
 */
export function matchesFilters(item: ConversationListItem, filters: ConversationFilters): boolean | null {
  if (filters.platform && item.platform !== filters.platform) return false;
  if (filters.accountId && item.social_account_id !== filters.accountId) return false;
  const open = item.status === "open";
  let match: boolean | null;
  switch (filters.view) {
    case "archived":
      match = item.status === "archived";
      break;
    case "unread":
      match = open && item.unread_count > 0;
      break;
    case "needs_reply":
      match = open && item.awaiting_reply;
      break;
    case "leads":
      match = open && (item.lead_score ?? 0) >= LEAD_SCORE;
      break;
    case "ai_handled":
      match = open ? null : false;
      break;
    case "all":
    default:
      match = open;
  }
  if (match && filters.q.trim()) return null;
  return match;
}

/** Newest activity first; ties by id, as the API's (last_message_at, id) cursor. */
export function compareConversations(a: ConversationListItem, b: ConversationListItem): number {
  const at = a.last_message_at ?? "";
  const bt = b.last_message_at ?? "";
  if (at !== bt) return at < bt ? 1 : -1;
  return a.id < b.id ? 1 : a.id > b.id ? -1 : 0;
}

function sameTime(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return a === b;
  return new Date(a).getTime() === new Date(b).getTime();
}

type UpsertOptions = {
  /** Never remove this conversation from a list (the one the user has open). */
  keepId?: string | null;
};

/** Replace, move, insert or remove one conversation in one list's pages. */
export function upsertInPages(
  data: ConversationPages,
  item: ConversationListItem,
  filters: ConversationFilters,
  options: UpsertOptions = {},
): ConversationPages {
  const match = matchesFilters(item, filters);
  let existing: ConversationListItem | undefined;
  for (const page of data.pages) {
    existing = page.items.find((c) => c.id === item.id);
    if (existing) break;
  }

  if (existing) {
    const merged = { ...existing, ...item };
    if (match === false && item.id !== options.keepId) return removeFromPages(data, item.id);
    if (sameTime(existing.last_message_at, item.last_message_at)) {
      return mapItems(data, (c) => (c.id === item.id ? merged : c));
    }
    return insertSorted(removeFromPages(data, item.id), merged);
  }
  if (match !== true) return data;
  return insertSorted(data, item);
}

function mapItems(
  data: ConversationPages,
  fn: (item: ConversationListItem) => ConversationListItem,
): ConversationPages {
  return { ...data, pages: data.pages.map((page) => ({ ...page, items: page.items.map(fn) })) };
}

function removeFromPages(data: ConversationPages, id: string): ConversationPages {
  return {
    ...data,
    pages: data.pages.map((page) =>
      page.items.some((c) => c.id === id) ? { ...page, items: page.items.filter((c) => c.id !== id) } : page,
    ),
  };
}

/** Insert where the sort order puts it, but only inside the loaded range. */
function insertSorted(data: ConversationPages, item: ConversationListItem): ConversationPages {
  const pages = data.pages.map((page) => ({ ...page, items: [...page.items] }));
  for (const page of pages) {
    const index = page.items.findIndex((c) => compareConversations(item, c) < 0);
    if (index !== -1) {
      page.items.splice(index, 0, item);
      return { ...data, pages };
    }
  }
  const last = pages[pages.length - 1];
  if (!last) return data;
  // After every loaded item: it belongs here only when nothing older is left to load.
  if (last.next_cursor) return data;
  last.items.push(item);
  return { ...data, pages };
}

/** Apply a conversation to every loaded list and its detail (conversation.updated). */
export function applyConversation(
  queryClient: QueryClient,
  wid: string,
  item: ConversationListItem,
  options: UpsertOptions = {},
): void {
  const lists = queryClient.getQueriesData<ConversationPages>({ queryKey: keys.conversationLists(wid) });
  for (const [key, data] of lists) {
    if (!data?.pages) continue;
    const filters = key[3] as ConversationFilters | undefined;
    if (!filters) continue;
    queryClient.setQueryData<ConversationPages>(key, upsertInPages(data, item, filters, options));
  }
  const detailKey = keys.conversation(wid, item.id);
  const detail = queryClient.getQueryData<Conversation>(detailKey);
  if (detail) {
    queryClient.setQueryData<Conversation>(detailKey, mergeDetail(detail, item));
    // The list shape has no reply window state; refetch the detail when the window moved.
    if (!sameTime(detail.reply_window_closes_at, item.reply_window_closes_at)) {
      void queryClient.invalidateQueries({ queryKey: detailKey, exact: true });
    }
  }
}

export function mergeDetail(detail: Conversation, item: ConversationListItem): Conversation {
  return { ...detail, ...item, contact: { ...detail.contact, ...item.contact } };
}

/** Local change to a conversation's fields in every list and the detail, without moving it. */
export function patchConversationEverywhere(
  queryClient: QueryClient,
  wid: string,
  id: string,
  patch: Partial<ConversationListItem>,
): void {
  queryClient.setQueriesData<ConversationPages>({ queryKey: keys.conversationLists(wid) }, (data) =>
    data?.pages ? mapItems(data, (c) => (c.id === id ? { ...c, ...patch } : c)) : data,
  );
  queryClient.setQueryData<Conversation>(keys.conversation(wid, id), (detail) => {
    if (!detail) return detail;
    const { contact, ...rest } = patch;
    return { ...detail, ...rest, contact: { ...detail.contact, ...contact } };
  });
}

// ---- messages

export function compareMessagesNewestFirst(a: Message, b: Message): number {
  if (a.occurred_at !== b.occurred_at) {
    return new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime();
  }
  return a.id < b.id ? 1 : a.id > b.id ? -1 : 0;
}

/**
 * message.created / message.updated: replace by id, else replace the optimistic message with
 * the same client_id, else insert into the newest page.
 */
export function upsertMessageInPages(data: MessagePages, message: Message): MessagePages {
  const byId = (m: Message) => m.id === message.id;
  const byClient = (m: Message) => Boolean(message.client_id) && m.client_id === message.client_id;
  for (const test of [byId, byClient]) {
    const pageIndex = data.pages.findIndex((page) => page.items.some(test));
    if (pageIndex !== -1) {
      const pages = data.pages.map((page, i) =>
        i === pageIndex ? { ...page, items: page.items.map((m) => (test(m) ? message : m)) } : page,
      );
      return { ...data, pages };
    }
  }
  const [first, ...rest] = data.pages;
  if (!first) return data;
  const items = [message, ...first.items].sort(compareMessagesNewestFirst);
  return { ...data, pages: [{ ...first, items }, ...rest] };
}

export function applyMessage(queryClient: QueryClient, wid: string, conversationId: string, message: Message): void {
  queryClient.setQueryData<MessagePages>(keys.messages(wid, conversationId), (data) =>
    data?.pages ? upsertMessageInPages(data, message) : data,
  );
}

/** Messages oldest first, from the newest-first pages. */
export function flattenMessages(data: MessagePages | undefined): Message[] {
  if (!data) return [];
  const all: Message[] = [];
  for (let p = data.pages.length - 1; p >= 0; p--) {
    const items = data.pages[p].items;
    for (let i = items.length - 1; i >= 0; i--) all.push(items[i]);
  }
  return all;
}

// ---- scheduled messages

/** scheduled_message.updated and the scheduling mutations. Canceled ones leave the lists. */
export function applyScheduled(queryClient: QueryClient, wid: string, scheduled: ScheduledMessage): void {
  if (scheduled.status === "canceled") {
    removeScheduled(queryClient, wid, scheduled);
    return;
  }
  queryClient.setQueryData<ScheduledPages>(keys.scheduled(wid), (data) => {
    if (!data?.pages) return data;
    const present = data.pages.some((page) => page.items.some((s) => s.id === scheduled.id));
    if (present) {
      return {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.map((s) => (s.id === scheduled.id ? scheduled : s)),
        })),
      };
    }
    const [first, ...rest] = data.pages;
    if (!first) return data;
    const items = [...first.items, scheduled].sort(compareScheduled);
    return { ...data, pages: [{ ...first, items }, ...rest] };
  });
  queryClient.setQueryData<ScheduledMessageList>(keys.scheduledFor(wid, scheduled.conversation_id), (data) => {
    if (!data) return data;
    const present = data.items.some((s) => s.id === scheduled.id);
    const items = present
      ? data.items.map((s) => (s.id === scheduled.id ? scheduled : s))
      : [...data.items, scheduled].sort(compareScheduled);
    return { ...data, items };
  });
}

export function removeScheduled(queryClient: QueryClient, wid: string, scheduled: ScheduledMessage): void {
  queryClient.setQueryData<ScheduledPages>(keys.scheduled(wid), (data) =>
    data?.pages
      ? {
          ...data,
          pages: data.pages.map((page) => ({ ...page, items: page.items.filter((s) => s.id !== scheduled.id) })),
        }
      : data,
  );
  queryClient.setQueryData<ScheduledMessageList>(keys.scheduledFor(wid, scheduled.conversation_id), (data) =>
    data ? { ...data, items: data.items.filter((s) => s.id !== scheduled.id) } : data,
  );
}

/** Pending first by send time, then the rest newest first (the endpoint's order). */
export function compareScheduled(a: ScheduledMessage, b: ScheduledMessage): number {
  const aPending = a.status === "scheduled" || a.status === "sending";
  const bPending = b.status === "scheduled" || b.status === "sending";
  if (aPending !== bPending) return aPending ? -1 : 1;
  const diff = new Date(a.send_at).getTime() - new Date(b.send_at).getTime();
  return aPending ? diff : -diff;
}
