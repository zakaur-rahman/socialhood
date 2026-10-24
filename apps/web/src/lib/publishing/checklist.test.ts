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
      kind: "post",
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

describe("localChecklist for Facebook Pages (GR-30)", () => {
  const page = account({ id: "p1", username: "maple.page", platform: "facebook", capabilities: ["publish"] });
  const toPage = { targets: [{ social_account_id: "p1", caption_override: null }] };

  it("makes text with no media a text post, without Instagram's hashtag and mention checks", () => {
    const items = localChecklist(input({ ...toPage, asset_ids: [], caption: "Open late #a @b" }, { accounts: [page], assets: {} }));
    expect(failures(items)).toEqual([]);
    expect(items.map((item) => item.key)).toEqual(["accounts", "media", "caption"]);
    expect(items.find((item) => item.key === "media")?.message).toBe("Text post");
  });

  it("asks a Page for media or text", () => {
    expect(failures(localChecklist(input({ ...toPage, asset_ids: [], caption: " " }, { accounts: [page], assets: {} })))).toEqual([
      ["media", "asset_ids", "Add a photo or video, or write the post's text."],
    ]);
  });

  it("still needs media when an Instagram account is chosen too", () => {
    const items = localChecklist(
      input(
        { targets: [{ social_account_id: "a1", caption_override: null }, ...toPage.targets], asset_ids: [], caption: "Text only" },
        { accounts: [ready, page], assets: {} },
      ),
    );
    expect(failures(items)).toEqual([["media", "asset_ids", "Add a photo or video."]]);
  });

  it("takes a wide photo that Instagram would ask to crop", () => {
    const wide = assetInfo({ width: 3000, height: 500 });
    expect(failures(localChecklist(input(toPage, { accounts: [page], assets: { as1: wide } })))).toEqual([]);
    expect(
      failures(
        localChecklist(
          input(
            { targets: [{ social_account_id: "a1", caption_override: null }, ...toPage.targets] },
            { accounts: [ready, page], assets: { as1: wide } },
          ),
        ),
      ).map((row) => row[0]),
    ).toEqual(["media_files"]);
  });

  it("does not mix photos and a video on a Page", () => {
    const items = localChecklist(
      input(
        { ...toPage, asset_ids: ["as1", "as2"] },
        { accounts: [page], assets: { as1: assetInfo(), as2: assetInfo({ id: "as2", resource_type: "video", duration_s: 10 }) } },
      ),
    );
    expect(failures(items)).toEqual([["media", "asset_ids", "A Facebook post can have several photos or one video, not both."]]);
  });

  it("holds a Page to Facebook's caption limit and a cross-post to the strictest account (C-131)", () => {
    const long = "a".repeat(2201);
    expect(failures(localChecklist(input({ ...toPage, caption: long }, { accounts: [page] })))).toEqual([]);
    expect(failures(localChecklist(input({ ...toPage, caption: "a".repeat(63207) }, { accounts: [page] })))[0][2]).toContain("Facebook allows 63,206");
    expect(failures(localChecklist(input({ caption: long })))[0][2]).toContain("Instagram allows 2,200");
    const both = { targets: [{ social_account_id: "a1", caption_override: null }, ...toPage.targets] };
    expect(failures(localChecklist(input({ ...both, caption: long }, { accounts: [ready, page] })))[0][2]).toContain("Instagram allows 2,200");
  });

  it("holds each account's own caption to its platform's limit", () => {
    const long = "a".repeat(3000);
    const own = { targets: [{ social_account_id: "a1", caption_override: "short" }, { social_account_id: "p1", caption_override: long }] };
    expect(failures(localChecklist(input({ ...own, caption: "short" }, { accounts: [ready, page] })))).toEqual([]);
    const swapped = { targets: [{ social_account_id: "a1", caption_override: long }, { social_account_id: "p1", caption_override: "short" }] };
    expect(failures(localChecklist(input({ ...swapped, caption: "short" }, { accounts: [ready, page] })))[0].slice(0, 2)).toEqual(["caption", "targets.0.caption_override"]);
  });
});

describe("localChecklist as a Story (GR-39)", () => {
  const story = (overrides: Partial<ChecklistInput["draft"]> = {}, extra: Partial<Omit<ChecklistInput, "draft">> = {}) =>
    input({ kind: "story", caption: "kept, never sent #a #b", ...overrides }, extra);

  it("passes one photo, and skips the caption, hashtag and mention checks", () => {
    const items = localChecklist(story());
    expect(failures(items)).toEqual([]);
    expect(items.map((item) => item.key)).toEqual(["accounts", "media", "media_files", "caption"]);
    expect(items.find((item) => item.key === "media")?.message).toBe("Story");
    expect(items.find((item) => item.key === "caption")?.message).toBe("Stories are published without a caption");
  });

  it("is one photo or video, never a carousel", () => {
    expect(failures(localChecklist(story({ asset_ids: ["as1", "as2"] }, { assets: { as1: assetInfo(), as2: assetInfo({ id: "as2" }) } })))).toEqual([
      ["media", "asset_ids", "A Story is one photo or one video."],
    ]);
  });

  it("takes a tall photo without a crop, with a note about 9:16", () => {
    const tall = assetInfo({ width: 1000, height: 2400 });
    const wide = assetInfo({ width: 1600, height: 900 });
    expect(failures(localChecklist(story({}, { assets: { as1: tall } })))).toEqual([]);
    const note = localChecklist(story({}, { assets: { as1: wide } })).find((item) => item.key === "media_files");
    expect(note).toMatchObject({ ok: true, message: expect.stringContaining("9:16") });
  });

  it.each([
    [2, "Photo 1: Story videos must be at least 3 seconds."],
    [75, "Photo 1: Story videos can be up to 60 seconds."],
  ])("a %i second video fails", (duration, message) => {
    const video = assetInfo({ resource_type: "video", width: 1080, height: 1920, duration_s: duration });
    expect(failures(localChecklist(story({}, { assets: { as1: video } })))).toEqual([["media_files", "asset_ids.0", message.replace("Photo", "Video")]]);
  });

  it("a 75 second video is still fine as a Reel", () => {
    const video = assetInfo({ resource_type: "video", width: 1080, height: 1920, duration_s: 75 });
    expect(failures(localChecklist(input({}, { assets: { as1: video } }))).map((row) => row[0])).toEqual([]);
  });

  it("takes a Facebook Page as a Story target, and names who crops a file that is not 9:16 (C-131)", () => {
    const page = account({ id: "p1", username: "maple.page", platform: "facebook", capabilities: ["publish"] });
    const toPage = { targets: [{ social_account_id: "p1", caption_override: null }] };
    const wide = assetInfo({ width: 1600, height: 900 });
    expect(failures(localChecklist(story(toPage, { accounts: [page] })))).toEqual([]);
    const note = (items: ReturnType<typeof localChecklist>) => items.find((item) => item.key === "media_files")?.message;
    expect(note(localChecklist(story(toPage, { accounts: [page], assets: { as1: wide } })))).toBe(
      "9:16 fits a Story best. Facebook may crop or add bars to this file.",
    );
    const both = { targets: [{ social_account_id: "a1", caption_override: null }, ...toPage.targets] };
    expect(note(localChecklist(story(both, { accounts: [ready, page], assets: { as1: wide } })))).toBe(
      "9:16 fits a Story best. Instagram and Facebook may crop or add bars to this file.",
    );
  });
});

describe("localChecklist as a Facebook Reel (C-131)", () => {
  const page = account({ id: "p1", username: "maple.page", platform: "facebook", capabilities: ["publish"] });
  const toPage = { targets: [{ social_account_id: "p1", caption_override: null }] };
  const video = (duration: number | null = 20) => assetInfo({ resource_type: "video", width: 1080, height: 1920, duration_s: duration });
  const reel = (overrides: Partial<ChecklistInput["draft"]> = {}, extra: Partial<Omit<ChecklistInput, "draft">> = {}) =>
    input({ ...toPage, kind: "reel", caption: "Behind the counter", ...overrides }, { accounts: [page], assets: { as1: video() }, ...extra });

  it("passes one video for a Page, with the caption checks kept", () => {
    const items = localChecklist(reel());
    expect(failures(items)).toEqual([]);
    expect(items.find((item) => item.key === "media")?.message).toBe("Reel");
    expect(items.map((item) => item.key)).toContain("caption");
  });

  it("needs a Facebook Page", () => {
    expect(failures(localChecklist(reel({ targets: [{ social_account_id: "a1", caption_override: null }] }, { accounts: [ready] })))).toEqual([
      ["accounts", "targets", "Choose a Facebook Page for a Reel. Instagram already publishes a single video as a Reel."],
    ]);
  });

  it("is one video", () => {
    expect(failures(localChecklist(reel({}, { assets: { as1: assetInfo() } }))).map((row) => [row[0], row[2]])).toEqual([
      ["media", "A Facebook Reel is one video."],
    ]);
    expect(failures(localChecklist(reel({ asset_ids: ["as1", "as2"] }, { assets: { as1: video(), as2: video() } })))[0][2]).toBe("A Facebook Reel is one video.");
    expect(failures(localChecklist(reel({ asset_ids: [] })))).toEqual([["media", "asset_ids", "Add a video for the Reel."]]);
  });

  it("waits for the file to load before judging it", () => {
    expect(failures(localChecklist(reel({}, { assets: {} })))).toEqual([]);
  });

  it("a video under 3 seconds fails, and a file that is not 9:16 passes with a note", () => {
    expect(failures(localChecklist(reel({}, { assets: { as1: video(2) } })))).toEqual([
      ["media_files", "asset_ids.0", "Video 1: Reel videos must be at least 3 seconds."],
    ]);
    const wide = assetInfo({ resource_type: "video", width: 1920, height: 1080, duration_s: 20 });
    const note = localChecklist(reel({}, { assets: { as1: wide } })).find((item) => item.key === "media_files");
    expect(note?.message).toBe("9:16 fits a Reel best. Facebook may crop or add bars to this file.");
  });

  it("is never a text post", () => {
    expect(failures(localChecklist(reel({ asset_ids: [] }))).map((row) => row[0])).toEqual(["media"]);
  });
});

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
