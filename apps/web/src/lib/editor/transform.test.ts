/**
 * The golden cases (packages/editor-fixtures/transform-cases.json, written from the API's builder):
 * this builder must give the same transformation, URL and size for every one, and carry the same
 * constants. apps/api/tests/unit/test_editor_transform.py runs the same file.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { EDITOR_CONSTANTS, emptySpec, normalizeSpec, textLayer, withLook, type PartialEditSpec } from "./spec";
import { assetMetaOf, build, cloudNameOf, cover, encodeText, fmt, still, type AssetMeta, type Built } from "./transform";

type Expected = Omit<Built, "duration_s"> & { duration_s?: number };
type Case = {
  name: string;
  valid: boolean;
  asset: AssetMeta;
  spec: PartialEditSpec;
  logo_public_id?: string;
  expect: {
    build: Expected;
    stills: (Expected & { at_s: number; max_width: number | null })[];
    cover: Expected | null;
  };
};
type Fixtures = { constants: Record<string, unknown>; cases: Case[] };

// vitest runs from apps/web.
const FIXTURES = resolve(process.cwd(), "../../packages/editor-fixtures/transform-cases.json");
const fixtures = JSON.parse(readFileSync(FIXTURES, "utf-8")) as Fixtures;

function same(actual: Built, expected: Expected) {
  expect({ ...actual, duration_s: actual.duration_s ?? undefined }).toEqual({ ...expected, duration_s: expected.duration_s });
}

describe("golden transformation cases", () => {
  it("has enough cases to mean something", () => {
    expect(fixtures.cases.length).toBeGreaterThanOrEqual(40);
  });

  it("carries the same constants as the API", () => {
    expect(JSON.parse(JSON.stringify(EDITOR_CONSTANTS))).toEqual(fixtures.constants);
  });

  it.each(fixtures.cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const options = { logoPublicId: c.logo_public_id ?? null };
    same(build(c.asset, c.spec, options), c.expect.build);
    for (const s of c.expect.stills) {
      same(still(c.asset, c.spec, { ...options, atS: s.at_s, maxWidth: s.max_width }), {
        kind: s.kind,
        transformation: s.transformation,
        format: s.format,
        url: s.url,
        width: s.width,
        height: s.height,
      });
    }
    const made = cover(c.asset, c.spec, options);
    if (c.expect.cover === null) expect(made).toBeNull();
    else same(made!, c.expect.cover);
  });
});

describe("helpers", () => {
  it("formats seconds with at most two decimals", () => {
    expect([0, 1, 1.5, 2.25, 3.333, 0.005, 12.1].map(fmt)).toEqual(["0", "1", "1.5", "2.25", "3.33", "0.01", "12.1"]);
  });

  it("encodes text for Cloudinary's text layers", () => {
    expect(encodeText("a, b/c 50%")).toBe("a%252C%20b%252Fc%2050%2525");
    expect(encodeText("Café 🔥")).toBe("Caf%C3%A9%20");
  });

  it("reads the cloud and size of an upload", () => {
    const url = "https://res.cloudinary.com/sh-demo/video/upload/v17/ws/x/post/clip.mp4";
    expect(cloudNameOf(url)).toBe("sh-demo");
    expect(cloudNameOf("https://example.com/a.jpg")).toBeNull();
    expect(
      assetMetaOf({ public_id: "ws/x/post/clip", resource_type: "video", url, width: 1920, height: 1080, duration_s: 12 }),
    ).toEqual({ cloud_name: "sh-demo", public_id: "ws/x/post/clip", resource_type: "video", width: 1920, height: 1080, duration_s: 12 });
    expect(assetMetaOf({ public_id: "ws/x/post/a", resource_type: "image", url, width: null, height: 10 })).toBeNull();
  });

  it("fills a partial spec with the API's defaults", () => {
    const spec = normalizeSpec({ texts: [{ text: "Hi" }], crop: { aspect: "4:5" } });
    expect(spec.texts?.[0]).toEqual(textLayer({ text: "Hi" }));
    expect(spec.crop).toEqual({ aspect: "4:5", zoom: 1, x: 0.5, y: 0.5 });
    expect(normalizeSpec({})).toEqual(emptySpec());
  });

  it("copies a photo's look without its crop or text", () => {
    const source = normalizeSpec({ preset: "noir", adjust: { contrast: 5 }, look: "zorro", enhance: true });
    const target = normalizeSpec({ crop: { aspect: "1:1" }, texts: [{ text: "Mine" }] });
    const copied = withLook(target, source);
    expect(copied.preset).toBe("noir");
    expect(copied.adjust?.contrast).toBe(5);
    expect(copied.look).toBe("zorro");
    expect(copied.enhance).toBe(true);
    expect(copied.crop).toEqual(target.crop);
    expect(copied.texts).toEqual(target.texts);
  });
});
