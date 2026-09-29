import { describe, expect, it } from "vitest";

import { aiCreditsExhausted, knowledgeLimitReached, shortDate } from "@/lib/copy";

import { checkLabel, checkValue, escalationBanner, sourceChips, takeoverText } from "./format";

describe("AI presentation rules", () => {
  it("escalation banners say why the AI didn't reply (UX-INB-08)", () => {
    expect(escalationBanner("refund")).toBe("AI didn't reply: customer is asking for a refund");
    expect(escalationBanner("out_of_knowledge")).toBe("AI didn't reply: the answer isn't in your knowledge");
  });

  it("decision checks: TR-AI-07's labels by number, confidence as a percentage", () => {
    expect(checkLabel({ n: 10, name: "confidence", passed: true, value: 0.82 })).toBe("AI is confident");
    expect(checkLabel({ n: 42, name: "new_check", passed: true })).toBe("new check");
    expect(checkValue({ n: 10, name: "confidence", passed: true, value: 0.82 })).toBe("82%");
    expect(checkValue({ n: 12, name: "rate", passed: true, value: 3 })).toBe("3");
    expect(checkValue({ n: 5, name: "window", passed: true, value: "open" })).toBe("open");
    expect(checkValue({ n: 9, name: "can_answer", passed: true, value: true })).toBeNull();
  });

  it("source chips: at most two, then +n", () => {
    const sources = [1, 2, 3, 4].map((i) => ({ id: `k${i}`, title: `S${i}` }));
    expect(sourceChips(sources)).toEqual({ shown: sources.slice(0, 2), more: 2 });
    expect(sourceChips(sources.slice(0, 1))).toEqual({ shown: sources.slice(0, 1), more: 0 });
  });

  it("takeover periods in words", () => {
    expect(takeoverText(30)).toBe("for 30 minutes");
    expect(takeoverText(120)).toBe("for 2 hours");
    expect(takeoverText(1440)).toBe("for 24 hours");
    expect(takeoverText(0)).toBe("until you resume it");
  });
});

describe("limits copy (§4.7 quota_exceeded)", () => {
  const now = new Date(2026, 8, 28);

  it("AI credits: the limit and the reset date", () => {
    expect(aiCreditsExhausted(5000, "2026-10-01", now)).toBe(
      "You've used all 5,000 AI credits for this month. They reset on 1 Oct.",
    );
    expect(aiCreditsExhausted(200, null, now)).toBe("You've used all 200 AI credits for this month.");
  });

  it("dates: the year only when it isn't this one", () => {
    expect(shortDate("2026-10-01", now)).toBe("1 Oct");
    expect(shortDate("2027-01-01", now)).toBe("1 Jan 2027");
  });

  it("knowledge: the plan's characters", () => {
    expect(knowledgeLimitReached(200_000)).toBe("Your plan includes 200,000 characters of knowledge.");
    expect(knowledgeLimitReached(null)).toBe("Your plan's knowledge limit is reached.");
  });
});
