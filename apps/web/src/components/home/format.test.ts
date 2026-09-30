import { describe, expect, it } from "vitest";

import { countTrend, formatPercent, formatShare, formatSpan, formatWait, rateTrend, waitTrend } from "./format";

describe("Home formatting (UX-SCR-01)", () => {
  it("formats waits from seconds to days", () => {
    expect(formatWait(null)).toBe("—");
    expect(formatWait(0)).toBe("0 s");
    expect(formatWait(45)).toBe("45 s");
    expect(formatWait(60)).toBe("1 min");
    expect(formatWait(465)).toBe("7 min 45 s");
    expect(formatWait(1500)).toBe("25 min");
    expect(formatWait(3600)).toBe("1 h");
    expect(formatWait(3900)).toBe("1 h 5 min");
    expect(formatWait(7190)).toBe("2 h"); // 1 h 59.8 min rounds up to the hour
    expect(formatWait(519601)).toBe("6 d");
    expect(formatWait(190800)).toBe("2 d 5 h");
  });

  it("shows the API's shares, and a dash when there was nothing to divide", () => {
    expect(formatPercent(62.5)).toBe("62.5%");
    expect(formatPercent(40)).toBe("40%");
    expect(formatPercent(null)).toBe("—");
    expect(formatShare(57.1)).toBe("57%");
    expect(formatShare(null)).toBe("—");
  });

  it("compares counts with the period before, not when it had none", () => {
    expect(countTrend(10, 8, "7d")).toEqual({
      direction: "up",
      good: null,
      text: "+25%",
      words: "up 25% from the previous 7 days",
    });
    expect(countTrend(6, 8, "30d")?.text).toBe("−25%");
    expect(countTrend(8, 8, "7d")).toMatchObject({ direction: "flat", text: "No change" });
    expect(countTrend(8, 0, "7d")).toBeNull();
  });

  it("compares shares in points, and waits with shorter as good news", () => {
    expect(rateTrend(40, 35.5, "7d")).toMatchObject({ text: "+4.5 pts", good: true, words: "up 4.5 points from the previous 7 days" });
    expect(rateTrend(40, 50, "7d", "neither")).toMatchObject({ text: "−10 pts", good: null });
    expect(rateTrend(null, 50, "7d")).toBeNull();
    expect(waitTrend(465, 930, "7d")).toMatchObject({ direction: "down", good: true, text: "−50%" });
    expect(waitTrend(930, 465, "7d")).toMatchObject({ direction: "up", good: false, text: "+100%" });
    expect(waitTrend(465, null, "7d")).toBeNull();
  });

  it("names the range's local days", () => {
    expect(formatSpan("2026-09-24", "2026-09-30")).toBe("24–30 Sep");
    expect(formatSpan("2026-09-01", "2026-09-30")).toBe("1–30 Sep");
    expect(formatSpan("2026-10-30", "2026-11-05")).toBe("30 Oct–5 Nov");
    expect(formatSpan("2026-12-28", "2027-01-03")).toBe("28 Dec 2026–3 Jan 2027");
  });
});
