import { describe, expect, it } from "vitest";

import { TONE_CLASS as INBOX_TONE_CLASS } from "@/lib/inbox/format";
import { CHIP_CLASS } from "@/lib/schedule/format";
import { colorTokens } from "@/styles/tokens";

import { TONE_CLASS, TONES } from "./tone";

const token = (name: string) => colorTokens.find((t) => t.name === name)?.value;

/** "#FB923C" and 0.15 → "rgb(251 146 60 / 0.15)", the way globals.css writes the soft tokens. */
function alpha(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255} / ${a.toFixed(2)})`;
}

describe("the tone map (lib/ui/tone)", () => {
  it("is the one source: the inbox's TONE_CLASS and the schedule's CHIP_CLASS are this map", () => {
    expect(INBOX_TONE_CLASS).toBe(TONE_CLASS);
    expect(CHIP_CLASS).toBe(TONE_CLASS);
    expect(Object.keys(TONE_CLASS).sort()).toEqual([...TONES].sort());
  });

  it("pairs each tone's fill with its text colour, through tokens only", () => {
    expect(TONE_CLASS).toEqual({
      neutral: "bg-hover text-fg-secondary",
      brand: "bg-brand-soft text-brand-fg",
      success: "bg-success-soft text-success",
      warning: "bg-warning-soft text-warning",
      danger: "bg-danger-soft text-danger-fg",
    });
    for (const classes of Object.values(TONE_CLASS)) {
      expect(classes).not.toMatch(/\/\d|white|black|\[/);
      expect(classes).not.toMatch(/text-danger(\s|$)/);
    }
  });

  it("keeps the colours the old maps drew (white/5 and the status colours at 15%), so nothing moves", () => {
    expect(token("hover")).toBe("rgb(255 255 255 / 0.05)");
    expect(token("brand-soft")).toBe(alpha(token("brand")!, 0.15));
    expect(token("success-soft")).toBe(alpha(token("success")!, 0.15));
    expect(token("warning-soft")).toBe(alpha(token("warning")!, 0.15));
    expect(token("danger-soft")).toBe(alpha(token("danger")!, 0.15));
  });
});
