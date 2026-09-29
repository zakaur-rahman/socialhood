import type {
  AgeName,
  AutomationSort,
  AutomationStatus,
  CommentFilter,
  InboxView,
  Platform,
  RunResult,
  TriggerName,
} from "../types";

/** Filters of one conversation list (FR-INB-01). Part of its query key. */
export type ConversationFilters = {
  view: InboxView;
  platform: Platform | null;
  accountId: string | null;
  q: string;
};

/** Server-side filters of the automations list (FR-AUT-19). Part of its query key. */
export type AutomationFilters = {
  accountId: string | null;
  status: AutomationStatus | null;
  trigger: TriggerName | null;
  q: string;
  sort: AutomationSort;
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
  // automations (P4)
  automationLists: (wid: string) => ["w", wid, "automations"] as const,
  automations: (wid: string, filters: AutomationFilters) => ["w", wid, "automations", "list", filters] as const,
  automationsSummary: (wid: string) => ["w", wid, "automations", "summary"] as const,
  automationTemplates: (wid: string) => ["w", wid, "automation-templates"] as const,
  automation: (wid: string, id: string) => ["w", wid, "automation", id] as const,
  automationRuns: (wid: string, id: string, result: RunResult | null) =>
    ["w", wid, "automation", id, "runs", result] as const,
  automationStats: (wid: string, id: string, days: 7 | 30) => ["w", wid, "automation", id, "stats", days] as const,
  // posts: the automation post picker (P4) and the Comments grid (P6) share these lists
  postLists: (wid: string) => ["w", wid, "posts"] as const,
  posts: (wid: string, accountId: string | null, q: string) => ["w", wid, "posts", accountId, q] as const,
  // comments and post analytics (P6)
  post: (wid: string, postId: string) => ["w", wid, "post", postId] as const,
  postCommentLists: (wid: string, postId: string) => ["w", wid, "post-comments", postId] as const,
  postComments: (wid: string, postId: string, filter: CommentFilter) =>
    ["w", wid, "post-comments", postId, filter] as const,
  postPerformance: (wid: string, postId: string, age: AgeName | null) =>
    ["w", wid, "analytics", "performance", postId, age] as const,
  postComparison: (wid: string, postId: string, age: AgeName | null) =>
    ["w", wid, "analytics", "compare", postId, age] as const,
  // AI and knowledge (P5)
  aiSettings: (wid: string) => ["w", wid, "ai-settings"] as const,
  aiDecision: (wid: string, messageId: string) => ["w", wid, "ai-decision", messageId] as const,
  knowledgeSources: (wid: string) => ["w", wid, "knowledge-sources"] as const,
  knowledgeGaps: (wid: string) => ["w", wid, "knowledge-gaps"] as const,
  billing: (wid: string) => ["w", wid, "billing"] as const,
};
