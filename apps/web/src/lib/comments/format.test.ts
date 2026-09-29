import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { comment } from "@/test/api";

import {
  analysingText,
  byteLength,
  commentActionError,
  COMMENT_FILTERS,
  filterEmpty,
  formatPlural,
  isAnalysing,
  matchesFilter,
  mediaTypeLabel,
  SECOND_PRIVATE_REPLY,
  sentimentLabel,
} from "./format";

function problem(status: number, code: string, detail?: string) {
  return new ApiError({ type: "about:blank", title: code, status, code, detail });
}

describe("filter chips (UX-SCR-05; CommentFilter in schemas/posts.py)", () => {
  it("lists the eight chips in the spec's order", () => {
    expect(COMMENT_FILTERS.map((f) => f.label)).toEqual([
      "All",
      "Positive",
      "Neutral",
      "Negative",
      "Questions",
      "Buying signals",
      "Spam",
      "Hidden",
    ]);
  });

  it("matches as the API filters", () => {
    const positiveQuestion = comment();
    const buying = comment({
      analysis: { sentiment: "neutral", sentiment_score: 0, intent: "purchase", is_spam: false, topic: null },
    });
    const pricing = comment({
      analysis: { sentiment: "neutral", sentiment_score: 0, intent: "pricing", is_spam: false, topic: null },
    });
    const spam = comment({
      analysis: { sentiment: "positive", sentiment_score: 0.2, intent: "pricing", is_spam: true, topic: null },
    });
    const hidden = comment({ hidden: true, analysis: null, analysis_status: "pending" });
    const deleted = comment({ deleted_at: "2026-09-28T12:00:00Z" });

    expect(matchesFilter(positiveQuestion, "positive")).toBe(true);
    expect(matchesFilter(positiveQuestion, "questions")).toBe(true);
    expect(matchesFilter(positiveQuestion, "buying")).toBe(false);
    expect(matchesFilter(buying, "buying")).toBe(true);
    expect(matchesFilter(buying, "questions")).toBe(false);
    // pricing is both a question and a buying signal
    expect(matchesFilter(pricing, "questions")).toBe(true);
    expect(matchesFilter(pricing, "buying")).toBe(true);
    // spam leaves the sentiment and intent filters
    expect(matchesFilter(spam, "positive")).toBe(false);
    expect(matchesFilter(spam, "buying")).toBe(false);
    expect(matchesFilter(spam, "spam")).toBe(true);
    // not analysed yet: only All and (here) Hidden
    expect(matchesFilter(hidden, "all")).toBe(true);
    expect(matchesFilter(hidden, "hidden")).toBe(true);
    expect(matchesFilter(hidden, "neutral")).toBe(false);
    // deleted comments leave every list
    expect(COMMENT_FILTERS.some((f) => matchesFilter(deleted, f.value))).toBe(false);
  });

  it("empty states name the filter and mention analysis in progress", () => {
    expect(filterEmpty("all", false).title).toBe("No comments yet");
    expect(filterEmpty("buying", false)).toEqual({
      title: "No buying signals",
      body: "Nothing matches this filter right now.",
    });
    expect(filterEmpty("negative", true).body).toMatch(/still being analysed/);
    expect(filterEmpty("hidden", true).body).toBe("Nothing matches this filter right now.");
  });
});

describe("posts", () => {
  it("names formats and compares Reels with Reels", () => {
    expect(mediaTypeLabel("reel")).toBe("Reel");
    expect(mediaTypeLabel("carousel")).toBe("Carousel");
    expect(mediaTypeLabel("image")).toBe("Photo");
    expect(formatPlural("reel")).toBe("Reels");
    expect(formatPlural("image")).toBe("feed posts");
  });

  it("FR-CMT-02 progress", () => {
    expect(isAnalysing({ analysed: 12_400, total: 58_000 })).toBe(true);
    expect(isAnalysing({ analysed: 3, total: 3 })).toBe(false);
    expect(analysingText({ analysed: 12_400, total: 58_000 })).toBe("Analysing 12,400 of 58,000 comments");
  });

  it("describes the sentiment bar in words", () => {
    expect(sentimentLabel({ positive: 7, neutral: 3, negative: 1 })).toBe("Sentiment: 7 positive, 3 neutral, 1 negative");
    expect(sentimentLabel({ positive: 0, neutral: 0, negative: 0 })).toBe("No analysed comments yet");
  });
});

describe("replies", () => {
  it("counts private replies in bytes, as Instagram does", () => {
    expect(byteLength("hi")).toBe(2);
    expect(byteLength("😍")).toBe(4);
  });

  it("a second private reply (409) is refused with a clear message", () => {
    expect(commentActionError(problem(409, "conflict", "Already replied"), "dm")).toBe(SECOND_PRIVATE_REPLY);
    // a conflict on another action shows the API's reason
    expect(commentActionError(problem(409, "conflict", "The comment was deleted on Instagram."), "hide")).toBe(
      "The comment was deleted on Instagram.",
    );
  });

  it("platform errors read as in the inbox (§4.7)", () => {
    expect(commentActionError(problem(409, "account_needs_reconnect"), "reply", "maple.bakery")).toBe(
      "@maple.bakery needs reconnecting before you can send from it.",
    );
    expect(commentActionError(problem(503, "platform_unavailable"), "delete")).toBe("Instagram didn't respond.");
    expect(commentActionError(new TypeError("Failed to fetch"), "reply")).toBe(
      "You're offline. Reconnect to send messages.",
    );
  });
});
