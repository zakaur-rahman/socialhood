import type { components, operations } from "@socialhood/api-client";

type Schemas = components["schemas"];

export type Me = Schemas["Me"];
export type WorkspaceSummary = Schemas["WorkspaceSummary"];
export type Workspace = Schemas["WorkspaceOut"];
export type WorkspacePatch = Schemas["WorkspacePatch"];
export type Overview = Schemas["Overview"];
export type OverviewPeriod = Schemas["OverviewPeriod"];
export type OverviewPost = Schemas["OverviewPost"];
export type OverviewGap = Schemas["OverviewGap"];
export type OverviewEngagement = Schemas["OverviewEngagement"];
export type PriorityConversation = Schemas["PriorityConversation"];
export type SentimentSplit = Schemas["SentimentSplit"];
export type AccountAttention = Schemas["AccountAttention"];
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
export type ConversationEntry = Schemas["ConversationEntry"];
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
// GR-15: the per-step funnel and a Split's results
export type AutomationFunnel = Schemas["AutomationFunnel"];
export type FunnelStep = Schemas["FunnelStep"];
export type SplitResult = Schemas["SplitResult"];
export type SplitBranch = Schemas["SplitBranch"];
export type AutomationTest = Schemas["AutomationTest"];
export type AutomationTestResult = Schemas["AutomationTestResult"];
export type OverlapWarning = Schemas["OverlapWarning"];
export type QueueInfo = Schemas["QueueInfo"];
export type LinkButton = Schemas["LinkButtonIn"];

// ---- flows (GR-03, the editor GR-13)

export type Flow = Schemas["Flow"];
export type FlowDefinition = Schemas["FlowDefinition"];
export type FlowStep = FlowDefinition["steps"][number];
export type FlowButton = Schemas["FlowButton"];
export type FlowCondition = Schemas["BranchRule"]["when"];
export type FlowAction = Schemas["ActionStep"]["action"];
export type FlowPreviewStep = Schemas["FlowPreviewStep"];
export type FlowFieldDefinition = Schemas["FieldDefinition"];
export type FlowTag = Schemas["Tag"];
export type PostRef = Schemas["PostRef"];
export type PostSummary = Schemas["PostSummary"];
export type PostList = Schemas["PostList"];
// GR-06, GR-07: live stories for the story picker, and the Mentions list.
export type Story = Schemas["Story"];
export type StoryList = Schemas["StoryList"];
// conversation starters (GR-11)
export type IceBreaker = Schemas["IceBreaker"];
export type IceBreakerList = Schemas["IceBreakerList"];
export type IceBreakersUpdate = Schemas["IceBreakersUpdate"];
export type StoryMention = Schemas["StoryMention"];
export type StoryMentionList = Schemas["StoryMentionList"];
// GR-21: saved replies (snippets typed after / in the composer).
export type SavedReply = Schemas["SavedReply"];
export type SavedReplyList = Schemas["SavedReplyList"];
export type SavedReplyCreate = Schemas["SavedReplyCreate"];
export type SavedReplyUpdate = Schemas["SavedReplyUpdate"];
export type SavedReplyFilled = Schemas["SavedReplyFilled"];
// GR-22: business hours and the away message.
export type BusinessHours = Schemas["BusinessHours"];
export type BusinessHoursUpdate = Schemas["BusinessHoursUpdate"];
export type BusinessHoursOverview = Schemas["BusinessHoursOverview"];
export type AccountBusinessHours = Schemas["AccountBusinessHours"];
export type DaySchedule = Schemas["DaySchedule"];
export type TimeRange = Schemas["TimeRange"];
export type AutoModeName = BusinessHours["auto_mode"];
// GR-08: entry links (ig.me links with QR codes).
export type EntryLink = Schemas["EntryLink"];
export type EntryLinkList = Schemas["EntryLinkList"];
export type EntryLinkCreate = Schemas["EntryLinkCreate"];
export type EntryLinkUpdate = Schemas["EntryLinkUpdate"];
export type QrFormat = "svg" | "png";
export type AutomationStatus = Automation["status"];
export type DisplayStatus = Automation["display_status"];
export type TriggerName = NonNullable<Automation["trigger"]>;
export type ActionName = NonNullable<Automation["action"]>;
export type MatchMode = Automation["match_mode"];
export type PostScope = Automation["post_scope"];
/** GR-10: where a comment trigger listens: posts, the account's Lives, or both. */
export type CommentSurface = Automation["comment_surface"];
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
/** The composer's AI Polish (C-063). */
export type PolishRequest = Schemas["PolishRequest"];
export type PolishResult = Schemas["PolishResult"];

// ---- knowledge (P5: FR-KB-01…06, UX-SCR-06)

export type KnowledgeSource = Schemas["KnowledgeSource"];
export type KnowledgeSourceList = Schemas["KnowledgeSourceList"];
export type KnowledgeSourceCreate = Schemas["KnowledgeSourceCreate"];
export type KnowledgeSourcePatch = Schemas["KnowledgeSourcePatch"];
export type KnowledgeType = KnowledgeSource["type"];
/** What can be added: a page of a website is made by a crawl (GR-35). */
export type KnowledgeCreateType = KnowledgeSourceCreate["type"];
export type SiteCrawlInfo = Schemas["SiteCrawlInfo"];
export type SitePage = Schemas["SitePage"];
export type SitePageList = Schemas["SitePageList"];
export type SitePageStatus = SitePage["status"];
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
/** The Comments grid's sort (D-11): newest first, or the posts with the most comments to reply to. */
export type PostSort = NonNullable<NonNullable<operations["list_posts"]["parameters"]["query"]>["sort"]>;
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
/** Payment history (C-066): the workspace's Dodo payments, newest first. */
export type Payment = Schemas["PaymentOut"];
export type PaymentList = Schemas["PaymentList"];

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
 * A visual answer (GR-38): built by the API's tools from service numbers and listed in the run's
 * `visuals`, in step order. A closed set: narrow on `kind`. Customer text in them (a caption, a
 * topic) is text: render it as text.
 */
export type Visual = AgentRun["visuals"][number];
export type VisualKind = Visual["kind"];
export type MetricComparisonVisual = Schemas["MetricComparisonVisual"];
export type RankedPostsVisual = Schemas["RankedPostsVisual"];
export type SentimentSummaryVisual = Schemas["SentimentSummaryVisual"];
export type MetricDelta = Schemas["MetricDelta"];
export type RankedPostRow = Schemas["RankedPostRow"];
export type VisualPeriod = Schemas["VisualPeriod"];
export type VisualTopic = Schemas["VisualTopic"];

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

// ---- outbound webhooks (GR-04)

export type WebhookEventType = Schemas["WebhookEventType"];
export type WebhookEventName = WebhookEventType["type"];
export type WebhookEndpoint = Schemas["WebhookEndpoint"];
export type WebhookEndpointWithSecret = Schemas["WebhookEndpointWithSecret"];
export type WebhookEndpointList = Schemas["WebhookEndpointList"];
export type WebhookEndpointCreate = Schemas["WebhookEndpointCreate"];
export type WebhookEndpointPatch = Schemas["WebhookEndpointPatch"];
export type WebhookDelivery = Schemas["WebhookDelivery"];
export type WebhookDeliveryList = Schemas["WebhookDeliveryList"];

// ---- Google Sheets sync (GR-27)

export type GoogleSheetsStatus = Schemas["GoogleSheetsStatus"];
export type GoogleSheetsConnectStart = Schemas["GoogleConnectStart"];
export type GoogleSheetColumn = Schemas["SheetColumnOut"];
export type GoogleSheetFieldOption = Schemas["SheetFieldOption"];
export type GoogleSheetRow = Schemas["SheetRowOut"];
export type GoogleSheetInfo = Schemas["SheetOut"];
export type GoogleSheetMappingPut = Schemas["SheetMappingPut"];
export type GoogleSheetTestResult = Schemas["SheetTestResult"];

// Activity (GR-05)
export type ActivityItem = Schemas["ActivityItem"];
export type ActivityList = Schemas["ActivityList"];
export type ActivityAction = Schemas["ActivityAction"];
export type ActivityRetry = Schemas["ActivityRetry"];
export type ActivityKind = ActivityItem["kind"];
export type ActivityOutcome = ActivityItem["outcome"];

// Contacts (GR-02, GR-17)
export type ContactListItem = Schemas["ContactListItem"];
export type ContactList = Schemas["ContactList"];
export type ContactRecord = Schemas["ContactRecord"];
export type ContactPatch = Schemas["ContactPatch"];
export type ContactCount = Schemas["ContactCount"];
export type ContactFilterSpec = Schemas["ContactFilterSpec"];
export type ContactFilterOut = Schemas["ContactFilterOut"];
export type ContactConsent = Schemas["Consent"];
export type ConsentChannel = ContactConsent["channel"];
export type ConsentCreate = Schemas["ConsentCreate"];
export type ContactTag = Schemas["Tag"];
export type TagList = Schemas["TagList"];
export type TagRef = Schemas["TagRef"];
export type TagCreate = Schemas["TagCreate"];
export type FieldDefinition = Schemas["FieldDefinition"];
export type FieldDefinitionList = Schemas["FieldDefinitionList"];
export type FieldType = FieldDefinition["type"];
export type BulkTagsUpdate = Schemas["BulkTagsUpdate"];
export type BulkTagsResult = Schemas["BulkTagsResult"];
export type ContactSegment = Schemas["Segment"];
export type ContactSegmentList = Schemas["SegmentList"];
export type ContactSegmentCreate = Schemas["SegmentCreate"];
export type ContactSegmentPatch = Schemas["SegmentPatch"];
export type TimelineItem = Schemas["TimelineItem"];
export type TimelineList = Schemas["TimelineList"];
export type TimelineKind = TimelineItem["kind"];

// Leads (GR-18)
export type LeadStage = ContactListItem["lead_stage"];
export type LeadStageUpdate = Schemas["LeadStageUpdate"];
export type LeadSummary = Schemas["LeadSummary"];
export type LeadStageCount = Schemas["LeadStageCount"];
export type LeadWeek = Schemas["LeadWeek"];
export type LeadSettings = Schemas["LeadSettings"];
export type LeadSettingsPatch = Schemas["LeadSettingsPatch"];

// Weekly report (GR-34)
export type WeeklyReport = Schemas["WeeklyReport"];
export type ReportMetric = Schemas["ReportMetric"];
export type ReportMetricKey = ReportMetric["key"];
export type ReportAccountMetric = Schemas["ReportAccountMetric"];
export type ReportPoint = Schemas["ReportPoint"];
export type ReportIntent = Schemas["ReportIntent"];
export type ReportQuestion = Schemas["ReportQuestion"];
export type ReportPost = Schemas["ReportPost"];

// ---- team (GR-19)

export type WorkspacePermissions = Schemas["WorkspacePermissions"];
export type TeamMember = Schemas["Member"];
export type TeamMemberList = Schemas["MemberList"];
export type TeamSeats = Schemas["Seats"];
export type TeamInvitation = Schemas["Invitation"];
export type TeamInvitationList = Schemas["InvitationList"];
export type TeamInvitationCreate = Schemas["InvitationCreate"];
export type TeamInvitableRole = TeamInvitationCreate["role"];
export type OwnershipTransfer = Schemas["OwnershipTransfer"];
export type AuditEvent = Schemas["AuditEvent"];
export type AuditEventList = Schemas["AuditEventList"];
