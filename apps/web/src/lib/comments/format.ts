/** Presentation rules for comments and posts (UX-SCR-05, FR-CMT-02…04). Pure, tested directly. */
import { toApiError } from "@/lib/api/errors";
import type { CommentFilter, CommentStats, Intent, PostComment } from "@/lib/api/types";
import { sendFailure } from "@/lib/copy";

/** The filter chips in the order UX-SCR-05 lists them. */
export const COMMENT_FILTERS: { value: CommentFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
  { value: "questions", label: "Questions" },
  { value: "buying", label: "Buying signals" },
  { value: "spam", label: "Spam" },
  { value: "hidden", label: "Hidden" },
];

/** The API's COMMENT_FILTER_INTENTS (schemas/posts.py). */
export const FILTER_INTENTS: Record<"questions" | "buying", readonly Intent[]> = {
  questions: ["pricing", "product_inquiry", "shipping", "order_status", "support"],
  buying: ["purchase", "pricing"],
};

/**
 * Whether a comment belongs in a list with this filter, as the API decides (CommentFilter in
 * schemas/posts.py): every filter leaves out deleted comments; sentiment and intent filters take
 * analysed comments that are not spam; "all" keeps hidden ones.
 */
export function matchesFilter(comment: PostComment, filter: CommentFilter): boolean {
  if (comment.deleted_at) return false;
  const analysis = comment.analysis;
  switch (filter) {
    case "all":
      return true;
    case "hidden":
      return comment.hidden;
    case "spam":
      return Boolean(analysis?.is_spam);
    case "positive":
    case "neutral":
    case "negative":
      return Boolean(analysis && !analysis.is_spam && analysis.sentiment === filter);
    case "questions":
    case "buying":
      return Boolean(analysis && !analysis.is_spam && FILTER_INTENTS[filter].includes(analysis.intent));
    default:
      return false;
  }
}

/** Newest first; ties by id, as the API's cursor. */
export function compareComments(a: PostComment, b: PostComment): number {
  const at = new Date(a.commented_at).getTime();
  const bt = new Date(b.commented_at).getTime();
  if (at !== bt) return bt - at;
  return a.id < b.id ? 1 : a.id > b.id ? -1 : 0;
}

/** The empty state of a filter chip with no comments. */
export function filterEmpty(filter: CommentFilter, analysing: boolean): { title: string; body: string } {
  if (filter === "all") {
    return { title: "No comments yet", body: "New comments on this post appear here as they arrive." };
  }
  const title: Record<Exclude<CommentFilter, "all">, string> = {
    positive: "No positive comments",
    neutral: "No neutral comments",
    negative: "No negative comments",
    questions: "No questions",
    buying: "No buying signals",
    spam: "No spam",
    hidden: "No hidden comments",
  };
  const waiting = analysing && filter !== "hidden";
  return {
    title: title[filter],
    body: waiting
      ? "Nothing matches this filter yet. Comments still being analysed show up here when they're done."
      : "Nothing matches this filter right now.",
  };
}

// ---- posts

const MEDIA_TYPE: Record<string, string> = {
  image: "Photo",
  video: "Video",
  carousel: "Carousel",
  carousel_album: "Carousel",
  reel: "Reel",
  reels: "Reel",
  story: "Story",
};

export function mediaTypeLabel(type: string | null | undefined): string {
  if (!type) return "Post";
  return MEDIA_TYPE[type.toLowerCase()] ?? type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
}

/** Reels are compared with Reels and everything else with feed posts (same_format). */
export function formatPlural(type: string | null | undefined): string {
  const key = type?.toLowerCase();
  return key === "reel" || key === "reels" ? "Reels" : "feed posts";
}

/** FR-CMT-02: the job is still working through the post's comments. */
export function isAnalysing(stats: Pick<CommentStats, "analysed" | "total">): boolean {
  return stats.analysed < stats.total;
}

const count = new Intl.NumberFormat("en-US");

export function formatCount(n: number): string {
  return count.format(n);
}

/** "Analysing 12,400 of 58,000 comments" (FR-CMT-02). */
export function analysingText(stats: Pick<CommentStats, "analysed" | "total">): string {
  return `Analysing ${formatCount(stats.analysed)} of ${formatCount(stats.total)} comments`;
}

export function plural(n: number, one: string, many: string): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** The screen-reader text of a sentiment bar; the bar itself only shows proportions. */
export function sentimentLabel(split: { positive: number; neutral: number; negative: number }): string {
  if (split.positive + split.neutral + split.negative === 0) return "No analysed comments yet";
  return `Sentiment: ${formatCount(split.positive)} positive, ${formatCount(split.neutral)} neutral, ${formatCount(split.negative)} negative`;
}

// ---- replies

/** Instagram's limits: public replies 2,200 characters; private replies 1,000 bytes. */
export const REPLY_MAX_CHARS = 2200;
export const PRIVATE_REPLY_MAX_BYTES = 1000;

const encoder = new TextEncoder();

export function byteLength(text: string): number {
  return encoder.encode(text).length;
}

export function authorHandle(comment: Pick<PostComment, "author_username">): string {
  return comment.author_username ? `@${comment.author_username}` : "this person";
}

export function authorName(comment: Pick<PostComment, "author_username">): string {
  return comment.author_username ? `@${comment.author_username}` : "Instagram user";
}

/** A second private reply (TR-PL-04): Instagram allows one per comment. */
export const SECOND_PRIVATE_REPLY =
  "Instagram allows one private reply per comment, and this comment already has one. Continue in the inbox instead.";

export type CommentAction = "reply" | "dm" | "hide" | "unhide" | "delete";

/**
 * What to show when a comment action fails (§4.7 error codes): the platform errors as the inbox
 * words them, and a clear refusal for a second private reply (409 conflict).
 */
export function commentActionError(error: unknown, action: CommentAction, accountUsername?: string | null): string {
  const apiError = toApiError(error);
  if (action === "dm" && apiError.code === "conflict") return SECOND_PRIVATE_REPLY;
  return sendFailure(
    {
      code: apiError.code,
      message: apiError.detail ?? apiError.errors[0]?.message ?? null,
      requestId: apiError.requestId,
    },
    { platform: "instagram", handle: accountUsername },
  ).message;
}
