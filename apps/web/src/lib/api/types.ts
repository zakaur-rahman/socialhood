import type { components, operations } from "@socialhood/api-client";

type Schemas = components["schemas"];

export type Me = Schemas["Me"];
export type WorkspaceSummary = Schemas["WorkspaceSummary"];
export type Workspace = Schemas["WorkspaceOut"];
export type WorkspacePatch = Schemas["WorkspacePatch"];
export type Overview = Schemas["Overview"];
export type ChecklistStep = Schemas["ChecklistStep"];
export type Role = WorkspaceSummary["role"];
export type Plan = WorkspaceSummary["plan"];
export type SocialAccount = Schemas["SocialAccountOut"];
export type SocialAccountPatch = Schemas["SocialAccountPatch"];
export type AccountStatus = SocialAccount["status"];
export type AiMode = SocialAccount["ai_mode"];
export type NotificationItem = Schemas["NotificationOut"];
export type NotificationList = Schemas["NotificationList"];
export type DataDeletionStatus = Schemas["DataDeletionStatus"];

// ---- inbox (§5.10)

export type Platform = SocialAccount["platform"];
export type ConversationListItem = Schemas["ConversationListItem"];
export type ConversationList = Schemas["ConversationList"];
export type Conversation = Schemas["Conversation"];
export type ConversationPatch = Schemas["ConversationPatch"];
export type ContactSummary = Schemas["ContactSummary"];
export type InboxCounts = Schemas["InboxCounts"];
export type ReplyWindow = Schemas["ReplyWindow"];
export type WindowState = ReplyWindow["state"];
export type Signal = NonNullable<ConversationListItem["signal"]>;
export type EscalationReason = NonNullable<ConversationListItem["needs_human_reason"]>;
export type Message = Schemas["Message"];
export type MessageList = Schemas["MessageList"];
export type MessageKind = Message["kind"];
export type MessageSource = Message["source"];
export type MessageStatus = NonNullable<Message["status"]>;
export type Attachment = Schemas["Attachment"];
export type SendMessage = Schemas["SendMessage"];
export type TemplateSend = Schemas["TemplateSend"];
export type ErrorInfo = Schemas["ErrorInfo"];
export type MessageAnalysis = Schemas["MessageAnalysis"];
export type Suggestion = Schemas["Suggestion"];
export type ScheduledMessage = Schemas["ScheduledMessage"];
export type ScheduledMessageList = Schemas["ScheduledMessageList"];
export type ScheduledMessageCreate = Schemas["ScheduledMessageCreate"];
export type ScheduledMessagePatch = Schemas["ScheduledMessagePatch"];
export type UploadSignature = Schemas["UploadSignature"];
export type MediaAsset = Schemas["MediaAssetOut"];
export type ResourceType = MediaAsset["resource_type"];
export type AssetPurpose = Schemas["UploadSignatureRequest"]["purpose"];
export type WhatsAppTemplate = Schemas["WhatsAppTemplate"];
export type EmbeddedSignup = Schemas["EmbeddedSignup"];

// ---- automations (P4: FR-AUT-01…19, UX-SCR-02, 03, 11, 12)

export type Automation = Schemas["Automation"];
export type AutomationList = Schemas["AutomationList"];
export type AutomationCreate = Schemas["AutomationCreate"];
export type AutomationDefinition = Schemas["AutomationDefinition"];
export type AutomationsSummary = Schemas["AutomationsSummary"];
export type AutomationTemplate = Schemas["AutomationTemplate"];
export type AutomationTemplateList = Schemas["AutomationTemplateList"];
export type AutomationRun = Schemas["AutomationRun"];
export type AutomationRunList = Schemas["AutomationRunList"];
export type AutomationStats = Schemas["AutomationStats"];
export type AutomationTest = Schemas["AutomationTest"];
export type AutomationTestResult = Schemas["AutomationTestResult"];
export type OverlapWarning = Schemas["OverlapWarning"];
export type QueueInfo = Schemas["QueueInfo"];
export type LinkButton = Schemas["LinkButtonIn"];
export type PostRef = Schemas["PostRef"];
export type PostSummary = Schemas["PostSummary"];
export type PostList = Schemas["PostList"];
export type AutomationStatus = Automation["status"];
export type DisplayStatus = Automation["display_status"];
export type TriggerName = NonNullable<Automation["trigger"]>;
export type ActionName = NonNullable<Automation["action"]>;
export type MatchMode = Automation["match_mode"];
export type PostScope = Automation["post_scope"];
export type SurgeOrder = Automation["surge_order"];
export type RunResult = AutomationRun["result"];
export type TemplateCategory = AutomationTemplate["category"];
/** The list endpoint's sort (FR-AUT-19). */
export type AutomationSort = NonNullable<
  NonNullable<operations["list_automations"]["parameters"]["query"]>["sort"]
>;

// ---- AI (P5: FR-AI-01…05, FR-SUG-01…06, FR-KB-04)

export type Intent = MessageAnalysis["intent"];
export type Sentiment = MessageAnalysis["sentiment"];
export type Priority = MessageAnalysis["priority"];
export type SuggestionSource = Schemas["SuggestionSource"];
export type ConversationSummary = Schemas["ConversationSummary"];
export type ConversationAi = Schemas["ConversationAi"];
export type AiSettings = Schemas["AiSettings"];
export type AiSettingsUpdate = Schemas["AiSettingsUpdate"];
export type BrandTone = AiSettings["tone"];
export type EmojiPolicy = AiSettings["emoji_policy"];
export type TakeoverMinutes = AiSettings["takeover_minutes"];
export type AnalysisCorrection = Schemas["AnalysisCorrection"];
export type AiDecision = Schemas["AiDecision"];
export type AiDecisionCheck = Schemas["AiDecisionCheck"];

// ---- knowledge (P5: FR-KB-01…06, UX-SCR-06)

export type KnowledgeSource = Schemas["KnowledgeSource"];
export type KnowledgeSourceList = Schemas["KnowledgeSourceList"];
export type KnowledgeSourceCreate = Schemas["KnowledgeSourceCreate"];
export type KnowledgeSourcePatch = Schemas["KnowledgeSourcePatch"];
export type KnowledgeType = KnowledgeSource["type"];
export type KnowledgeStatus = KnowledgeSource["status"];
export type KnowledgeUsage = Schemas["KnowledgeUsage"];
export type KnowledgeTestResult = Schemas["KnowledgeTestResult"];
export type KnowledgeGap = Schemas["KnowledgeGap"];
export type KnowledgeGapList = Schemas["KnowledgeGapList"];

// ---- comments and post analytics (P6: FR-CMT-02…04, FR-ANL-02, UX-SCR-05)

export type PostDetail = Schemas["PostDetail"];
export type PostTopic = Schemas["PostTopic"];
export type CommentStats = Schemas["CommentStats"];
/** A comment on a post ("Comment" alone would shadow the DOM's Comment node type). */
export type PostComment = Schemas["Comment"];
export type CommentList = Schemas["CommentList"];
export type CommentAnalysis = Schemas["CommentAnalysis"];
export type CommentAnalysisStatus = PostComment["analysis_status"];
/** The Comments nav badge: comments waiting for a reply. */
export type CommentCounts = Schemas["CommentCounts"];
/** The post detail's filter chips (UX-SCR-05). */
export type CommentFilter = NonNullable<
  NonNullable<operations["list_post_comments"]["parameters"]["query"]>["filter"]
>;
export type PostPerformance = Schemas["PostPerformance"];
export type PostComparison = Schemas["PostComparison"];
export type PostMetrics = Schemas["PostMetrics"];
export type MetricComparison = Schemas["MetricComparison"];
export type Baseline = Schemas["Baseline"];
/** A post's age after publishing: a snapshot window, or its latest known values. */
export type AgeName = PostPerformance["age"];
export type MetricName = MetricComparison["metric"];

// ---- billing (TR-BIL-04, F-15; P5 reads usage for the AI credit banner, P8 the rest)

export type BillingState = Schemas["BillingState"];
export type UsageMeter = Schemas["UsageMeter"];
export type BillingStatus = BillingState["status"];
export type BillingPrice = Schemas["BillingPrice"];
export type EntitlementValue = Schemas["EntitlementValue"];
export type PlanOffer = Schemas["PlanOffer"];
export type PlanList = Schemas["PlanList"];
export type CheckoutSession = Schemas["CheckoutSession"];
export type PortalSession = Schemas["PortalSession"];

// ---- notification preferences and push (P8: FR-NOT-03, FR-NOT-04, TR-FE-09, C-049)

export type NotificationPreferences = Schemas["NotificationPreferences"];
export type PushPreferences = Schemas["PushPreferences"];
export type PushEvent = keyof PushPreferences;
export type PushConfig = Schemas["PushConfig"];
export type PushDevice = Schemas["PushDevice"];
export type PushSubscriptionCreate = Schemas["PushSubscriptionCreate"];
export type DigestUnsubscribed = Schemas["DigestUnsubscribed"];

// ---- publishing: the Schedule page (P7: FR-PUB-08, 09, 12, 14, UX-SCR-04, UX-SCR-14)

export type ScheduledPostSummary = Schemas["ScheduledPostSummary"];
export type ScheduledPostDetail = Schemas["ScheduledPost"];
export type ScheduledPostList = Schemas["ScheduledPostList"];
export type ScheduledPostTarget = Schemas["ScheduledPostTarget"];
export type ScheduledPostStatus = ScheduledPostSummary["status"];
export type PostFormat = NonNullable<ScheduledPostSummary["format"]>;
/** The List view's tabs (UX-SCR-04). */
export type ScheduledPostView = NonNullable<
  NonNullable<operations["list_scheduled_posts"]["parameters"]["query"]>["view"]
>;
export type BulkScheduledPostRequest = Schemas["BulkScheduledPostRequest"];
export type BulkScheduledPostResult = Schemas["BulkScheduledPostResult"];
export type Calendar = Schemas["Calendar"];
export type CalendarMessage = Schemas["CalendarMessage"];
export type CalendarSlot = Schemas["CalendarSlot"];
export type CalendarAccount = Schemas["CalendarAccount"];
export type PostingSlot = Schemas["PostingSlot"];
export type PostingSlots = Schemas["PostingSlots"];
export type HashtagGroup = Schemas["HashtagGroup"];
export type HashtagGroupCreate = Schemas["HashtagGroupCreate"];
export type HashtagGroupPatch = Schemas["HashtagGroupPatch"];

// ---- Ask Social Hood: the read-only agent (PA: FR-AGT-01…07, agent-architecture.html §11, §12)

export type AgentRun = Schemas["AgentRun"];
export type AgentRunDetail = Schemas["AgentRunDetail"];
export type AgentRunList = Schemas["AgentRunList"];
export type AgentRunCreate = Schemas["AgentRunCreate"];
export type AgentStep = Schemas["AgentStep"];
export type AgentThread = Schemas["AgentThread"];
export type AgentThreadList = Schemas["AgentThreadList"];
export type AgentPolicy = Schemas["AgentPolicy"];
export type AgentPermissions = Schemas["AgentPermissions"];
export type AgentRunStatus = AgentRun["status"];
export type AgentMode = AgentRun["mode"];
export type AgentStepStatus = AgentStep["status"];
export type RiskTier = NonNullable<AgentStep["tier"]>;
export type StepVerification = Schemas["StepVerification"];
/** A record an answer used: `[n]` in the answer is item n of answer_refs (1-based). */
export type AnswerRef = Schemas["AnswerRef"];
export type AnswerRefKind = AnswerRef["kind"];
/** A prepared action (FR-AGT-03): it opens an existing screen pre-filled. */
export type ActionCard = AgentRun["action_cards"][number];
export type ActionKind = ActionCard["kind"];
export type ScheduleMessageAction = Schemas["ScheduleMessageAction"];
export type CommentReplyAction = Schemas["CommentReplyAction"];
export type AutomationDraftAction = Schemas["AutomationDraftAction"];
export type ScheduleMessagePrefill = Schemas["ScheduleMessagePrefill"];
export type CommentReplyPrefill = Schemas["CommentReplyPrefill"];
export type AutomationDraftPrefill = Schemas["AutomationDraftPrefill"];

/**
 * Real-time agent events aren't in the OpenAPI document; their fields are picks of AgentRun and
 * AgentStep (schemas/agent.py AgentRunEvent, AgentStepEvent). They carry ids, statuses and
 * plain-word steps only, never the request or the answer.
 */
export type AgentRunEvent = Pick<AgentRun, "id" | "thread_id" | "status" | "error"> & {
  requested_by_user_id?: string | null;
  /** Steps so far. */
  step_count: number;
};
export type AgentStepProgress = Pick<
  AgentStep,
  "id" | "ordinal" | "kind" | "tool" | "label" | "status" | "summary" | "latency_ms"
>;
export type AgentStepEvent = {
  run_id: string;
  requested_by_user_id?: string | null;
  step: AgentStepProgress;
};

/** The inbox views the list endpoint accepts (FR-INB-01). */
export type InboxView = NonNullable<
  NonNullable<operations["list_conversations"]["parameters"]["query"]>["view"]
>;
