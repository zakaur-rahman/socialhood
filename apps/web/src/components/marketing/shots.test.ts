import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { SHOTS } from "./shots";

const PUBLIC = join(__dirname, "..", "..", "..", "public");

/** A WebP file's pixel size, from its VP8X, VP8 or VP8L header. */
function webpSize(bytes: Buffer): { width: number; height: number } {
  expect(bytes.toString("ascii", 0, 4)).toBe("RIFF");
  expect(bytes.toString("ascii", 8, 12)).toBe("WEBP");
  const chunk = bytes.toString("ascii", 12, 16);
  if (chunk === "VP8X") return { width: 1 + bytes.readUIntLE(24, 3), height: 1 + bytes.readUIntLE(27, 3) };
  if (chunk === "VP8 ") return { width: bytes.readUInt16LE(26) & 0x3fff, height: bytes.readUInt16LE(28) & 0x3fff };
  const bits = bytes.readUInt32LE(21); // VP8L
  return { width: (bits & 0x3fff) + 1, height: ((bits >> 14) & 0x3fff) + 1 };
}

describe("the landing page's product screenshots", () => {
  it("each is a WebP in public/marketing whose size matches what the page reserves for it", () => {
    for (const shot of Object.values(SHOTS)) {
      expect(shot.src).toMatch(/^\/marketing\/[a-z-]+\.webp$/);
      const bytes = readFileSync(join(PUBLIC, shot.src));
      expect(webpSize(bytes), shot.src).toEqual({ width: shot.width, height: shot.height });
      // Optimised: none of them is a heavy download.
      expect(bytes.length, shot.src).toBeLessThan(300 * 1024);
      expect(shot.alt.length).toBeGreaterThan(30);
    }
  });

  it("every file there is used", () => {
    const used = new Set(Object.values(SHOTS).map((shot) => shot.src.replace("/marketing/", "")));
    expect(readdirSync(join(PUBLIC, "marketing")).filter((name) => name.endsWith(".webp")).sort()).toEqual([...used].sort());
  });
});
