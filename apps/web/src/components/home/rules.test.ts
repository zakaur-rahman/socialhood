import { describe, expect, it } from "vitest";

import { isFast, needsAttention, queueState } from "./rules";

const now = new Date("2026-10-01T12:00:00Z");
const ago = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();

describe("Home's labels (C-065)", () => {
  it("Attention: someone needs a reply and has waited more than an hour", () => {
    expect(needsAttention(3, ago(61), now)).toBe(true);
    expect(needsAttention(3, ago(60), now)).toBe(false);
    expect(needsAttention(3, ago(5), now)).toBe(false);
    expect(needsAttention(0, ago(600), now)).toBe(false);
    expect(needsAttention(3, null, now)).toBe(false);
  });

  it("Fast: a median first response under 5 minutes", () => {
    expect(isFast(54)).toBe(true);
    expect(isFast(299)).toBe(true);
    expect(isFast(300)).toBe(false);
    expect(isFast(null)).toBe(false);
    expect(isFast(undefined)).toBe(false);
  });

  it("a queue row: needs you first, then a draft to review, else a reply to write", () => {
    expect(queueState({ needs_you: false, has_pending_suggestion: true })).toEqual({
      chip: { label: "AI draft ready", tone: "brand" },
      action: "Review & Send",
    });
    expect(queueState({ needs_you: false, has_pending_suggestion: false })).toEqual({
      chip: { label: "Needs reply", tone: "warning" },
      action: "Open chat",
    });
    expect(queueState({ needs_you: true, has_pending_suggestion: false })).toEqual({
      chip: { label: "Needs you", tone: "danger" },
      action: "Open chat",
    });
    expect(queueState({ needs_you: true, has_pending_suggestion: true }).action).toBe("Review & Send");
  });
});
