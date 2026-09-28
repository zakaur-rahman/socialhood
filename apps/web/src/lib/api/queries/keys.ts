import type { InboxView, Platform } from "../types";

/** Filters of one conversation list (FR-INB-01). Part of its query key. */
export type ConversationFilters = {
  view: InboxView;
  platform: Platform | null;
  accountId: string | null;
  q: string;
};

/** Query keys (TR-FE-03): everything workspace-scoped starts with ["w", workspaceId]. */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (wid: string) => ["w", wid, "workspace"] as const,
  overview: (wid: string, range: "7d" | "30d") => ["w", wid, "overview", range] as const,
  accounts: (wid: string) => ["w", wid, "social-accounts"] as const,
  notifications: (wid: string) => ["w", wid, "notifications"] as const,
  // inbox (P3)
  conversationLists: (wid: string) => ["w", wid, "conversations"] as const,
  conversations: (wid: string, filters: ConversationFilters) => ["w", wid, "conversations", filters] as const,
  conversation: (wid: string, id: string) => ["w", wid, "conversation", id] as const,
  messages: (wid: string, conversationId: string) => ["w", wid, "messages", conversationId] as const,
  inboxCounts: (wid: string) => ["w", wid, "inbox-counts"] as const,
  scheduled: (wid: string) => ["w", wid, "scheduled-messages"] as const,
  scheduledFor: (wid: string, conversationId: string) =>
    ["w", wid, "scheduled-messages", "conversation", conversationId] as const,
  templates: (wid: string, accountId: string) => ["w", wid, "templates", accountId] as const,
  suggestion: (wid: string, conversationId: string) => ["w", wid, "suggestion", conversationId] as const,
};
