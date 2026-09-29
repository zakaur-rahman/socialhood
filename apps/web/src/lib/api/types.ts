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

// ---- billing state (TR-BIL-04; P5 reads usage for the AI credit banner)

export type BillingState = Schemas["BillingState"];
export type UsageMeter = Schemas["UsageMeter"];

/** The inbox views the list endpoint accepts (FR-INB-01). */
export type InboxView = NonNullable<
  NonNullable<operations["list_conversations"]["parameters"]["query"]>["view"]
>;
