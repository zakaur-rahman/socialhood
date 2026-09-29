import { describe, expect, it } from "vitest";

import { comparison, performance } from "@/test/api";

import {
  AGES,
  atAge,
  baselineText,
  diffTone,
  diffWords,
  formatDiff,
  formatMetric,
  notEnoughHistory,
  youngerNote,
} from "./format";

describe("figures are the API's, only formatted (FR-ANL-02)", () => {
  it("offers every snapshot window and lifetime", () => {
    expect(AGES).toEqual(["1h", "6h", "24h", "72h", "7d", "30d", "lifetime"]);
    expect(atAge("24h")).toBe("at 24 h");
    expect(atAge("7d")).toBe("at 7 d");
    expect(atAge("lifetime")).toBe("lifetime");
  });

  it("formats counts and the engagement rate, and never shows an unknown as 0", () => {
    expect(formatMetric("reach", 12_400)).toBe("12,400");
    expect(formatMetric("engagement_rate", 6.1)).toBe("6.1%");
    expect(formatMetric("reach", 1050.5)).toBe("1,050.5");
    expect(formatMetric("saves", 0)).toBe("0");
    expect(formatMetric("views", null)).toBe("—");
    expect(formatMetric("views", undefined)).toBe("—");
  });

  it("formats the API's difference with its sign, and says it in words", () => {
    expect(formatDiff(18.12)).toBe("+18.1%");
    expect(formatDiff(-7)).toBe("−7%");
    expect(formatDiff(0.01)).toBe("0%");
    expect(formatDiff(null)).toBe("—");
    expect(diffTone(18)).toBe("up");
    expect(diffTone(-3)).toBe("down");
    expect(diffTone(0)).toBe("flat");
    expect(diffTone(null)).toBe("none");
    expect(diffWords(18.12)).toBe("18.1% above the median");
    expect(diffWords(-7)).toBe("7% below the median");
    expect(diffWords(null)).toBe("no median to compare with");
  });
});

describe("the age used is always stated (agent-architecture §6)", () => {
  it("says when a younger post is shown at the age it has reached", () => {
    expect(youngerNote(performance({ requested_age: "7d", age: "24h" }), "figures")).toBe(
      "This post hasn't reached 7 d yet, so these are its figures at 24 h.",
    );
    expect(youngerNote(performance({ requested_age: "7d", age: "24h" }), "comparison")).toBe(
      "This post hasn't reached 7 d yet, so it's compared at 24 h.",
    );
    expect(youngerNote(performance({ requested_age: "24h", age: "24h" }), "figures")).toBeNull();
    expect(youngerNote(performance({ requested_age: null, age: "6h" }), "figures")).toBeNull();
  });

  it("states the baseline size and format", () => {
    expect(baselineText(comparison())).toBe("Compared with 8 earlier feed posts (of the last 10) at 24 h");
    expect(
      baselineText(
        comparison({
          post: performance({ media_type: "reel" }),
          baseline_size: 1,
          age: "lifetime",
          baseline: { kind: "range", since: "2026-09-01", until: "2026-09-28", same_format: true, post_ids: [] },
        }),
      ),
    ).toBe("Compared with 1 earlier Reel, on lifetime figures");
  });

  it("explains not enough history with the size found", () => {
    expect(notEnoughHistory(comparison({ baseline_size: 2, enough_history: false }))).toBe(
      "Only 2 earlier feed posts have figures at 24 h. Comparisons need at least 3.",
    );
    expect(notEnoughHistory(comparison({ baseline_size: 1, enough_history: false }))).toBe(
      "Only 1 earlier feed post has figures at 24 h. Comparisons need at least 3.",
    );
    expect(notEnoughHistory(comparison({ baseline_size: 0, enough_history: false }))).toBe(
      "No earlier feed posts have figures at 24 h yet. Comparisons need at least 3.",
    );
  });
});
