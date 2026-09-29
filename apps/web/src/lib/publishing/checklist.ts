/**
 * The composer's checklist (FR-PUB-10, UX-SCR-13). The API computes it on every save; the
 * composer also computes the checks it can answer itself, so an edit shows its effect at once
 * instead of a second later. While the draft on screen is the one the API checked, a failure
 * from either side counts; while edits are unsaved, the local checks stand for their keys and the
 * API's answer stands for the checks only it can make (room in the publishing limit).
 *
 * Items name the field to fix with the API's names (targets.{i}, targets.{i}.caption_override,
 * asset_ids, asset_ids.{i}, caption, first_comment, publish_at), so each failing item links to
 * its control.
 */
import type { ProblemField } from "@/lib/api/errors";
import type { SocialAccount } from "@/lib/api/types";

import {
  assetLabel,
  CAPTION_MAX_CHARS,
  cannotPublishReason,
  countText,
  cropNeeded,
  deriveFormat,
  FIRST_COMMENT_MAX_CHARS,
  formatCount,
  formatDuration,
  handleOf,
  MAX_ASSETS,
  MAX_HASHTAGS,
  MAX_MENTIONS,
  MIN_SCHEDULE_LEAD_MS,
  videoTooLong,
  type AssetInfo,
} from "./rules";
import type { ChecklistItem, ChecklistKey, ScheduledPostDraft } from "./types";

/** The API's order (schemas/publishing.py CHECKLIST_KEYS). */
export const CHECKLIST_KEYS: readonly ChecklistKey[] = [
  "accounts",
  "media",
  "media_files",
  "caption",
  "hashtags",
  "mentions",
  "publishing_limit",
  "publish_at",
];

/** Keys the composer checks itself; the others come only from the API. */
export const LOCAL_KEYS: ReadonlySet<ChecklistKey> = new Set([
  "accounts",
  "media",
  "media_files",
  "caption",
  "hashtags",
  "mentions",
  "publish_at",
]);

export type ChecklistInput = {
  draft: ScheduledPostDraft;
  /** Every account of the workspace, to read each selected one's status and capabilities. */
  accounts: SocialAccount[];
  /** What is known about each asset id in the draft. */
  assets: Record<string, AssetInfo>;
  now: Date;
};

function fail(key: ChecklistKey, message: string, field: string | null): ChecklistItem {
  return { key, ok: false, message, field };
}

function pass(key: ChecklistKey, message: string): ChecklistItem {
  return { key, ok: true, message, field: null };
}

/** One caption with the field it lives in, for the per-caption checks. */
type CaptionSlot = { text: string; field: string; owner: string };

function captionSlots(draft: ScheduledPostDraft, accounts: SocialAccount[]): CaptionSlot[] {
  const slots: CaptionSlot[] = [{ text: draft.caption ?? "", field: "caption", owner: "The caption" }];
  (draft.targets ?? []).forEach((target, index) => {
    if (target.caption_override == null) return;
    const account = accounts.find((item) => item.id === target.social_account_id);
    slots.push({
      text: target.caption_override,
      field: `targets.${index}.caption_override`,
      owner: `The caption for ${handleOf(account)}`,
    });
  });
  return slots;
}

/** The checks the composer can make without the API, in checklist order. */
export function localChecklist({ draft, accounts, assets, now }: ChecklistInput): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const targets = draft.targets ?? [];
  const assetIds = draft.asset_ids ?? [];

  // accounts: at least one, each connected and able to publish
  if (targets.length === 0) {
    items.push(fail("accounts", "Choose at least one account.", "targets"));
  } else {
    const problems: ChecklistItem[] = [];
    targets.forEach((target, index) => {
      const account = accounts.find((item) => item.id === target.social_account_id);
      if (!account) return; // not loaded yet, or gone: the API says which
      const reason = cannotPublishReason(account);
      if (!reason) return;
      const handle = handleOf(account);
      const message =
        account.status === "needs_reconnect"
          ? `${handle} needs reconnecting before you can publish from it.`
          : account.status === "disconnected"
            ? `${handle} is disconnected. Reconnect it or remove it from this post.`
            : account.status === "error"
              ? `${handle} has a connection problem. Reconnect it or remove it from this post.`
              : `${handle} didn't give Social Hood permission to publish. Reconnect to allow it.`;
      problems.push(fail("accounts", message, `targets.${index}`));
    });
    if (problems.length) items.push(...problems);
    else items.push(pass("accounts", targets.length === 1 ? "1 account can publish" : `${targets.length} accounts can publish`));
  }

  // media: the assets make a format
  const known = assetIds.map((id) => assets[id]).filter((asset): asset is AssetInfo => Boolean(asset));
  if (assetIds.length === 0) {
    items.push(fail("media", "Add a photo or video.", "asset_ids"));
  } else if (assetIds.length > MAX_ASSETS) {
    items.push(fail("media", `A carousel can have up to ${MAX_ASSETS} photos and videos.`, "asset_ids"));
  } else if (assetIds.length > 1) {
    items.push(pass("media", `Carousel of ${assetIds.length}`));
  } else {
    items.push(pass("media", deriveFormat(known) === "reel" ? "Reel" : "Single image"));
  }

  // media_files: each asset's aspect ratio and video length (type and size are checked on upload)
  const fileProblems: ChecklistItem[] = [];
  assetIds.forEach((id, index) => {
    const asset = assets[id];
    if (!asset) return;
    const label = assetLabel(asset, index);
    const crop = cropNeeded(asset);
    if (crop) {
      const shape = crop === "tall" ? "taller than 4:5" : "wider than 1.91:1";
      fileProblems.push(fail("media_files", `${label} is ${shape}. Crop it to 1:1, 4:5 or 1.91:1.`, `asset_ids.${index}`));
    } else if (videoTooLong(asset)) {
      fileProblems.push(
        fail(
          "media_files",
          `${label} is ${formatDuration(asset.duration_s ?? 0)} long. Instagram allows videos up to 90 seconds.`,
          `asset_ids.${index}`,
        ),
      );
    }
  });
  if (fileProblems.length) items.push(...fileProblems);
  else if (assetIds.length) items.push(pass("media_files", "Photos and videos fit Instagram's sizes"));

  // caption, hashtags, mentions: every caption, and the first comment's length and hashtags
  const slots = captionSlots(draft, accounts);
  const comment = draft.first_comment ?? "";
  const captionProblems: ChecklistItem[] = [];
  const hashtagProblems: ChecklistItem[] = [];
  const mentionProblems: ChecklistItem[] = [];
  for (const slot of slots) {
    const counts = countText(slot.text);
    if (counts.chars > CAPTION_MAX_CHARS) {
      captionProblems.push(
        fail(
          "caption",
          `${slot.owner} is ${formatCount(counts.chars)} characters. Instagram allows ${formatCount(CAPTION_MAX_CHARS)}.`,
          slot.field,
        ),
      );
    }
    if (counts.hashtags > MAX_HASHTAGS) {
      hashtagProblems.push(
        fail("hashtags", `${slot.owner} has ${counts.hashtags} hashtags. Instagram allows ${MAX_HASHTAGS}.`, slot.field),
      );
    }
    if (counts.mentions > MAX_MENTIONS) {
      mentionProblems.push(
        fail("mentions", `${slot.owner} mentions ${counts.mentions} accounts. Instagram allows ${MAX_MENTIONS}.`, slot.field),
      );
    }
  }
  const commentCounts = countText(comment);
  if (commentCounts.chars > FIRST_COMMENT_MAX_CHARS) {
    captionProblems.push(
      fail(
        "caption",
        `The first comment is ${formatCount(commentCounts.chars)} characters. Instagram allows ${formatCount(FIRST_COMMENT_MAX_CHARS)}.`,
        "first_comment",
      ),
    );
  }
  if (commentCounts.hashtags > MAX_HASHTAGS) {
    hashtagProblems.push(
      fail("hashtags", `The first comment has ${commentCounts.hashtags} hashtags. Instagram allows ${MAX_HASHTAGS}.`, "first_comment"),
    );
  }
  items.push(...(captionProblems.length ? captionProblems : [pass("caption", `Caption within ${formatCount(CAPTION_MAX_CHARS)} characters`)]));
  items.push(...(hashtagProblems.length ? hashtagProblems : [pass("hashtags", `Up to ${MAX_HASHTAGS} hashtags`)]));
  items.push(...(mentionProblems.length ? mentionProblems : [pass("mentions", `Up to ${MAX_MENTIONS} mentions`)]));

  // publish_at: only when the post has a time
  if (draft.publish_at) {
    const at = new Date(draft.publish_at).getTime();
    items.push(
      at - now.getTime() < MIN_SCHEDULE_LEAD_MS
        ? fail("publish_at", "Pick a time at least 5 minutes from now.", "publish_at")
        : pass("publish_at", "Time is at least 5 minutes away"),
    );
  }
  return items;
}

/** A 422's field errors as checklist items, so they show and link like the others. */
export function itemsFromErrors(errors: ProblemField[]): ChecklistItem[] {
  return errors.map((error) => fail(keyOfField(error.field), error.message, error.field));
}

/** The checklist key a field belongs to. */
export function keyOfField(field: string): ChecklistKey {
  if (/^targets\.\d+\.caption_override$/.test(field) || field === "caption" || field === "first_comment") return "caption";
  if (field.startsWith("asset_ids.")) return "media_files";
  if (field.startsWith("asset_ids")) return "media";
  if (field.startsWith("publish_at")) return "publish_at";
  return "accounts";
}

function sameProblem(a: ChecklistItem, b: ChecklistItem): boolean {
  return a.key === b.key && (a.field ?? null) === (b.field ?? null);
}

/**
 * The list to show: failing items first (in checklist order), then one passing line per key.
 * ``inSync`` says the API checked the draft on screen; ``extra`` are failures from the last
 * rejected action (a 422), shown until the next edit.
 */
export function mergeChecklist(
  local: ChecklistItem[],
  server: ChecklistItem[],
  inSync: boolean,
  extra: ChecklistItem[] = [],
): { items: ChecklistItem[]; ready: boolean; failing: number } {
  const failures: ChecklistItem[] = [];
  const add = (item: ChecklistItem) => {
    if (!failures.some((existing) => sameProblem(existing, item))) failures.push(item);
  };
  for (const item of local) if (!item.ok) add(item);
  for (const item of server) {
    if (item.ok) continue;
    if (!LOCAL_KEYS.has(item.key) || inSync) add(item);
  }
  for (const item of extra) add(item);

  const passing: ChecklistItem[] = [];
  for (const key of CHECKLIST_KEYS) {
    if (failures.some((item) => item.key === key)) continue;
    const source = LOCAL_KEYS.has(key) ? local : server;
    const ok = source.find((item) => item.key === key && item.ok);
    if (ok) passing.push(ok);
  }
  const order = (item: ChecklistItem) => CHECKLIST_KEYS.indexOf(item.key);
  failures.sort((a, b) => order(a) - order(b));
  return { items: [...failures, ...passing], ready: failures.length === 0, failing: failures.length };
}
