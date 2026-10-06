/**
 * Labels, colours and small rules for the Schedule page (UX-SCR-04, UX-SCR-14, FR-PUB-08, 09,
 * 12, 14). Colours are token utilities only.
 */
import { ApiError } from "@/lib/api/errors";
import type {
  BulkScheduledPostResult,
  PostingSlot,
  ScheduledPostStatus,
  ScheduledPostSummary,
  ScheduledPostView,
  SocialAccount,
} from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import type { Tone } from "@/lib/inbox/format";
import { type Identity, identityAt } from "@/lib/ui/identity";

import { formatMinutes, TOO_SOON_MESSAGE, WEEKDAYS_SHORT } from "./dates";

type StatusMeta = {
  label: string;
  tone: Tone | "success";
  /** The card's left border (UX-SCR-04: brand scheduled, success published, danger failed, muted draft). */
  border: string;
  /** The List tab, and the status filter group, it belongs to. */
  group: ScheduledPostView;
};

export const POST_STATUS: Record<ScheduledPostStatus, StatusMeta> = {
  draft: { label: "Draft", tone: "neutral", border: "border-l-fg-disabled", group: "drafts" },
  scheduled: { label: "Scheduled", tone: "brand", border: "border-l-brand", group: "scheduled" },
  publishing: { label: "Publishing", tone: "brand", border: "border-l-brand motion-safe:animate-pulse", group: "scheduled" },
  published: { label: "Published", tone: "success", border: "border-l-success", group: "published" },
  partially_published: { label: "Partly published", tone: "warning", border: "border-l-success", group: "published" },
  failed: { label: "Failed", tone: "danger", border: "border-l-danger", group: "failed" },
  canceled: { label: "Canceled", tone: "neutral", border: "border-l-danger", group: "failed" },
};

/** The post status chip's fill and text: the one tone map (lib/ui/tone), under its old name. */
export { TONE_CLASS as CHIP_CLASS } from "@/lib/ui/tone";

/** The List view's tabs and the status filter, in order (UX-SCR-04). */
export const STATUS_GROUPS: { value: ScheduledPostView; label: string }[] = [
  { value: "scheduled", label: "Scheduled" },
  { value: "drafts", label: "Drafts" },
  { value: "published", label: "Published" },
  { value: "failed", label: "Failed" },
];

/** FR-PUB-08: only drafts and scheduled posts move; publishing and published ones never do. */
export function canMove(post: Pick<ScheduledPostSummary, "status">): boolean {
  return post.status === "scheduled" || post.status === "draft";
}

/** Why a card can't be dragged, said when someone tries. */
export function lockedMessage(post: Pick<ScheduledPostSummary, "status">): string {
  switch (post.status) {
    case "publishing":
      return "Publishing started, so this post can't be moved.";
    case "published":
    case "partially_published":
      return "Published posts can't be moved.";
    default:
      return "Open this post to edit it and try again.";
  }
}

/** The caption's first line, or what stands in for it. */
export function captionLine(caption: string | null | undefined): string {
  const line = (caption ?? "").split(/\r?\n/).find((part) => part.trim())?.trim();
  return line || "No caption yet";
}

export function postFormatLabel(post: Pick<ScheduledPostSummary, "format" | "asset_count">): string {
  switch (post.format) {
    case "reel":
      return "Reel";
    case "carousel":
      return `Carousel · ${post.asset_count} items`;
    case "image":
      return "Image";
    default:
      return post.asset_count > 0 ? `${post.asset_count} files` : "No media yet";
  }
}

/**
 * Each account keeps one identity on the page (UX-SCR-04): its ring and dot, and its avatar's
 * gradient when it has no picture, all from the identity palette (lib/ui/identity, D-13), never a
 * status or platform colour. Accounts take the identities in order, so the first three differ.
 */
export type AccountColor = Identity;

export function accountColors(accounts: Pick<SocialAccount, "id">[]): Map<string, AccountColor> {
  return new Map(accounts.map((account, i) => [account.id, identityAt(i)]));
}

/** An account the page doesn't know (disconnected): a neutral ring, no identity. */
export const UNKNOWN_ACCOUNT_COLOR: AccountColor = { gradient: "", ring: "ring-line-strong", dot: "bg-line-strong" };

/** "Mon, Wed, Fri 18:00 · Sat 10:00": weekly posting times grouped by time. */
export function summarizeSlots(slots: PostingSlot[]): string {
  if (slots.length === 0) return "None yet";
  const byTime = new Map<string, number[]>();
  for (const slot of slots) {
    const time = slot.local_time.slice(0, 5);
    const days = byTime.get(time) ?? [];
    if (!days.includes(slot.weekday)) days.push(slot.weekday);
    byTime.set(time, days);
  }
  const groups = new Map<string, string[]>();
  for (const [time, days] of [...byTime.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const sorted = [...days].sort((a, b) => a - b);
    const label = sorted.length === 7 ? "Every day" : sorted.map((d) => WEEKDAYS_SHORT[d]).join(", ");
    groups.set(label, [...(groups.get(label) ?? []), time]);
  }
  return [...groups.entries()].map(([days, times]) => `${days} ${times.join(", ")}`).join(" · ");
}

/** "18:00:00" or "18:00" to minutes since midnight. */
export function slotMinutes(localTime: string): number {
  const [h, m] = localTime.split(":").map(Number);
  return h * 60 + m;
}

export function slotTime(minutes: number): string {
  return formatMinutes(minutes);
}

// ---- hashtag groups (FR-PUB-12)

export const MAX_HASHTAGS = 30;
export const HASHTAG_GROUP_NAME_MAX = 60;

/**
 * Hashtags as typed: separated by spaces, commas or new lines, with or without "#", any case;
 * kept without "#", lowercase and once each, as the API stores them.
 */
export function parseHashtags(text: string): { tags: string[]; invalid: string[] } {
  const tags: string[] = [];
  const invalid: string[] = [];
  for (const raw of text.split(/[\s,]+/)) {
    const tag = raw.replace(/^#+/, "").toLowerCase();
    if (!tag) continue;
    // Letters (with their combining marks, as in Hindi), digits and underscores.
    if (!/^[\p{L}\p{M}\p{N}_]+$/u.test(tag) || tag.length > 100) {
      if (!invalid.includes(raw)) invalid.push(raw);
      continue;
    }
    if (!tags.includes(tag)) tags.push(tag);
  }
  return { tags, invalid };
}

// ---- errors

/** The message for a refused move or schedule: the field's own words when the API gave them. */
export function moveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const field = error.errors.find((e) => e.field === "publish_at");
    if (field) return field.message;
    if (error.code === "conflict") return error.detail ?? "Publishing started, so this post can't be moved.";
  }
  return errorMessage(error);
}

function fieldIn(field: string, names: string[]): boolean {
  return names.some((name) => field === name || field.startsWith(`${name}.`));
}

/**
 * A draft dropped on the calendar is checked like Schedule (F-13): a failure on anything but the
 * time (or, for Add to queue, the accounts' posting times) means the post itself needs work, so
 * the composer opens with its checklist.
 */
export function needsComposer(error: unknown, timing: string[] = ["publish_at"]): boolean {
  return (
    error instanceof ApiError &&
    error.status === 422 &&
    (error.errors.length === 0 || error.errors.some((e) => !fieldIn(e.field, timing)))
  );
}

/** The first field's message, else the error's copy (section 4.7). */
export function firstProblem(error: unknown): string {
  if (error instanceof ApiError && error.errors[0]) return error.errors[0].message;
  return errorMessage(error);
}

export { TOO_SOON_MESSAGE };

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** FR-PUB-14: what a bulk action did, and what it skipped and why. */
export function bulkResultMessage(
  action: "shift" | "unschedule" | "delete",
  result: BulkScheduledPostResult,
): { message: string; skipped: string | null } {
  const done = action === "delete" ? result.deleted_ids.length : result.updated.length;
  const verb = action === "shift" ? "moved" : action === "unschedule" ? "moved to drafts" : "deleted";
  const message = `${plural(done, "post")} ${verb}.`;
  if (result.skipped.length === 0) return { message, skipped: null };
  const reasons = [...new Set(result.skipped.map((s) => s.message))].join(" ");
  return { message, skipped: `${plural(result.skipped.length, "post")} skipped. ${reasons}`.trim() };
}
