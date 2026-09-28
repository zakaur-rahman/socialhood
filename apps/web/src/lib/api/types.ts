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
export type WhatsAppTemplate = Schemas["WhatsAppTemplate"];
export type EmbeddedSignup = Schemas["EmbeddedSignup"];

/** The inbox views the list endpoint accepts (FR-INB-01). */
export type InboxView = NonNullable<
  NonNullable<operations["list_conversations"]["parameters"]["query"]>["view"]
>;
