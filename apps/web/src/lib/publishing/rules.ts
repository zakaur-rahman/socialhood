/**
 * The composer's rules (FR-PUB-01, FR-PUB-10, FR-PUB-12, TR-MED-02): Instagram's limits, the
 * caption counters, the post format the media make, which files can be uploaded and which images
 * need a crop. The API applies the same limits (models/publishing.py); these give instant answers
 * while the user types, and the API's checklist decides once the draft is saved.
 */
import type { MediaAsset, SocialAccount } from "@/lib/api/types";
import type { Tone } from "@/lib/ui/tone";

import type { PostAsset, PostFormat, ScheduledPostStatus } from "./types";

export const CAPTION_MAX_CHARS = 2200;
/** A Facebook Page post's text (Meta's figure, unverified until a real Page publishes, C-131). */
export const FACEBOOK_CAPTION_MAX_CHARS = 63206;
export const FIRST_COMMENT_MAX_CHARS = 2200;
export const MAX_HASHTAGS = 30;
export const MAX_MENTIONS = 20;
export const CAROUSEL_MIN_ASSETS = 2;
export const MAX_ASSETS = 10;
export const SUGGESTED_HASHTAGS_MAX = 20;
/** Schedule, reschedule and Update schedule refuse a time closer than this (F-13). */
export const MIN_SCHEDULE_LEAD_MS = 60_000; // owner 2026-11-08: 1 minute, was 5

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
export const UNSUPPORTED_MEDIA = "Instagram can't publish this file. Use JPEG or PNG images, or MP4 or MOV video.";

/** The video size cap when the API doesn't say (its ``post_video_max_mb`` setting, C-134). */
export const DEFAULT_VIDEO_MAX_MB = 100;

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
export function checkPostFile(file: Pick<File, "name" | "type" | "size">, videoMaxMb = DEFAULT_VIDEO_MAX_MB): string | null {
  const kind = postFileKind(file);
  if (!kind) return UNSUPPORTED_MEDIA;
  const rule = POST_FILE_RULES[kind];
  const maxBytes = kind === "video" ? videoMaxMb * MB : rule.maxBytes;
  if (file.size > maxBytes) return `${rule.label} can be up to ${maxBytes / MB} MB on Instagram.`;
  return null;
}

/** Instagram's feed ratios (TR-MED-02): 4:5 portrait to 1.91:1 landscape. */
export const MIN_RATIO = 4 / 5;
export const MAX_RATIO = 1.91;
const RATIO_TOLERANCE = 0.01;
export const MAX_VIDEO_SECONDS = 90;
/** An Instagram Reel (a single video for Instagram alone) runs 3 seconds to 15 minutes (Meta, C-134). */
export const IG_REEL_MIN_SECONDS = 3;
export const IG_REEL_MAX_SECONDS = 900;

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

/** Why a single Instagram video can't be a Reel, or null: shorter than 3 s or longer than 15 minutes. */
export function igReelProblem(asset: Pick<AssetInfo, "resource_type" | "duration_s">): string | null {
  if (asset.resource_type !== "video" || asset.duration_s == null) return null;
  if (asset.duration_s > IG_REEL_MAX_SECONDS) return `Reels can be up to ${IG_REEL_MAX_SECONDS / 60} minutes.`;
  if (asset.duration_s < IG_REEL_MIN_SECONDS) return `Reels must be at least ${IG_REEL_MIN_SECONDS} seconds.`;
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

export const FORMAT_LABEL: Record<PostFormat, string> = { image: "Image", carousel: "Carousel", reel: "Reel", story: "Story", text: "Text" };

// ---- Stories (GR-39; Meta's limits, unverified until a real account publishes one, C-114)

/** A Story video runs 3 to 60 seconds. */
export const STORY_VIDEO_MIN_SECONDS = 3;
export const STORY_VIDEO_MAX_SECONDS = 60;
/** A Facebook Reel is one video of 3 to 90 seconds (Meta's limits, unverified, C-131). */
export const FACEBOOK_REEL_MIN_SECONDS = 3;
export const FACEBOOK_REEL_MAX_SECONDS = 90;

/** A Story lives for 24 hours. */
export const STORY_LIFETIME_HOURS = 24;
const STORY_RATIO = 9 / 16;
const STORY_RATIO_TOLERANCE = 0.05;

/** A Story file that is not 9:16 still publishes, but Instagram crops it or adds bars. */
export function storyShapeOff(asset: Pick<AssetInfo, "width" | "height">): boolean {
  const ratio = ratioOf(asset);
  return ratio !== null && Math.abs(ratio - STORY_RATIO) > STORY_RATIO * STORY_RATIO_TOLERANCE;
}

/** Why a video can't be a Story, or null: shorter than 3 s or longer than 60 s. */
export function storyVideoProblem(asset: Pick<AssetInfo, "resource_type" | "duration_s">): string | null {
  if (asset.resource_type !== "video" || asset.duration_s == null) return null;
  if (asset.duration_s > STORY_VIDEO_MAX_SECONDS) return `Story videos can be up to ${STORY_VIDEO_MAX_SECONDS} seconds.`;
  if (asset.duration_s < STORY_VIDEO_MIN_SECONDS) return `Story videos must be at least ${STORY_VIDEO_MIN_SECONDS} seconds.`;
  return null;
}

/** Why a video can't be a Facebook Reel, or null: shorter than 3 s (the longest is the usual 90 s). */
export function reelVideoProblem(asset: Pick<AssetInfo, "resource_type" | "duration_s">): string | null {
  if (asset.resource_type !== "video" || asset.duration_s == null) return null;
  if (asset.duration_s < FACEBOOK_REEL_MIN_SECONDS) return `Reel videos must be at least ${FACEBOOK_REEL_MIN_SECONDS} seconds.`;
  return null;
}

export const REEL_ONE_VIDEO = "A Facebook Reel is one video.";
export const REEL_NEEDS_VIDEO = "Add a video for the Reel.";
export const REEL_NEEDS_PAGE = "Choose a Facebook Page for a Reel. Instagram already publishes a single video as a Reel.";

/** "Photo 2" or "Video 3": items are named by their place in the post. */
export function assetLabel(asset: Pick<AssetInfo, "resource_type">, index: number): string {
  return `${asset.resource_type === "video" ? "Video" : "Photo"} ${index + 1}`;
}

// ---- accounts

/**
 * The accounts that can publish: Instagram accounts and Facebook Pages (WhatsApp can't, C-043),
 * and YouTube channels while the workspace has the youtube switch (C-195).
 */
export function publishingAccounts(accounts: SocialAccount[], features: readonly string[] = []): SocialAccount[] {
  const youtube = features.includes("youtube");
  return accounts.filter(
    (account) => account.platform === "instagram" || account.platform === "facebook" || (youtube && account.platform === "youtube"),
  );
}

/** GR-30: the platforms the post goes to; before the accounts load, Instagram's rules apply. */
export function postPlatforms(accounts: Pick<SocialAccount, "platform">[]): { instagram: boolean; facebook: boolean; youtube: boolean } {
  const facebook = accounts.some((account) => account.platform === "facebook");
  const instagram = accounts.some((account) => account.platform === "instagram") || accounts.length === 0;
  const youtube = accounts.some((account) => account.platform === "youtube");
  return { instagram, facebook, youtube };
}

/**
 * The caption length for a post to these platforms (the API's ``caption_limit``): Instagram's
 * 2,200, a Facebook Page's 63,206, YouTube's 5,000 (bytes, see ``YOUTUBE_DESCRIPTION_MAX_BYTES``);
 * a cross-posted post is held to the strictest. No accounts yet: Instagram's.
 */
export function captionLimit(platforms: readonly string[]): number {
  if (platforms.length === 0) return CAPTION_MAX_CHARS;
  return Math.min(
    ...platforms.map((platform) =>
      platform === "facebook" ? FACEBOOK_CAPTION_MAX_CHARS : platform === "youtube" ? YOUTUBE_DESCRIPTION_MAX_BYTES : CAPTION_MAX_CHARS,
    ),
  );
}

// ---- YouTube (C-195 Phase 2; YouTube Data API videos resource, checked 2026-11-14)

export const YOUTUBE_TITLE_MAX_CHARS = 100;
/** The description is the caption; YouTube counts its 5,000 in UTF-8 bytes. */
export const YOUTUBE_DESCRIPTION_MAX_BYTES = 5000;
/** Tags count toward 500 characters in total. */
export const YOUTUBE_TAGS_MAX_CHARS = 500;
/** A Short is vertical (or square) and up to 3 minutes. */
export const SHORT_MAX_SECONDS = 180;
export const YOUTUBE_KIDS_HELP_URL = "https://support.google.com/youtube/answer/9528076";
export const YOUTUBE_AI_HELP_URL = "https://support.google.com/youtube/answer/14328491";
/** The formats YouTube takes, offered by the YouTube dropzone. */
export const YOUTUBE_VIDEO_EXTENSIONS = ["mp4", "mov", "m4v", "webm", "avi", "mkv", "wmv", "flv", "3gp", "mpg", "mpeg"];

/** The options every YouTube target carries (the API's YouTubeOptions); the two questions start unanswered. */
export type YouTubeOptions = {
  title: string;
  privacy: "public" | "unlisted" | "private";
  /** null until answered: YouTube requires the answer, and there is no default (D4). */
  made_for_kids: boolean | null;
  synthetic_media: boolean | null;
  category_id: string | null;
  tags: string[];
  notify_subscribers: boolean;
  format: "video" | "short";
};

export const DEFAULT_YOUTUBE_OPTIONS: YouTubeOptions = {
  title: "",
  privacy: "public",
  made_for_kids: null,
  synthetic_media: null,
  category_id: null,
  tags: [],
  notify_subscribers: true,
  format: "video",
};

/** YouTube's video categories that work in most regions (videoCategories.list, assignable ones). */
export const YOUTUBE_CATEGORIES: { id: string; label: string }[] = [
  { id: "1", label: "Film & Animation" },
  { id: "2", label: "Autos & Vehicles" },
  { id: "10", label: "Music" },
  { id: "15", label: "Pets & Animals" },
  { id: "17", label: "Sports" },
  { id: "19", label: "Travel & Events" },
  { id: "20", label: "Gaming" },
  { id: "22", label: "People & Blogs" },
  { id: "23", label: "Comedy" },
  { id: "24", label: "Entertainment" },
  { id: "25", label: "News & Politics" },
  { id: "26", label: "Howto & Style" },
  { id: "27", label: "Education" },
  { id: "28", label: "Science & Technology" },
  { id: "29", label: "Nonprofits & Activism" },
];

export function byteCount(text: string): number {
  return new TextEncoder().encode(text).length;
}

/** Tags as YouTube counts them: a tag with a space is quoted, and tags are joined by commas. */
export function tagsLength(tags: readonly string[]): number {
  return tags.reduce((sum, tag, index) => sum + charCount(tag) + (/\s/.test(tag) ? 2 : 0) + (index > 0 ? 1 : 0), 0);
}

/**
 * Whether the API will take these options (its YouTubeOptions): a title of 1 to 100 characters
 * without < or >, both questions answered, tags within 500 characters. Until then the draft saves
 * the target without options, and the checklist says what's missing.
 */
export function youtubeOptionsReady(options: YouTubeOptions | null | undefined): options is YouTubeOptions & { made_for_kids: boolean; synthetic_media: boolean } {
  if (!options) return false;
  const title = options.title.trim();
  return (
    title.length > 0 &&
    charCount(title) <= YOUTUBE_TITLE_MAX_CHARS &&
    !/[<>]/.test(title) &&
    options.made_for_kids != null &&
    options.synthetic_media != null &&
    tagsLength(options.tags) <= YOUTUBE_TAGS_MAX_CHARS
  );
}

/**
 * Where a post's video goes (the plan's Approach): ``direct`` when every chosen account is a
 * YouTube channel (the browser uploads straight to YouTube), ``media`` when YouTube shares the post
 * with Instagram or Facebook (the media tray, then our scheduler), null without a channel.
 */
export function youtubeRoute(accounts: Pick<SocialAccount, "platform">[]): "direct" | "media" | null {
  if (!accounts.some((account) => account.platform === "youtube")) return null;
  return accounts.every((account) => account.platform === "youtube") ? "direct" : "media";
}

/** A file the YouTube dropzone can send: a video YouTube takes. Any size (YouTube's 256 GB, D2). */
export function checkYouTubeFile(file: Pick<File, "name" | "type" | "size">): string | null {
  if (file.size === 0) return "This file is empty.";
  if (!YOUTUBE_VIDEO_EXTENSIONS.includes(extensionOf(file.name)) && !file.type.startsWith("video/")) {
    return "YouTube takes video files, such as MP4, MOV or WebM.";
  }
  return null;
}

/** Why a video can't be a Short, or null: vertical (or square) and up to 3 minutes. */
export function shortProblem(asset: Pick<AssetInfo, "width" | "height" | "duration_s">): string | null {
  if (asset.width && asset.height && asset.width > asset.height) return "A Short must be vertical or square. This video is wider than it is tall.";
  if (asset.duration_s != null && asset.duration_s > SHORT_MAX_SECONDS) {
    return `A Short can be up to 3 minutes. This video is ${formatDuration(asset.duration_s)} long.`;
  }
  return null;
}

/** No media and some text, for Facebook Pages alone: a text post (GR-30). */
export function pagesOnlyText(accounts: Pick<SocialAccount, "platform">[], caption: string): boolean {
  return accounts.length > 0 && accounts.every((account) => account.platform === "facebook") && caption.trim().length > 0;
}

export const FACEBOOK_NO_MIX = "A Facebook post can have several photos or one video, not both.";

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

export const STATUS_TONE: Record<ScheduledPostStatus, Tone> = {
  draft: "neutral",
  scheduled: "brand",
  publishing: "brand",
  published: "success",
  partially_published: "warning",
  failed: "danger",
  canceled: "neutral",
};

/** Draft and scheduled posts can be edited; once publishing starts the composer is read-only. */
export function isEditable(status: ScheduledPostStatus): boolean {
  return status === "draft" || status === "scheduled";
}

// ---- Instagram extras (FR-PUB-07, C-134; Meta's IG User Media references, checked 2026-10-25)

/** Collaborators: the publishing reference says up to 3, the collaborators reference 5. We allow 3. */
export const COLLABORATORS_MAX = 3;
/** Meta states no limit on user tags; 20 per photo is Instagram's own limit in the app (unverified for the API). */
export const USER_TAGS_MAX_PER_IMAGE = 20;
export const INSTAGRAM_USERNAME_MAX_CHARS = 30;
export const AUDIO_NAME_MAX_CHARS = 100;
export const COVER_MAX_BYTES = 8 * MB;

const USERNAME = /^[a-z0-9._]{1,30}$/;

/** A username as stored: without "@", lowercase; null when it isn't a valid Instagram username. */
export function normalizeUsername(raw: string): string | null {
  const name = raw.trim().replace(/^@+/, "").trim().toLowerCase();
  return USERNAME.test(name) ? name : null;
}

const PAGE_ID = /^\d{5,20}$/;
const PAGE_LINKS = [/[?&]id=(\d{5,20})(?:&|$)/, /facebook\.com\/(?:pages\/[^/?#]+\/)?(?:[^/?#]*-)?(\d{5,20})(?:[/?#]|$)/i];

export const LOCATION_HELP =
  "Paste the numeric id of a Facebook Page that has a location, or the link to it (facebook.com/profile.php?id=…).";

/** The Facebook Page id in a pasted id or Page link, else null. A vanity link has no id in it. */
export function parseLocation(raw: string): string | null {
  const text = raw.trim();
  if (PAGE_ID.test(text)) return text;
  if (!/facebook\.com/i.test(text)) return null;
  for (const pattern of PAGE_LINKS) {
    const match = pattern.exec(text);
    if (match) return match[1];
  }
  return null;
}
