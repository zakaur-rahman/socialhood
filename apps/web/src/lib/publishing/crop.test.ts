import { describe, expect, it } from "vitest";

import { CROP_RATIOS, cropRect, focusOf, moveFocus, suggestedRatio } from "./crop";

describe("crop (TR-MED-02)", () => {
  it("suggests 4:5 for tall photos and 1.91:1 for wide ones", () => {
    expect(suggestedRatio(1080, 1920).key).toBe("4:5");
    expect(suggestedRatio(4000, 1000).key).toBe("1.91:1");
    expect(suggestedRatio(1000, 1050).key).toBe("1:1");
  });

  it("takes the largest rectangle of the ratio, centred", () => {
    expect(cropRect(1080, 1920, 1)).toEqual({ x: 0, y: 420, width: 1080, height: 1080 });
    expect(cropRect(1080, 1920, 4 / 5)).toEqual({ x: 0, y: 285, width: 1080, height: 1350 });
    expect(cropRect(4000, 1000, 1.91)).toEqual({ x: 1045, y: 0, width: 1910, height: 1000 });
  });

  it("moves the frame with the focus, stopping at the edges", () => {
    expect(cropRect(1080, 1920, 1, { x: 0.5, y: 0 })).toEqual({ x: 0, y: 0, width: 1080, height: 1080 });
    expect(cropRect(1080, 1920, 1, { x: 0.5, y: 1 })).toEqual({ x: 0, y: 840, width: 1080, height: 1080 });
    expect(moveFocus({ x: 0.99, y: 0.5 }, 0.05, -0.6)).toEqual({ x: 1, y: 0 });
  });

  it("keeps the frame's centre when the shape changes", () => {
    const rect = cropRect(1080, 1920, 1, { x: 0.5, y: 0.2 });
    const focus = focusOf(rect, 1080, 1920);
    expect(cropRect(1080, 1920, 1, focus)).toEqual(rect);
    expect(CROP_RATIOS.map((ratio) => ratio.key)).toEqual(["1:1", "4:5", "1.91:1"]);
  });
});
