import { describe, expect, it, vi } from "vitest";

import { ATTACHMENT_RULES, chunkRanges, SINGLE_UPLOAD_MAX_BYTES, STICKER_RULE, resourceTypeFor, sendToStorage } from "./upload";

const MB = 1024 * 1024;

function file(name: string, size = 1000, type = ""): File {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

describe("attachment rules (FR-INB-08, Meta's limits)", () => {
  it.each([
    ["instagram", "brochure.pdf", 1000, null],
    ["instagram", "note.m4a", 1000, null],
    ["instagram", "clip.webm", 20 * MB, null],
    ["instagram", "photo.png", 1000, null],
    ["instagram", "sheet.xlsx", 1000, "Instagram can't send this type of file."],
    ["instagram", "song.mp3", 1000, "Instagram can't send this type of file."],
    ["instagram", "clip.mp4", 26 * MB, "Videos can be up to 25 MB on Instagram."],
    ["whatsapp", "sheet.xlsx", 50 * MB, null],
    ["whatsapp", "song.mp3", 1000, null],
    ["whatsapp", "photo.jpg", 6 * MB, "Images can be up to 5 MB on WhatsApp."],
    ["whatsapp", "archive.zip", 1000, "WhatsApp can't send this type of file."],
  ] as const)("%s %s (%i bytes)", (platform, name, size, expected) => {
    expect(ATTACHMENT_RULES[platform].check(file(name, size))).toBe(expected);
  });

  it("lists every accepted extension for the file picker", () => {
    expect(ATTACHMENT_RULES.instagram.accept.split(",")).toEqual(
      expect.arrayContaining([".pdf", ".m4a", ".mp4", ".png"]),
    );
    expect(ATTACHMENT_RULES.whatsapp.accept).toContain(".docx");
  });

  it("stores audio as a Cloudinary video resource and documents as raw", () => {
    expect(resourceTypeFor(file("note.m4a"))).toBe("video");
    expect(resourceTypeFor(file("clip.mp4"))).toBe("video");
    expect(resourceTypeFor(file("photo.heic"))).toBe("image");
    expect(resourceTypeFor(file("brochure.pdf", 1000, "application/pdf"))).toBe("raw");
  });

  it("checks WhatsApp stickers", () => {
    expect(STICKER_RULE.check(file("wave.webp", 40_000))).toBeNull();
    expect(STICKER_RULE.check(file("wave.png", 40_000))).toBe("Stickers are WebP images.");
    expect(STICKER_RULE.check(file("wave.webp", 600 * 1024))).toBe("Stickers can be up to 500 KB.");
  });
});

describe("large video uploads (C-134)", () => {
  it("sends a file over 100 MB in 20 MB chunks that cover it exactly", () => {
    const size = 250 * MB + 5;
    const ranges = chunkRanges(size);
    expect(ranges).toHaveLength(13);
    expect(ranges[0]).toEqual({ start: 0, end: 20 * MB - 1 });
    expect(ranges.at(-1)?.end).toBe(size - 1);
    for (let i = 1; i < ranges.length; i += 1) expect(ranges[i].start).toBe(ranges[i - 1].end + 1);
  });

  it("sends a small file in one request", () => {
    expect(chunkRanges(5)).toEqual([{ start: 0, end: 4 }]);
    expect(SINGLE_UPLOAD_MAX_BYTES).toBe(100 * MB);
  });
});

describe("sendToStorage", () => {
  it("sends the signed file name with the upload", async () => {
    const sent: FormData[] = [];
    class FakeXhr {
      upload = {};
      status = 200;
      responseText = '{"public_id":"ws/w/message/abc"}';
      onload?: () => void;
      open() {}
      setRequestHeader() {}
      send(form: FormData) {
        sent.push(form);
        this.onload?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const signature = {
      api_key: "k",
      timestamp: 1,
      folder: "ws/w/message",
      public_id: "abc",
      allowed_formats: "png,jpg",
      signature: "s",
      upload_url: "https://api.cloudinary.com/v1_1/demo/image/upload",
      cloud_name: "demo",
    };

    await expect(sendToStorage(signature, new File(["x"], "a.png"))).resolves.toEqual({ public_id: "ws/w/message/abc" });
    expect(sent[0].get("public_id")).toBe("abc");
    expect(sent[0].get("allowed_formats")).toBe("png,jpg");
    vi.unstubAllGlobals();
  });
});
