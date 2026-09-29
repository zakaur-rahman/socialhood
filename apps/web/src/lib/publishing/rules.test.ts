import { describe, expect, it } from "vitest";

import { account } from "@/test/api";
import { assetInfo, mediaAsset } from "@/test/composer-fixtures";

import {
  appendHashtags,
  cannotPublishReason,
  charCount,
  checkPostFile,
  countText,
  cropNeeded,
  deriveFormat,
  formatDuration,
  fromMediaAsset,
  hashtagsIn,
  mentionsIn,
  UNSUPPORTED_MEDIA,
  videoTooLong,
} from "./rules";

const MB = 1024 * 1024;

function file(name: string, size = 1000): File {
  const f = new File(["x"], name);
  Object.defineProperty(f, "size", { value: size });
  return f;
}

describe("caption counters (FR-PUB-10)", () => {
  it("counts characters as code points, so an emoji is one", () => {
    expect(charCount("hi 👋")).toBe(4);
    expect(charCount("नमस्ते")).toBe(6);
  });

  it("finds hashtags in any script, but not inside words or entities", () => {
    expect(hashtagsIn("Fresh #Linen and #दिवाली_sale!")).toEqual(["linen", "दिवाली_sale"]);
    expect(hashtagsIn("abc#def &#123; # alone")).toEqual([]);
    expect(hashtagsIn("#one#two")).toEqual(["one"]);
  });

  it("keeps Devanagari vowel signs, viramas and zero-width joiners inside a hashtag, like the API", () => {
    expect(hashtagsIn("#नमस्ते #हिंदी #मराठी")).toEqual(["नमस्ते", "हिंदी", "मराठी"]);
    expect(hashtagsIn("#क्‍ष")).toEqual(["क्‍ष"]);
  });

  it("finds @mentions, not email addresses", () => {
    expect(mentionsIn("Thanks @priya.styles and @maple_bakery.")).toEqual(["priya.styles", "maple_bakery"]);
    expect(mentionsIn("Write to hello@maple.example")).toEqual([]);
  });

  it("counts all three at once", () => {
    expect(countText("Hi @a #b #c")).toEqual({ chars: 11, hashtags: 2, mentions: 1 });
  });
});

describe("appendHashtags (FR-PUB-12)", () => {
  it("puts new hashtags on their own line after a blank line", () => {
    expect(appendHashtags("New dresses", ["linen", "#Summer"])).toBe("New dresses\n\n#linen #summer");
  });

  it("joins a last line that is already hashtags, skipping ones present", () => {
    expect(appendHashtags("New dresses\n\n#linen", ["linen", "ootd"])).toBe("New dresses\n\n#linen #ootd");
  });

  it("starts an empty text with the hashtags, and leaves the text when nothing is new", () => {
    expect(appendHashtags("", ["a", "b"])).toBe("#a #b");
    expect(appendHashtags("Hi #a", ["A"])).toBe("Hi #a");
  });
});

describe("post files (TR-MED-02)", () => {
  it.each([
    ["photo.jpg", 2 * MB, null],
    ["photo.HEIC", 2 * MB, null],
    ["photo.png", 9 * MB, "Photos can be up to 8 MB on Instagram."],
    ["clip.mov", 90 * MB, null],
    ["clip.mp4", 101 * MB, "Videos can be up to 100 MB on Instagram."],
    ["clip.webm", 1 * MB, UNSUPPORTED_MEDIA],
    ["menu.pdf", 1 * MB, UNSUPPORTED_MEDIA],
  ] as const)("%s (%i bytes)", (name, size, expected) => {
    expect(checkPostFile(file(name, size))).toBe(expected);
  });

  it("offers a crop outside 4:5 to 1.91:1, for photos only", () => {
    expect(cropNeeded(assetInfo({ width: 1080, height: 1350 }))).toBeNull(); // 4:5
    expect(cropNeeded(assetInfo({ width: 1910, height: 1000 }))).toBeNull(); // 1.91:1
    expect(cropNeeded(assetInfo({ width: 1080, height: 1920 }))).toBe("tall"); // 9:16
    expect(cropNeeded(assetInfo({ width: 3000, height: 1000 }))).toBe("wide");
    expect(cropNeeded(assetInfo({ resource_type: "video", width: 1080, height: 1920 }))).toBeNull();
    expect(cropNeeded(assetInfo({ width: null, height: null }))).toBeNull();
  });

  it("flags videos over 90 seconds", () => {
    expect(videoTooLong(assetInfo({ resource_type: "video", duration_s: 90 }))).toBe(false);
    expect(videoTooLong(assetInfo({ resource_type: "video", duration_s: 125 }))).toBe(true);
    expect(formatDuration(125)).toBe("2:05");
  });

  it("derives the format: one photo, one video (a Reel), or a carousel", () => {
    expect(deriveFormat([])).toBeNull();
    expect(deriveFormat([{ resource_type: "image" }])).toBe("image");
    expect(deriveFormat([{ resource_type: "video" }])).toBe("reel");
    expect(deriveFormat([{ resource_type: "image" }, { resource_type: "video" }])).toBe("carousel");
  });

  it("reads an upload or library item, leaving out documents", () => {
    expect(fromMediaAsset(mediaAsset())).toMatchObject({ id: "ma1", resource_type: "image", width: 1080, height: 1350, name: "dress.jpg" });
    expect(fromMediaAsset(mediaAsset({ resource_type: "raw" }))).toBeNull();
  });
});

describe("accounts that can publish", () => {
  it("names why an account can't publish", () => {
    expect(cannotPublishReason(account({ capabilities: ["publish"] }))).toBeNull();
    expect(cannotPublishReason(account({ status: "needs_reconnect", capabilities: ["publish"] }))).toBe("Needs reconnecting");
    expect(cannotPublishReason(account({ status: "disconnected" }))).toBe("Disconnected");
    expect(cannotPublishReason(account({ capabilities: ["dm_send"] }))).toBe("Reconnect to allow publishing");
  });
});
