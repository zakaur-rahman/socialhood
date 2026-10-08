import { describe, expect, it } from "vitest";

import { readyPost } from "@/test/composer-fixtures";

import { sameDraft, toDraft } from "./use-post-draft";

describe("sameDraft (UI-032: an undone edit is not unsaved)", () => {
  const stored = toDraft(readyPost({ publish_at: "2026-10-08T10:00:00Z", first_comment: null }));

  it("treats what the PUT would send as the post: the same instant, an empty first comment", () => {
    expect(sameDraft({ ...stored, publish_at: "2026-10-08T10:00:00.000Z" }, stored)).toBe(true);
    expect(sameDraft({ ...stored, first_comment: "" }, stored)).toBe(true);
    expect(sameDraft({ ...stored, targets: stored.targets.map((t) => ({ ...t })) }, stored)).toBe(true);
  });

  it("sees every edit", () => {
    expect(sameDraft({ ...stored, caption: `${stored.caption}!` }, stored)).toBe(false);
    expect(sameDraft({ ...stored, publish_at: "2026-10-08T10:15:00Z" }, stored)).toBe(false);
    expect(sameDraft({ ...stored, publish_at: null }, stored)).toBe(false);
    expect(sameDraft({ ...stored, first_comment: "#linen" }, stored)).toBe(false);
    expect(sameDraft({ ...stored, asset_ids: [] }, stored)).toBe(false);
    expect(
      sameDraft({ ...stored, targets: stored.targets.map((t) => ({ ...t, caption_override: stored.caption })) }, stored),
    ).toBe(false);
  });
});
