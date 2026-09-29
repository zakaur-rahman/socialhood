/**
 * Publishing types (P7: §5.10 ScheduledPost, FR-PUB-01…14), from the generated contract. Kept
 * beside the composer's rules rather than in lib/api/types.ts so the composer and the Schedule
 * page can grow their own sets without editing one shared list.
 */
import type { components } from "@socialhood/api-client";

type Schemas = components["schemas"];

export type ScheduledPost = Schemas["ScheduledPost"];
export type ScheduledPostSummary = Schemas["ScheduledPostSummary"];
export type ScheduledPostDraft = Schemas["ScheduledPostDraft"];
export type ScheduledPostTarget = Schemas["ScheduledPostTarget"];
export type ScheduledPostStatus = ScheduledPost["status"];
export type TargetStatus = ScheduledPostTarget["status"];
export type TargetIn = Schemas["TargetIn"];
export type PostAsset = Schemas["PostAsset"];
export type PostFormat = NonNullable<ScheduledPost["format"]>;
export type ChecklistItem = Schemas["ChecklistItem"];
export type ChecklistKey = ChecklistItem["key"];
export type LinkedAutomation = Schemas["LinkedAutomation"];
export type FirstCommentResult = Schemas["FirstCommentResult"];
export type HashtagGroup = Schemas["HashtagGroup"];
export type HashtagGroupList = Schemas["HashtagGroupList"];
export type MediaAssetList = Schemas["MediaAssetList"];
export type PostingSlots = Schemas["PostingSlots"];
export type CaptionRequest = Schemas["CaptionRequest"];
export type CaptionSuggestion = Schemas["CaptionSuggestion"];
export type HashtagSuggestionRequest = Schemas["HashtagSuggestionRequest"];
export type HashtagSuggestion = Schemas["HashtagSuggestion"];
