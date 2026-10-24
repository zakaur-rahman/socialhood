import { describe, expect, it } from "vitest";

import { colorValue } from "./tokens";
import type { Theme } from "./tokens";

/**
 * The contrast of the key token pairs in both themes (C-101, C-102), by the WCAG 2.x formula. The
 * numbers in globals.css's comments and THEME.md are these, measured; this test is what keeps them
 * true when a value changes. Text is 4.5:1, non-text marks and control edges 3:1.
 */
type Rgb = [number, number, number];
type Rgba = [number, number, number, number];

function parse(value: string): Rgba {
  const hex = value.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (hex) return [parseInt(hex[1], 16), parseInt(hex[2], 16), parseInt(hex[3], 16), 1];
  const rgb = value.match(/^rgb\((\d+) (\d+) (\d+)(?: \/ ([\d.]+))?\)$/);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), rgb[4] === undefined ? 1 : Number(rgb[4])];
  throw new Error(`Not a plain colour: ${value}`);
}

/** `top` laid over the opaque `base`. */
function over(top: Rgba, base: Rgb): Rgb {
  const [r, g, b, a] = top;
  return [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)];
}

function luminance([r, g, b]: Rgb): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function ratio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const SURFACES = ["canvas", "panel", "field", "raised", "raised-hover", "overlay"] as const;

function suite(theme: Theme, floor: { secondary: number; brandFg: number }) {
  const token = (name: string): Rgba => parse(colorValue(name, theme));
  const solid = (name: string): Rgb => over(token(name), [0, 0, 0]);
  /** A token over a surface (alpha tokens are composited; the surface is opaque). */
  const on = (name: string, surface: string): Rgb => over(token(name), solid(surface));

  describe(`${theme} palette`, () => {
    it.each(SURFACES)("fg reads on %s at 7:1 or more", (surface) => {
      expect(ratio(solid("fg"), solid(surface))).toBeGreaterThanOrEqual(7);
    });

    it.each(SURFACES)(`fg-secondary is ${floor.secondary}:1 or more on %s`, (surface) => {
      expect(ratio(solid("fg-secondary"), solid(surface))).toBeGreaterThanOrEqual(floor.secondary);
    });

    it.each(SURFACES)("line-control, the edge of a control, is 3:1 or more on %s", (surface) => {
      expect(ratio(on("line-control", surface), solid(surface))).toBeGreaterThanOrEqual(3);
    });

    it.each(SURFACES)("brand marks (focus ring, switch on) are 3:1 or more on %s", (surface) => {
      expect(ratio(solid("brand"), solid(surface))).toBeGreaterThanOrEqual(3);
    });

    it.each(SURFACES)(`brand-fg text is ${floor.brandFg}:1 or more on %s`, (surface) => {
      expect(ratio(solid("brand-fg"), solid(surface))).toBeGreaterThanOrEqual(floor.brandFg);
    });

    it("carries on-brand text on brand-strong and danger-fill at 4.5:1 or more", () => {
      expect(ratio(solid("on-brand"), solid("brand-strong"))).toBeGreaterThanOrEqual(5.8);
      expect(ratio(solid("on-brand"), solid("danger-fill"))).toBeGreaterThanOrEqual(4.5);
    });

    it.each(["panel", "field", "canvas"] as const)("keeps brand-fg readable on brand-soft over %s", (surface) => {
      const fill = over(token("brand-soft"), solid(surface));
      expect(ratio(solid("brand-fg"), fill)).toBeGreaterThanOrEqual(4.5);
    });

    it.each([
      ["success", "success-soft"],
      ["warning", "warning-soft"],
      ["danger-fg", "danger-soft"],
    ] as const)("keeps %s text readable on %s over panel and field", (text, soft) => {
      for (const surface of ["panel", "field"] as const) {
        // The light status colours are chosen dark enough to be text; the dark ones sit on dark fills.
        expect(ratio(solid(text), over(token(soft), solid(surface))), `${text} on ${soft} over ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    });

    it("keeps disabled text quieter than secondary text", () => {
      expect(ratio(solid("fg-disabled"), solid("panel"))).toBeLessThan(ratio(solid("fg-secondary"), solid("panel")));
    });
  });
}

suite("dark", { secondary: 5.4, brandFg: 6.4 });
suite("light", { secondary: 5.0, brandFg: 5.7 });

describe("the light palette's order", () => {
  it("is a soft cool canvas under white panels, with the selected state a step darker than the field", () => {
    const l = (name: string) => luminance(over(parse(colorValue(name, "light")), [0, 0, 0]));
    expect(colorValue("panel", "light").toLowerCase()).toBe("#ffffff");
    expect(l("canvas")).toBeLessThan(l("panel"));
    expect(l("raised")).toBeLessThan(l("field"));
    expect(l("raised-hover")).toBeLessThan(l("raised"));
  });
});
