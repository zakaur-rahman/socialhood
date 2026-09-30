/** Publishing fixtures for the composer's tests (P7). */
import type { MediaAsset } from "@/lib/api/types";
import type { AssetInfo } from "@/lib/publishing/rules";
import type { ChecklistItem, HashtagGroup, PostAsset, ScheduledPost, ScheduledPostTarget } from "@/lib/publishing/types";

export function postAsset(overrides: Partial<PostAsset> = {}): PostAsset {
  return {
    id: "as1",
    public_id: "ws/w1/post/as1",
    resource_type: "image",
    url: "https://res.cloudinary.com/demo/image/upload/ws/w1/post/as1.jpg",
    thumbnail_url: "https://res.cloudinary.com/demo/image/upload/ws/w1/post/as1.jpg",
    width: 1080,
    height: 1080,
    duration_s: null,
    position: 0,
    ...overrides,
  };
}

export function assetInfo(overrides: Partial<AssetInfo> = {}): AssetInfo {
  return {
    id: "as1",
    resource_type: "image",
    url: "https://res.cloudinary.com/demo/image/upload/as1.jpg",
    thumbnail_url: "https://res.cloudinary.com/demo/image/upload/as1.jpg",
    width: 1080,
    height: 1080,
    duration_s: null,
    name: null,
    ...overrides,
  };
}

export function mediaAsset(overrides: Partial<MediaAsset> = {}): MediaAsset {
  return {
    id: "ma1",
    public_id: "ws/w1/post/ma1",
    resource_type: "image",
    purpose: "post",
    format: "jpg",
    mime_type: "image/jpeg",
    original_filename: "dress.jpg",
    secure_url: "https://res.cloudinary.com/demo/image/upload/ws/w1/post/ma1.jpg",
    bytes: 120_000,
    width: 1080,
    height: 1350,
    duration_s: null,
    created_at: "2026-09-28T10:00:00Z",
    ...overrides,
  };
}

export function target(overrides: Partial<ScheduledPostTarget> = {}): ScheduledPostTarget {
  return {
    social_account_id: "a1",
    caption_override: null,
    status: "pending",
    platform_media_id: null,
    permalink: null,
    post_id: null,
    published_at: null,
    error: null,
    first_comment: null,
    ...overrides,
  };
}

/** A passing checklist as the API returns it for a complete post. */
export const READY_CHECKLIST: ChecklistItem[] = [
  { key: "accounts", ok: true, message: "1 account can publish", field: null },
  { key: "media", ok: true, message: "Single image", field: null },
  { key: "media_files", ok: true, message: "Photos and videos fit Instagram's sizes", field: null },
  { key: "caption", ok: true, message: "Caption within 2,200 characters", field: null },
  { key: "hashtags", ok: true, message: "Up to 30 hashtags", field: null },
  { key: "mentions", ok: true, message: "Up to 20 mentions", field: null },
  { key: "publishing_limit", ok: true, message: "Room in today's publishing limit", field: null },
];

export function scheduledPost(overrides: Partial<ScheduledPost> = {}): ScheduledPost {
  return {
    id: "sp1",
    status: "draft",
    format: null,
    caption: "",
    publish_at: null,
    published_at: null,
    thumbnail_url: null,
    asset_count: 0,
    targets: [],
    created_at: "2026-09-28T10:00:00Z",
    updated_at: "2026-09-28T10:00:00Z",
    first_comment: null,
    assets: [],
    automations: [],
    checklist: [],
    ready: false,
    created_by_user_id: null,
    ...overrides,
  };
}

/** A complete draft: one account, one square photo and a caption. */
export function readyPost(overrides: Partial<ScheduledPost> = {}): ScheduledPost {
  return scheduledPost({
    format: "image",
    caption: "New linen dresses are here #linen",
    asset_count: 1,
    targets: [target()],
    assets: [postAsset()],
    checklist: READY_CHECKLIST,
    ready: true,
    ...overrides,
  });
}

export function hashtagGroup(overrides: Partial<HashtagGroup> = {}): HashtagGroup {
  return {
    id: "hg1",
    name: "Summer",
    hashtags: ["summer", "linen", "ootd"],
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    ...overrides,
  };
}
