import { describe, expect, it } from "vitest";

import {
  agoLabel,
  channelsConnected,
  channelsLine,
  countTrend,
  formatPercent,
  formatShare,
  formatSpan,
  formatWait,
  periodLabel,
  periodPhrase,
  rangeHeading,
  rateTrend,
  waitTrend,
} from "./format";

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
    expect(countTrend(10, 8, "7 days")).toEqual({
      direction: "up",
      good: null,
      text: "+25%",
      words: "up 25% from the previous 7 days",
    });
    expect(countTrend(6, 8, "30 days")?.text).toBe("−25%");
    expect(countTrend(8, 8, "7 days")).toMatchObject({ direction: "flat", text: "No change" });
    expect(countTrend(8, 0, "7 days")).toBeNull();
  });

  it("compares shares in points, and waits with shorter as good news", () => {
    expect(rateTrend(40, 35.5, "7 days")).toMatchObject({ text: "+4.5 pts", good: true, words: "up 4.5 points from the previous 7 days" });
    expect(rateTrend(40, 50, "7 days", "neither")).toMatchObject({ text: "−10 pts", good: null });
    expect(rateTrend(null, 50, "7 days")).toBeNull();
    expect(waitTrend(465, 930, "7 days")).toMatchObject({ direction: "down", good: true, text: "−50%" });
    expect(waitTrend(930, 465, "7 days")).toMatchObject({ direction: "up", good: false, text: "+100%" });
    expect(waitTrend(465, null, "7 days")).toBeNull();
  });

  it("names the range's local days", () => {
    expect(formatSpan("2026-09-24", "2026-09-30")).toBe("24–30 Sep");
    expect(formatSpan("2026-09-01", "2026-09-30")).toBe("1–30 Sep");
    expect(formatSpan("2026-10-30", "2026-11-05")).toBe("30 Oct–5 Nov");
    expect(formatSpan("2026-12-28", "2027-01-03")).toBe("28 Dec 2026–3 Jan 2027");
  });

  it("names a custom period by its length, and compares it with as many days before", () => {
    expect(periodLabel(1)).toBe("1 day");
    expect(periodLabel(12)).toBe("12 days");
    expect(rangeHeading({ range: "7d", days: 7 })).toBe("Last 7 days");
    expect(rangeHeading({ range: "custom", days: 12 })).toBe("12 days");
    expect(periodPhrase({ range: "30d", days: 30 })).toBe("the last 30 days");
    expect(periodPhrase({ range: "custom", days: 12 })).toBe("these 12 days");
    expect(countTrend(12, 10, "12 days")?.words).toBe("up 20% from the previous 12 days");
  });

  it("names the channels and how long ago a customer wrote", () => {
    expect(channelsLine(["instagram", "whatsapp"])).toBe("Overview across Instagram & WhatsApp");
    expect(channelsLine(["instagram"])).toBe("Overview across Instagram");
    expect(channelsLine([])).toBe("No channels connected yet");
    expect(channelsConnected(2)).toBe("2 channels connected");
    expect(channelsConnected(1)).toBe("1 channel connected");
    expect(channelsConnected(0)).toBe("No channels connected");
    expect(agoLabel("now")).toBe("just now");
    expect(agoLabel("12m")).toBe("12m ago");
    expect(agoLabel("3d")).toBe("3d ago");
    expect(agoLabel("28 Sep")).toBe("28 Sep");
  });
});
