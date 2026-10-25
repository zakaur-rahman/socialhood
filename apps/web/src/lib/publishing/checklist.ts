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
  AUDIO_NAME_MAX_CHARS,
  CAPTION_MAX_CHARS,
  COLLABORATORS_MAX,
  igReelProblem,
  LOCATION_HELP,
  normalizeUsername,
  parseLocation,
  USER_TAGS_MAX_PER_IMAGE,
  captionLimit,
  cannotPublishReason,
  countText,
  cropNeeded,
  deriveFormat,
  FACEBOOK_CAPTION_MAX_CHARS,
  FIRST_COMMENT_MAX_CHARS,
  formatCount,
  formatDuration,
  handleOf,
  MAX_ASSETS,
  MAX_HASHTAGS,
  MAX_MENTIONS,
  MIN_SCHEDULE_LEAD_MS,
  FACEBOOK_NO_MIX,
  postPlatforms,
  REEL_NEEDS_PAGE,
  REEL_NEEDS_VIDEO,
  REEL_ONE_VIDEO,
  reelVideoProblem,
  storyShapeOff,
  storyVideoProblem,
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
  "extras",
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
  "extras",
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
type CaptionSlot = { text: string; field: string; owner: string; limit: number };

function captionSlots(draft: ScheduledPostDraft, accounts: SocialAccount[]): CaptionSlot[] {
  // Each caption is held to the limit of the accounts it goes to (C-131): an account's own caption
  // to its platform's; the shared one to the strictest of the accounts without their own.
  const platformOf = (id: string) => accounts.find((item) => item.id === id)?.platform ?? "instagram";
  const targets = draft.targets ?? [];
  const shared = targets.filter((target) => target.caption_override == null).map((target) => platformOf(target.social_account_id));
  const slots: CaptionSlot[] = [
    { text: draft.caption ?? "", field: "caption", owner: "The caption", limit: shared.length ? captionLimit(shared) : FACEBOOK_CAPTION_MAX_CHARS },
  ];
  targets.forEach((target, index) => {
    if (target.caption_override == null) return;
    const account = accounts.find((item) => item.id === target.social_account_id);
    slots.push({
      text: target.caption_override,
      field: `targets.${index}.caption_override`,
      owner: `The caption for ${handleOf(account)}`,
      limit: captionLimit([platformOf(target.social_account_id)]),
    });
  });
  return slots;
}

/** The checks the composer can make without the API, in checklist order. */
export function localChecklist({ draft, accounts, assets, now }: ChecklistInput): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const targets = draft.targets ?? [];
  const assetIds = draft.asset_ids ?? [];
  const story = draft.kind === "story";
  const reel = draft.kind === "reel";
  const selected = targets
    .map((target) => accounts.find((item) => item.id === target.social_account_id))
    .filter((account): account is SocialAccount => Boolean(account));
  const { instagram: ig, facebook: fb } = postPlatforms(selected);
  // Text for Facebook Pages alone, with no media, is a text post (GR-30).
  const textPost = fb && !ig && !story && !reel && assetIds.length === 0 && Boolean((draft.caption ?? "").trim());
  const limitName = ig ? "Instagram" : "Social Hood";

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
    // A Reel is for Facebook Pages: Instagram already publishes a single video as a Reel (C-131).
    if (reel && !fb) problems.push(fail("accounts", REEL_NEEDS_PAGE, "targets"));
    if (problems.length) items.push(...problems);
    else items.push(pass("accounts", targets.length === 1 ? "1 account can publish" : `${targets.length} accounts can publish`));
  }

  // media: the assets make a format
  const known = assetIds.map((id) => assets[id]).filter((asset): asset is AssetInfo => Boolean(asset));
  if (assetIds.length === 0) {
    items.push(
      textPost
        ? pass("media", "Text post")
        : fail(
            "media",
            reel ? REEL_NEEDS_VIDEO : fb && !ig ? "Add a photo or video, or write the post's text." : "Add a photo or video.",
            "asset_ids",
          ),
    );
  } else if (reel) {
    const oneVideo = assetIds.length === 1 && (known.length === 0 || known[0].resource_type === "video");
    items.push(oneVideo ? pass("media", "Reel") : fail("media", REEL_ONE_VIDEO, "asset_ids"));
  } else if (fb && !story && assetIds.length > 1 && known.some((asset) => asset.resource_type === "video")) {
    items.push(fail("media", FACEBOOK_NO_MIX, "asset_ids"));
  } else if (story) {
    items.push(assetIds.length === 1 ? pass("media", "Story") : fail("media", "A Story is one photo or one video.", "asset_ids"));
  } else if (assetIds.length > MAX_ASSETS) {
    items.push(fail("media", `A carousel can have up to ${MAX_ASSETS} photos and videos.`, "asset_ids"));
  } else if (assetIds.length > 1) {
    items.push(pass("media", `Carousel of ${assetIds.length}`));
  } else {
    items.push(pass("media", deriveFormat(known) === "reel" ? "Reel" : "Single image"));
  }

  // A single video for Instagram alone is a Reel: 3 seconds to 15 minutes (C-134); other videos stay at 90 seconds.
  const igAlone = ig && !fb && assetIds.length === 1;
  // media_files: each asset's aspect ratio and video length (type and size are checked on upload)
  const fileProblems: ChecklistItem[] = [];
  assetIds.forEach((id, index) => {
    const asset = assets[id];
    if (!asset) return;
    const label = assetLabel(asset, index);
    const crop = story || !ig ? null : cropNeeded(asset);
    const storyProblem = story ? storyVideoProblem(asset) : reel && fb ? reelVideoProblem(asset) : null;
    if (storyProblem) {
      fileProblems.push(fail("media_files", `${label}: ${storyProblem}`, `asset_ids.${index}`));
    } else if (crop) {
      const shape = crop === "tall" ? "taller than 4:5" : "wider than 1.91:1";
      fileProblems.push(fail("media_files", `${label} is ${shape}. Crop it to 1:1, 4:5 or 1.91:1.`, `asset_ids.${index}`));
    } else if (!story && igAlone && igReelProblem(asset)) {
      fileProblems.push(
        fail("media_files", `${label} is ${formatDuration(asset.duration_s ?? 0)} long. ${igReelProblem(asset)}`, `asset_ids.${index}`),
      );
    } else if (!story && !igAlone && videoTooLong(asset)) {
      fileProblems.push(
        fail(
          "media_files",
          `${label} is ${formatDuration(asset.duration_s ?? 0)} long. Instagram allows videos up to 90 seconds.`,
          `asset_ids.${index}`,
        ),
      );
    }
  });
  const offShape = (story || reel) && assetIds.length === 1 && assets[assetIds[0]] && storyShapeOff(assets[assetIds[0]]);
  const who = ig && fb ? "Instagram and Facebook" : fb ? "Facebook" : "Instagram";
  if (fileProblems.length) items.push(...fileProblems);
  else if (assetIds.length) {
    items.push(
      pass(
        "media_files",
        offShape
          ? `9:16 fits a ${story ? "Story" : "Reel"} best. ${who} may crop or add bars to this file.`
          : `Photos and videos fit ${ig && fb ? "Instagram's and Facebook's" : fb ? "Facebook's" : "Instagram's"} sizes`,
      ),
    );
  }

  // A Story has no caption, hashtags or mentions: what the draft holds is kept but never sent.
  if (story) {
    items.push(pass("caption", "Stories are published without a caption"));
    items.push(...extrasChecklist({ draft, assets, ig, story, reel, singleVideo: false }));
    return finishChecklist(items, draft, now);
  }

  // caption, hashtags, mentions: every caption, and the first comment's length and hashtags
  const slots = captionSlots(draft, accounts);
  const comment = draft.first_comment ?? "";
  const captionProblems: ChecklistItem[] = [];
  const hashtagProblems: ChecklistItem[] = [];
  const mentionProblems: ChecklistItem[] = [];
  for (const slot of slots) {
    const counts = countText(slot.text);
    if (counts.chars > slot.limit) {
      captionProblems.push(
        fail(
          "caption",
          `${slot.owner} is ${formatCount(counts.chars)} characters. ${slot.limit === CAPTION_MAX_CHARS ? "Instagram" : "Facebook"} allows ${formatCount(slot.limit)}.`,
          slot.field,
        ),
      );
    }
    if (ig && counts.hashtags > MAX_HASHTAGS) {
      hashtagProblems.push(
        fail("hashtags", `${slot.owner} has ${counts.hashtags} hashtags. Instagram allows ${MAX_HASHTAGS}.`, slot.field),
      );
    }
    if (ig && counts.mentions > MAX_MENTIONS) {
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
        `The first comment is ${formatCount(commentCounts.chars)} characters. ${limitName} allows ${formatCount(FIRST_COMMENT_MAX_CHARS)}.`,
        "first_comment",
      ),
    );
  }
  if (ig && commentCounts.hashtags > MAX_HASHTAGS) {
    hashtagProblems.push(
      fail("hashtags", `The first comment has ${commentCounts.hashtags} hashtags. Instagram allows ${MAX_HASHTAGS}.`, "first_comment"),
    );
  }
  items.push(...(captionProblems.length ? captionProblems : [pass("caption", `Caption within ${formatCount(captionLimit(selected.map((account) => account.platform)))} characters`)]));
  // Hashtag and mention limits are Instagram's: a post for Facebook Pages alone has none.
  if (ig) {
    items.push(...(hashtagProblems.length ? hashtagProblems : [pass("hashtags", `Up to ${MAX_HASHTAGS} hashtags`)]));
    items.push(...(mentionProblems.length ? mentionProblems : [pass("mentions", `Up to ${MAX_MENTIONS} mentions`)]));
  }

  const singleVideo = assetIds.length === 1 && assets[assetIds[0]]?.resource_type === "video";
  items.push(...extrasChecklist({ draft, assets, ig, story, reel, singleVideo }));
  return finishChecklist(items, draft, now);
}

type ExtrasInput = {
  draft: ScheduledPostDraft;
  assets: Record<string, AssetInfo>;
  ig: boolean;
  story: boolean;
  reel: boolean;
  /** The post's one asset is a video (an Instagram Reel). */
  singleVideo: boolean;
};

/**
 * The Instagram extras (FR-PUB-07, C-134): collaborators, user tags, the location and a Reel's
 * options. Nothing is listed for a post that uses none. They are Instagram's: a Story or a post
 * without an Instagram account cannot carry them.
 */
export function extrasChecklist({ draft, assets, ig, story, reel, singleVideo }: ExtrasInput): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const unavailable = (what: string, field: string): boolean => {
    if (story) {
      items.push(fail("extras", `${what} are not available on Stories. Remove them or publish a post.`, field));
      return true;
    }
    if (!ig || reel) {
      items.push(fail("extras", `${what} are an Instagram feature. Choose an Instagram account or remove them.`, field));
      return true;
    }
    return false;
  };

  const collaborators = draft.collaborators ?? [];
  if (collaborators.length && !unavailable("Collaborators", "collaborators")) {
    const names = collaborators.map((raw) => ({ raw, name: normalizeUsername(raw) }));
    const bad = names.find((item) => !item.name);
    const valid = [...new Set(names.flatMap((item) => (item.name ? [item.name] : [])))];
    if (bad) items.push(fail("extras", `${bad.raw} is not a valid Instagram username.`, "collaborators"));
    else if (valid.length > COLLABORATORS_MAX) {
      items.push(fail("extras", `Add at most ${COLLABORATORS_MAX} collaborators (now ${valid.length}).`, "collaborators"));
    } else items.push(pass("extras", `Collaborators: ${valid.map((name) => `@${name}`).join(", ")}`));
  }

  const tags = draft.user_tags ?? [];
  const assetIds = draft.asset_ids ?? [];
  const tagged = assetIds
    .map((id, index) => ({ index, count: tags.filter((tag) => tag.asset_id === id).length }))
    .filter((item) => item.count > 0);
  if (tagged.length && !unavailable("User tags", "asset_ids")) {
    const over = tagged.filter((item) => item.count > USER_TAGS_MAX_PER_IMAGE);
    for (const item of over) {
      items.push(fail("extras", `Tag at most ${USER_TAGS_MAX_PER_IMAGE} accounts in one photo (now ${item.count}).`, `asset_ids.${item.index}`));
    }
    if (!over.length) {
      const total = tagged.reduce((sum, item) => sum + item.count, 0);
      items.push(pass("extras", `${total} ${total === 1 ? "tag" : "tags"} on ${tagged.length} ${tagged.length === 1 ? "photo" : "photos"}`));
    }
  }

  if (draft.location && draft.location.trim() && !unavailable("Locations", "location")) {
    items.push(parseLocation(draft.location) ? pass("extras", "Location set") : fail("extras", LOCATION_HELP, "location"));
  }

  const cover = draft.cover_asset_id ? assets[draft.cover_asset_id] : undefined;
  const reelOptions =
    Boolean(draft.cover_asset_id) || draft.cover_offset_ms != null || draft.share_to_feed === false || Boolean(draft.audio_name?.trim());
  if (reelOptions) {
    if (story || !ig || reel || !singleVideo) {
      items.push(fail("extras", "Reel options only apply to a single Instagram video. Remove them.", "cover_asset_id"));
    } else {
      const problems: ChecklistItem[] = [];
      if (cover && cover.resource_type !== "image") problems.push(fail("extras", "The cover must be an image.", "cover_asset_id"));
      const video = assets[assetIds[0]];
      if (draft.cover_offset_ms != null && video?.duration_s != null && draft.cover_offset_ms > video.duration_s * 1000) {
        problems.push(fail("extras", "The cover frame is past the end of the video.", "cover_offset_ms"));
      }
      if ((draft.audio_name?.trim().length ?? 0) > AUDIO_NAME_MAX_CHARS) {
        problems.push(fail("extras", `Keep the audio name to ${AUDIO_NAME_MAX_CHARS} characters.`, "audio_name"));
      }
      items.push(...(problems.length ? problems : [pass("extras", "Reel options set")]));
    }
  }
  return items;
}

/** publish_at: only when the post has a time. */
function finishChecklist(items: ChecklistItem[], draft: ScheduledPostDraft, now: Date): ChecklistItem[] {
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
  if (["collaborators", "location", "user_tags", "cover_asset_id", "cover_offset_ms", "audio_name", "share_to_feed"].includes(field.split(".")[0])) {
    return "extras";
  }
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
    // The Instagram options report one passing line each under "extras"; every other key has one.
    const oks = source.filter((item) => item.key === key && item.ok);
    passing.push(...(key === "extras" ? oks : oks.slice(0, 1)));
  }
  const order = (item: ChecklistItem) => CHECKLIST_KEYS.indexOf(item.key);
  failures.sort((a, b) => order(a) - order(b));
  return { items: [...failures, ...passing], ready: failures.length === 0, failing: failures.length };
}
