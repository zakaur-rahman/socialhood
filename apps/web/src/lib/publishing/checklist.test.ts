import { describe, expect, it } from "vitest";

import { account } from "@/test/api";
import { assetInfo } from "@/test/composer-fixtures";

import { itemsFromErrors, keyOfField, localChecklist, mergeChecklist, type ChecklistInput } from "./checklist";
import type { ChecklistItem } from "./types";

const now = new Date("2026-09-29T12:00:00Z");
const ready = account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] });

function input(overrides: Partial<ChecklistInput["draft"]> = {}, extra: Partial<Omit<ChecklistInput, "draft">> = {}): ChecklistInput {
  return {
    draft: {
      targets: [{ social_account_id: "a1", caption_override: null }],
      asset_ids: ["as1"],
      caption: "Hello",
      first_comment: null,
      publish_at: null,
      ...overrides,
    },
    accounts: [ready],
    assets: { as1: assetInfo() },
    now,
    ...extra,
  };
}

const failures = (items: ChecklistItem[]) => items.filter((item) => !item.ok).map((item) => [item.key, item.field, item.message]);

describe("localChecklist (FR-PUB-10)", () => {
  it("passes a complete post, one line per check", () => {
    const items = localChecklist(input());
    expect(failures(items)).toEqual([]);
    expect(items.map((item) => item.key)).toEqual(["accounts", "media", "media_files", "caption", "hashtags", "mentions"]);
  });

  it("asks for an account and media, naming the fields to fix", () => {
    expect(failures(localChecklist(input({ targets: [], asset_ids: [] })))).toEqual([
      ["accounts", "targets", "Choose at least one account."],
      ["media", "asset_ids", "Add a photo or video."],
    ]);
  });

  it("flags each account that can't publish on targets.{i}", () => {
    const stale = account({ id: "a2", username: "maple.studio", status: "needs_reconnect", capabilities: ["publish"] });
    const items = localChecklist(
      input(
        { targets: [{ social_account_id: "a1", caption_override: null }, { social_account_id: "a2", caption_override: null }] },
        { accounts: [ready, stale] },
      ),
    );
    expect(failures(items)).toEqual([
      ["accounts", "targets.1", "@maple.studio needs reconnecting before you can publish from it."],
    ]);
  });

  it("flags photos outside the ratios and long videos on asset_ids.{i}", () => {
    const items = localChecklist(
      input(
        { asset_ids: ["as1", "tall", "long"] },
        {
          assets: {
            as1: assetInfo(),
            tall: assetInfo({ id: "tall", width: 1080, height: 1920 }),
            long: assetInfo({ id: "long", resource_type: "video", duration_s: 125 }),
          },
        },
      ),
    );
    expect(failures(items)).toEqual([
      ["media_files", "asset_ids.1", "Photo 2 is taller than 4:5. Crop it to 1:1, 4:5 or 1.91:1."],
      ["media_files", "asset_ids.2", "Video 3 is 2:05 long. Instagram allows videos up to 90 seconds."],
    ]);
    expect(items.find((item) => item.key === "media")).toMatchObject({ ok: true, message: "Carousel of 3" });
  });

  it("refuses more than 10 items", () => {
    const ids = Array.from({ length: 11 }, (_, index) => `x${index}`);
    expect(failures(localChecklist(input({ asset_ids: ids }, { assets: {} })))).toEqual([
      ["media", "asset_ids", "A carousel can have up to 10 photos and videos."],
    ]);
  });

  it("checks every caption, the per-account ones and the first comment", () => {
    const long = "a".repeat(2201);
    const tags = Array.from({ length: 31 }, (_, index) => `#t${index}`).join(" ");
    const mentions = Array.from({ length: 21 }, (_, index) => `@u${index}`).join(" ");
    const items = localChecklist(
      input({
        caption: long,
        targets: [{ social_account_id: "a1", caption_override: `${tags} ${mentions}` }],
        first_comment: tags,
      }),
    );
    expect(failures(items)).toEqual([
      ["caption", "caption", "The caption is 2,201 characters. Instagram allows 2,200."],
      ["hashtags", "targets.0.caption_override", "The caption for @maple.bakery has 31 hashtags. Instagram allows 30."],
      ["hashtags", "first_comment", "The first comment has 31 hashtags. Instagram allows 30."],
      ["mentions", "targets.0.caption_override", "The caption for @maple.bakery mentions 21 accounts. Instagram allows 20."],
    ]);
  });

  it("checks the time only when the post has one: at least 5 minutes away", () => {
    expect(localChecklist(input()).some((item) => item.key === "publish_at")).toBe(false);
    expect(failures(localChecklist(input({ publish_at: "2026-09-29T12:03:00Z" })))).toEqual([
      ["publish_at", "publish_at", "Pick a time at least 5 minutes from now."],
    ]);
    expect(localChecklist(input({ publish_at: "2026-09-29T12:05:00Z" })).find((item) => item.key === "publish_at")?.ok).toBe(true);
  });
});

describe("mergeChecklist", () => {
  const local = localChecklist(input());
  const limit: ChecklistItem = { key: "publishing_limit", ok: false, message: "@maple.bakery has used today's 100 posts.", field: "targets.0" };
  const serverCaption: ChecklistItem = { key: "caption", ok: false, message: "Server says no", field: "caption" };

  it("keeps the API's own checks even while edits are unsaved", () => {
    const merged = mergeChecklist(local, [limit, serverCaption], false);
    expect(merged.ready).toBe(false);
    expect(failures(merged.items)).toEqual([["publishing_limit", "targets.0", limit.message]]);
  });

  it("adds the API's failures for the checks both make once the draft on screen is saved", () => {
    const merged = mergeChecklist(local, [serverCaption], true);
    expect(failures(merged.items)).toEqual([["caption", "caption", "Server says no"]]);
    expect(merged.failing).toBe(1);
  });

  it("lists failures first in checklist order, then one passing line per check", () => {
    const merged = mergeChecklist(localChecklist(input({ targets: [] })), [{ ...limit, ok: true, message: "Room today", field: null }], true, [
      { key: "publish_at", ok: false, message: "Pick a later time.", field: "publish_at" },
    ]);
    expect(merged.items.map((item) => [item.key, item.ok])).toEqual([
      ["accounts", false],
      ["publish_at", false],
      ["media", true],
      ["media_files", true],
      ["caption", true],
      ["hashtags", true],
      ["mentions", true],
      ["publishing_limit", true],
    ]);
  });

  it("is ready when nothing fails", () => {
    expect(mergeChecklist(local, [], true)).toMatchObject({ ready: true, failing: 0 });
  });
});

describe("422 field errors", () => {
  it("become checklist items under the check they belong to", () => {
    expect(
      itemsFromErrors([
        { field: "targets.1", message: "@x has no posting times." },
        { field: "asset_ids.0", message: "Instagram can't publish this file." },
        { field: "publish_at", message: "Pick a time at least 5 minutes from now." },
      ]).map((item) => [item.key, item.field]),
    ).toEqual([
      ["accounts", "targets.1"],
      ["media_files", "asset_ids.0"],
      ["publish_at", "publish_at"],
    ]);
    expect(keyOfField("targets.0.caption_override")).toBe("caption");
    expect(keyOfField("first_comment")).toBe("caption");
    expect(keyOfField("asset_ids")).toBe("media");
  });
});
