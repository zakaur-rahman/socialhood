/**
 * The composer's rules (FR-PUB-01, FR-PUB-10, FR-PUB-12, TR-MED-02): Instagram's limits, the
 * caption counters, the post format the media make, which files can be uploaded and which images
 * need a crop. The API applies the same limits (models/publishing.py); these give instant answers
 * while the user types, and the API's checklist decides once the draft is saved.
 */
import type { MediaAsset, SocialAccount } from "@/lib/api/types";

import type { PostAsset, PostFormat, ScheduledPostStatus } from "./types";

export const CAPTION_MAX_CHARS = 2200;
export const FIRST_COMMENT_MAX_CHARS = 2200;
export const MAX_HASHTAGS = 30;
export const MAX_MENTIONS = 20;
export const CAROUSEL_MIN_ASSETS = 2;
export const MAX_ASSETS = 10;
export const SUGGESTED_HASHTAGS_MAX = 20;
/** Schedule, reschedule and Update schedule refuse a time closer than this (F-13). */
export const MIN_SCHEDULE_LEAD_MS = 5 * 60_000;

// ---- counting (FR-PUB-10)

const number = new Intl.NumberFormat("en-US");

export function formatCount(value: number): string {
  return number.format(value);
}

/** Characters as Instagram and the API count them: code points, so an emoji is one. */
export function charCount(text: string): number {
  return [...text].length;
}

// A hashtag starts at the beginning or after a character that can't be part of a word, so
// "abc#def" and "&#123;" are not hashtags; Instagram allows letters (any script), digits and _.
// Built from strings: lookbehind and \p{…} are ES2018 syntax, above the tsconfig target, and
// every browser the app supports has them. The zero-width (non-)joiner is allowed too, like the
// API's rule, so Hindi hashtags such as #नमस्ते count whole.
const HASHTAG = new RegExp("(?<![\\p{L}\\p{M}\\p{N}_&#])#([\\p{L}\\p{M}\\p{N}_\\u200C\\u200D]+)", "gu");
// Instagram usernames: letters, digits, periods and underscores; an email address is not a mention.
const MENTION = new RegExp("(?<![\\p{L}\\p{M}\\p{N}_.@])@([A-Za-z0-9._]+)", "gu");

/** The hashtags in the text, lowercase and without "#", in order (repeats included). */
export function hashtagsIn(text: string): string[] {
  return Array.from(text.matchAll(HASHTAG), (match) => match[1].toLowerCase());
}

export function mentionsIn(text: string): string[] {
  return Array.from(text.matchAll(MENTION), (match) => match[1].replace(/\.+$/, "")).filter(Boolean);
}

export type TextCounts = { chars: number; hashtags: number; mentions: number };

export function countText(text: string): TextCounts {
  return { chars: charCount(text), hashtags: hashtagsIn(text).length, mentions: mentionsIn(text).length };
}

/** A typed hashtag as stored: without "#", lowercase. */
export function normaliseHashtag(tag: string): string {
  return tag.trim().replace(/^#+/, "").toLowerCase();
}

/**
 * Add hashtags to a caption or first comment (FR-PUB-12, Suggest hashtags). Tags already in the
 * text are skipped. They join a last line that is only hashtags, or go on their own line after a
 * blank line, as Instagram captions usually end.
 */
export function appendHashtags(text: string, tags: string[]): string {
  const present = new Set(hashtagsIn(text));
  const added: string[] = [];
  for (const raw of tags) {
    const tag = normaliseHashtag(raw);
    if (!tag || present.has(tag)) continue;
    present.add(tag);
    added.push(`#${tag}`);
  }
  if (added.length === 0) return text;
  const block = added.join(" ");
  const trimmed = text.replace(/\s+$/, "");
  if (!trimmed) return block;
  const lastLine = trimmed.slice(trimmed.lastIndexOf("\n") + 1);
  const onlyHashtags = lastLine.trim() !== "" && lastLine.replace(HASHTAG, "").trim() === "";
  return onlyHashtags ? `${trimmed} ${block}` : `${trimmed}\n\n${block}`;
}

// ---- media (TR-MED-02)

const MB = 1024 * 1024;

type FileRule = { label: string; extensions: string[]; maxBytes: number };

export const POST_FILE_RULES: Record<"image" | "video", FileRule> = {
  image: { label: "Photos", extensions: ["jpg", "jpeg", "png", "webp", "heic"], maxBytes: 8 * MB },
  video: { label: "Videos", extensions: ["mp4", "mov"], maxBytes: 100 * MB },
};

/** §4.7 unsupported_media. */
export const UNSUPPORTED_MEDIA =
  "Instagram can't publish this file. Use JPEG or PNG images, or MP4 video up to 90 seconds.";

export const POST_FILE_ACCEPT = [...POST_FILE_RULES.image.extensions, ...POST_FILE_RULES.video.extensions]
  .map((extension) => `.${extension}`)
  .join(",");

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

/** "image" or "video" for a file Instagram can publish, else null. */
export function postFileKind(file: Pick<File, "name" | "type">): "image" | "video" | null {
  const extension = extensionOf(file.name);
  if (POST_FILE_RULES.image.extensions.includes(extension)) return "image";
  if (POST_FILE_RULES.video.extensions.includes(extension)) return "video";
  return null;
}

/** Why a picked file can't be used, before it is uploaded; null when it can. */
export function checkPostFile(file: Pick<File, "name" | "type" | "size">): string | null {
  const kind = postFileKind(file);
  if (!kind) return UNSUPPORTED_MEDIA;
  const rule = POST_FILE_RULES[kind];
  if (file.size > rule.maxBytes) return `${rule.label} can be up to ${rule.maxBytes / MB} MB on Instagram.`;
  return null;
}

/** Instagram's feed ratios (TR-MED-02): 4:5 portrait to 1.91:1 landscape. */
export const MIN_RATIO = 4 / 5;
export const MAX_RATIO = 1.91;
const RATIO_TOLERANCE = 0.01;
export const MAX_VIDEO_SECONDS = 90;

/** What the composer knows about one image or video of the post. */
export type AssetInfo = {
  id: string;
  resource_type: "image" | "video";
  url: string;
  thumbnail_url: string | null;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  name: string | null;
};

export function fromPostAsset(asset: PostAsset): AssetInfo {
  return {
    id: asset.id,
    resource_type: asset.resource_type,
    url: asset.url,
    thumbnail_url: asset.thumbnail_url ?? null,
    width: asset.width ?? null,
    height: asset.height ?? null,
    duration_s: asset.duration_s ?? null,
    name: null,
  };
}

/** An upload or a library item; documents ("raw") are not post media. */
export function fromMediaAsset(asset: MediaAsset): AssetInfo | null {
  if (asset.resource_type !== "image" && asset.resource_type !== "video") return null;
  return {
    id: asset.id,
    resource_type: asset.resource_type,
    url: asset.secure_url ?? "",
    thumbnail_url: asset.resource_type === "image" ? (asset.secure_url ?? null) : null,
    width: asset.width ?? null,
    height: asset.height ?? null,
    duration_s: asset.duration_s ?? null,
    name: asset.original_filename ?? null,
  };
}

export function ratioOf(asset: Pick<AssetInfo, "width" | "height">): number | null {
  if (!asset.width || !asset.height) return null;
  return asset.width / asset.height;
}

/** "tall" or "wide" when an image is outside 4:5 to 1.91:1 and needs a crop (TR-MED-02). */
export function cropNeeded(asset: Pick<AssetInfo, "resource_type" | "width" | "height">): "tall" | "wide" | null {
  if (asset.resource_type !== "image") return null;
  const ratio = ratioOf(asset);
  if (ratio === null) return null;
  if (ratio < MIN_RATIO - RATIO_TOLERANCE) return "tall";
  if (ratio > MAX_RATIO + RATIO_TOLERANCE) return "wide";
  return null;
}

export function videoTooLong(asset: Pick<AssetInfo, "resource_type" | "duration_s">): boolean {
  return asset.resource_type === "video" && (asset.duration_s ?? 0) > MAX_VIDEO_SECONDS;
}

/** "1:05" */
export function formatDuration(seconds: number): string {
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** The format the media make (FR-PUB-01): one image, one video (a Reel), or a carousel of 2 to 10. */
export function deriveFormat(assets: Pick<AssetInfo, "resource_type">[]): PostFormat | null {
  if (assets.length === 0) return null;
  if (assets.length === 1) return assets[0].resource_type === "video" ? "reel" : "image";
  return "carousel";
}

export const FORMAT_LABEL: Record<PostFormat, string> = { image: "Image", carousel: "Carousel", reel: "Reel" };

/** "Photo 2" or "Video 3": items are named by their place in the post. */
export function assetLabel(asset: Pick<AssetInfo, "resource_type">, index: number): string {
  return `${asset.resource_type === "video" ? "Video" : "Photo"} ${index + 1}`;
}

// ---- accounts

/** Instagram accounts are the ones that can publish (WhatsApp can't, C-043). */
export function publishingAccounts(accounts: SocialAccount[]): SocialAccount[] {
  return accounts.filter((account) => account.platform === "instagram");
}

export function handleOf(account: Pick<SocialAccount, "username" | "display_name"> | null | undefined): string {
  if (!account) return "This account";
  return account.username ? `@${account.username}` : (account.display_name ?? "This account");
}

/** Why the account can't publish now (UX-SCR-13 disables its chip with the reason), or null. */
export function cannotPublishReason(account: SocialAccount): string | null {
  if (account.status === "disconnected") return "Disconnected";
  if (account.status === "needs_reconnect") return "Needs reconnecting";
  if (account.status === "error") return "Connection error";
  if (!account.capabilities.includes("publish")) return "Reconnect to allow publishing";
  return null;
}

// ---- status (FR-PUB-06)

export const STATUS_LABEL: Record<ScheduledPostStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  publishing: "Publishing",
  published: "Published",
  partially_published: "Partly published",
  failed: "Failed",
  canceled: "Cancelled",
};

export const STATUS_TONE: Record<ScheduledPostStatus, string> = {
  draft: "bg-raised text-fg-secondary",
  scheduled: "bg-brand-soft text-brand-fg",
  publishing: "bg-brand-soft text-brand-fg",
  published: "bg-success/15 text-success",
  partially_published: "bg-warning/15 text-warning",
  failed: "bg-danger/15 text-danger-fg",
  canceled: "bg-raised text-fg-secondary",
};

/** Draft and scheduled posts can be edited; once publishing starts the composer is read-only. */
export function isEditable(status: ScheduledPostStatus): boolean {
  return status === "draft" || status === "scheduled";
}
