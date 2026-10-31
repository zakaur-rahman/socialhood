import type { ContactFilters } from "@/lib/contacts/filters";
import type {
  ActivityKind,
  AgeName,
  AgentRunStatus,
  AutomationSort,
  AutomationStatus,
  CommentFilter,
  InboxView,
  Platform,
  PostSort,
  RunResult,
  ScheduledPostView,
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

/** The Products page's list filters (GR-31). Part of its query key. */
export type ProductFilters = { q: string; active: boolean | null };

export type ActivityFilters = {
  failuresOnly: boolean;
  kind: ActivityKind | null;
  automationId: string | null;
  accountId: string | null;
};

/** Filters of the audit log (GR-19). Part of its query key. */
export type AuditFilters = { member: string | null; action: string | null; since: string | null; page: number };

/** Query keys (TR-FE-03): everything workspace-scoped starts with ["w", workspaceId]. */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (wid: string) => ["w", wid, "workspace"] as const,
  /** `range` is "7d", "30d" or "custom:{from}:{to}" (Home's range control). */
  overview: (wid: string, range: string) => ["w", wid, "overview", range] as const,
  accounts: (wid: string) => ["w", wid, "social-accounts"] as const,
  notifications: (wid: string) => ["w", wid, "notifications"] as const,
  apiKeys: (wid: string) => ["w", wid, "api-keys"] as const,
  mcpUpload: (wid: string, id: string) => ["w", wid, "mcp-uploads", id] as const,
  aiConnectionsSettings: (wid: string) => ["w", wid, "ai-connections", "settings"] as const,
  aiConnections: (wid: string) => ["w", wid, "ai-connections", "list"] as const,
  aiConnectionActivity: (wid: string, id: string) => ["w", wid, "ai-connections", "activity", id] as const,
  connectRequest: (id: string) => ["connect-request", id] as const,
  webhookEvents: (wid: string) => ["w", wid, "webhook-events"] as const,
  webhookEndpoints: (wid: string) => ["w", wid, "webhook-endpoints"] as const,
  googleSheets: (wid: string) => ["w", wid, "google-sheets"] as const,
  products: (wid: string) => ["w", wid, "products"] as const,
  productList: (wid: string, filters: ProductFilters) => ["w", wid, "products", "list", filters] as const,
  shopify: (wid: string) => ["w", wid, "shopify"] as const,
  orders: (wid: string) => ["w", wid, "orders"] as const, // GR-32
  orderList: (wid: string, status: string | null) => ["w", wid, "orders", "list", status] as const,
  payments: (wid: string) => ["w", wid, "payments"] as const,
  waCatalogue: (wid: string) => ["w", wid, "wa-catalogue"] as const, // GR-33
  webhookDeliveries: (wid: string, endpointId: string) => ["w", wid, "webhook-deliveries", endpointId] as const,
  /** Activity (GR-05): `activity(wid)` is the prefix every filter's list shares. */
  activityLists: (wid: string) => ["w", wid, "activity"] as const,
  activity: (wid: string, filters: ActivityFilters) => ["w", wid, "activity", filters] as const,
  // contacts (GR-17): `contactLists(wid)` is the prefix of every list, count, record and timeline
  contactLists: (wid: string) => ["w", wid, "contacts"] as const,
  contacts: (wid: string, filters: ContactFilters) => ["w", wid, "contacts", "list", filters] as const,
  contactCount: (wid: string, filters: ContactFilters) => ["w", wid, "contacts", "count", filters] as const,
  contact: (wid: string, id: string) => ["w", wid, "contacts", "one", id] as const,
  contactTimeline: (wid: string, id: string) => ["w", wid, "contacts", "timeline", id] as const,
  tags: (wid: string) => ["w", wid, "tags"] as const,
  // leads (GR-18): moving a lead also refreshes `contactLists(wid)`, which holds its cards
  leadSummary: (wid: string) => ["w", wid, "leads", "summary"] as const,
  leadSettings: (wid: string) => ["w", wid, "leads", "settings"] as const,
  // the weekly report (GR-34); `week` is the Monday, or "latest"
  weeklyReport: (wid: string, week: string, account: string) => ["w", wid, "reports", "weekly", week, account] as const,
  contactFields: (wid: string) => ["w", wid, "contact-fields"] as const,
  contactSegments: (wid: string) => ["w", wid, "contact-segments"] as const,
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
  automationFlow: (wid: string, id: string) => ["w", wid, "automation", id, "flow"] as const, // GR-13
  flowTags: (wid: string) => ["w", wid, "flow-tags"] as const,
  flowFields: (wid: string) => ["w", wid, "flow-fields"] as const,
  entryLinks: (wid: string) => ["w", wid, "entry-links"] as const, // GR-08
  savedReplies: (wid: string) => ["w", wid, "saved-replies"] as const, // GR-21
  permissions: (wid: string) => ["w", wid, "permissions"] as const, // GR-19
  members: (wid: string) => ["w", wid, "members"] as const,
  assignment: (wid: string) => ["w", wid, "assignment"] as const, // GR-20
  // sequences (GR-24): `sequences(wid)` is the prefix of every list, detail and enrolment page
  sequences: (wid: string) => ["w", wid, "sequences"] as const,
  sequenceList: (wid: string) => ["w", wid, "sequences", "list"] as const,
  sequence: (wid: string, id: string) => ["w", wid, "sequences", "one", id] as const,
  sequencePeople: (wid: string, id: string, status: string | null, page: number) =>
    ["w", wid, "sequences", "one", id, "people", status, page] as const,
  sequenceAnalytics: (wid: string, id: string) => ["w", wid, "sequences", "one", id, "analytics"] as const,
  sequencePreview: (wid: string, body: unknown) => ["w", wid, "sequences", "preview", body] as const,
  contactSequences: (wid: string, contactId: string) => ["w", wid, "sequences", "contact", contactId] as const,
  invitations: (wid: string) => ["w", wid, "invitations"] as const,
  auditEvents: (wid: string, filters: AuditFilters) => ["w", wid, "audit-events", filters] as const,
  broadcastAvailability: (wid: string) => ["w", wid, "broadcasts", "availability"] as const, // GR-23
  broadcastLists: (wid: string) => ["w", wid, "broadcasts", "list"] as const,
  broadcast: (wid: string, id: string) => ["w", wid, "broadcasts", "one", id] as const,
  broadcastRecipients: (wid: string, id: string, status: string | null, page: number) =>
    ["w", wid, "broadcasts", "one", id, "recipients", status, page] as const,
  broadcastPreview: (wid: string, draft: unknown) => ["w", wid, "broadcasts", "preview", draft] as const,
  businessHours: (wid: string) => ["w", wid, "business-hours"] as const, // GR-22
  widget: (wid: string) => ["w", wid, "widget"] as const, // GR-28
  // stories and mentions (GR-06, GR-07)
  stories: (wid: string, accountId: string | null) => ["w", wid, "stories", accountId] as const,
  iceBreakers: (wid: string, accountId: string) => ["w", wid, "ice-breakers", accountId] as const,
  storyMentions: (wid: string, accountId: string | null) => ["w", wid, "story-mentions", accountId] as const,
  automationRuns: (wid: string, id: string, result: RunResult | null) =>
    ["w", wid, "automation", id, "runs", result] as const,
  automationStats: (wid: string, id: string, days: 7 | 30) => ["w", wid, "automation", id, "stats", days] as const,
  automationFunnel: (wid: string, id: string, days: 7 | 30 | 90) =>
    ["w", wid, "automation", id, "funnel", days] as const,
  // posts: the automation post picker (P4) and the Comments grid (P6) share these lists
  postLists: (wid: string) => ["w", wid, "posts"] as const,
  posts: (wid: string, accountId: string | null, q: string, sort: PostSort = "recent") =>
    ["w", wid, "posts", accountId, q, sort] as const,
  // comments and post analytics (P6)
  commentCounts: (wid: string) => ["w", wid, "comment-counts"] as const,
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
  // GR-35: under the sources' key, so refreshing the sources refreshes the open site's pages too
  sitePages: (wid: string, siteId: string) => ["w", wid, "knowledge-sources", siteId, "pages"] as const,
  billing: (wid: string) => ["w", wid, "billing"] as const,
  billingPayments: (wid: string) => ["w", wid, "billing", "payments"] as const,
  // P8: public plans, and the member's own notification settings and push
  billingPlans: ["billing-plans"] as const,
  notificationPreferences: (wid: string) => ["w", wid, "notification-preferences"] as const,
  pushConfig: ["push-config"] as const,
  // publishing: the Schedule page (P7)
  calendars: (wid: string) => ["w", wid, "calendar"] as const,
  calendar: (wid: string, from: string, to: string) => ["w", wid, "calendar", from, to] as const,
  scheduledPostLists: (wid: string) => ["w", wid, "scheduled-posts"] as const,
  scheduledPosts: (wid: string, view: ScheduledPostView, accountIds: readonly string[] | null) =>
    ["w", wid, "scheduled-posts", view, accountIds] as const,
  postingSlots: (wid: string, accountId: string) => ["w", wid, "posting-slots", accountId] as const,
  bestTimes: (wid: string, accountId: string) => ["w", wid, "best-times", accountId] as const,
  hashtagGroups: (wid: string) => ["w", wid, "hashtag-groups"] as const,
  // Ask Amplychat (PA): run lists (a thread's runs, the admin history) share one prefix
  agentRunLists: (wid: string) => ["w", wid, "agent", "runs"] as const,
  agentThreadRuns: (wid: string, threadId: string) => ["w", wid, "agent", "runs", "thread", threadId] as const,
  agentRunHistory: (wid: string) => ["w", wid, "agent", "runs", "history"] as const,
  /** The history narrowed by status and text (Settings → Agent, C-066); under the same prefix. */
  agentRunHistoryFiltered: (wid: string, statuses: readonly AgentRunStatus[], q: string) =>
    ["w", wid, "agent", "runs", "history", { statuses, q }] as const,
  agentRun: (wid: string, runId: string) => ["w", wid, "agent", "run", runId] as const,
  agentThreads: (wid: string) => ["w", wid, "agent", "threads"] as const,
  agentPolicy: (wid: string) => ["w", wid, "agent", "policy"] as const,
  /** GR-36: the agent's proposed writes; every list shares one prefix. */
  agentApprovalLists: (wid: string) => ["w", wid, "agent", "approvals"] as const,
  agentApprovals: (wid: string, status: string, runId: string | null) =>
    ["w", wid, "agent", "approvals", { status, runId }] as const,
};
