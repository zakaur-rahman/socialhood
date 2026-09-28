import type { components } from "@socialhood/api-client";

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
