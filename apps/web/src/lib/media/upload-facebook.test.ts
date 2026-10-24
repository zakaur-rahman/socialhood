import { describe, expect, it } from "vitest";

import { ATTACHMENT_RULES } from "./upload";

const MB = 1024 * 1024;

function file(name: string, size = 1000): File {
  const f = new File(["x"], name, { type: "" });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

// GR-29: Messenger takes images, video, audio and files by URL up to 25 MB (unverified until a
// real Page confirms it); the API's rules for a Page (services/sending.SEND_RULES) match.
describe("attachment rules for a Facebook Page", () => {
  it.each([
    ["photo.png", 24 * MB, null],
    ["photo.jpg", 26 * MB, "Images can be up to 25 MB on Facebook."],
    ["clip.mp4", 25 * MB, null],
    ["clip.mp4", 26 * MB, "Videos can be up to 25 MB on Facebook."],
    ["song.mp3", 5 * MB, null],
    ["note.m4a", 1000, null],
    ["brochure.pdf", 1000, null],
    ["sheet.xlsx", 20 * MB, null],
    ["archive.zip", 1000, "Facebook can't send this type of file."],
  ] as const)("%s (%i bytes)", (name, size, expected) => {
    expect(ATTACHMENT_RULES.facebook.check(file(name, size))).toBe(expected);
  });

  it("offers the same kinds in the file picker", () => {
    expect(ATTACHMENT_RULES.facebook.accept.split(",")).toEqual(
      expect.arrayContaining([".png", ".mp4", ".mp3", ".pdf", ".docx"]),
    );
  });
});
