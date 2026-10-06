import { describe, expect, it } from "vitest";

import { colorTokens } from "@/styles/tokens";

import { IDENTITIES, IDENTITY_FILL, identityAt, identityFor } from "./identity";

/** D-13 option 1: brand, shell and platform-blue values only; no status, no other platform. */
const ALLOWED = ["brand", "brand-strong", "brand-deep", "brand-fg", "shell-1", "shell-2", "facebook", "linkedin"];

function hex(name: string): string {
  const token = colorTokens.find((t) => t.name === name);
  if (!token || !/^#[0-9A-F]{6}$/i.test(token.value)) throw new Error(`no solid colour token "${name}"`);
  return token.value;
}

/** WCAG 2.2 contrast ratio between two solid colours. */
function contrast(a: string, b: string): number {
  const luminance = (h: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(h.slice(i, i + 2), 16) / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function stops(gradient: string): [string, string] {
  const match = /^from-([a-z0-9-]+) to-([a-z0-9-]+)$/.exec(gradient);
  if (!match) throw new Error(`not a two-stop gradient: "${gradient}"`);
  return [match[1], match[2]];
}

const ringToken = (ring: string) => ring.replace(/^ring-/, "");

describe("identity palette (D-13)", () => {
  it("has up to four identities, each a gradient pair, a ring and a matching solid dot", () => {
    expect(IDENTITIES.length).toBeGreaterThanOrEqual(2);
    expect(IDENTITIES.length).toBeLessThanOrEqual(4);
    for (const identity of IDENTITIES) {
      stops(identity.gradient);
      expect(identity.ring).toMatch(/^ring-[a-z0-9-]+$/);
      expect(identity.dot).toBe(`bg-${ringToken(identity.ring)}`);
    }
    expect(new Set(IDENTITIES.map((i) => i.gradient)).size).toBe(IDENTITIES.length);
    expect(new Set(IDENTITIES.map((i) => i.ring)).size).toBe(IDENTITIES.length);
  });

  it("uses only existing brand, shell and platform-blue values: no status or other platform colour", () => {
    for (const identity of IDENTITIES) {
      for (const name of [...stops(identity.gradient), ringToken(identity.ring)]) {
        expect(ALLOWED).toContain(name);
        hex(name);
      }
    }
  });

  it("keeps every gradient stop at 4.5:1 or more with the on-brand initial", () => {
    for (const identity of IDENTITIES) {
      for (const stop of stops(identity.gradient)) {
        expect(contrast(hex(stop), hex("on-brand")), `${stop} with on-brand`).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(IDENTITY_FILL.split(" ")).toEqual(expect.arrayContaining(["bg-linear-135", "text-on-brand"]));
  });

  it("keeps every ring at 3:1 or more on panel, and the rings apart from each other", () => {
    const rings = IDENTITIES.map((i) => hex(ringToken(i.ring)));
    for (const [i, ring] of rings.entries()) {
      expect(contrast(ring, hex("panel")), `${IDENTITIES[i].ring} on panel`).toBeGreaterThanOrEqual(3);
      for (const other of rings.slice(i + 1)) {
        // brand-strong and facebook, 1.07:1 apart, would read as one colour.
        expect(contrast(ring, other)).toBeGreaterThanOrEqual(1.3);
      }
    }
  });

  it("gives accounts the identities in order, cycling", () => {
    expect(identityAt(0)).toBe(IDENTITIES[0]);
    expect(identityAt(1)).toBe(IDENTITIES[1]);
    expect(identityAt(IDENTITIES.length)).toBe(IDENTITIES[0]);
    expect(identityAt(-1)).toBe(IDENTITIES[IDENTITIES.length - 1]);
  });

  it("picks a stable identity for an id and spreads ids over all of them", () => {
    expect(identityFor("0d9f3c1e-8a55-4c3e-9c43-1f7a2e6b8d10")).toBe(identityFor("0d9f3c1e-8a55-4c3e-9c43-1f7a2e6b8d10"));
    expect(IDENTITIES).toContain(identityFor(""));
    const used = new Set(Array.from({ length: 60 }, (_, i) => identityFor(`contact-${i}`)));
    expect(used.size).toBe(IDENTITIES.length);
  });
});
