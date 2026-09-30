import { describe, expect, it } from "vitest";

import type { SourceSheetMode } from "@/components/knowledge/SourceSheet";

import { faqPrefill, gapPrefill } from "./prefill";

describe("Add to knowledge, prefilled (C-065)", () => {
  it("is an FAQ create for the knowledge sheet, answering the gap", () => {
    const mode: SourceSheetMode = gapPrefill({ id: "g1", question: " Any eggless cakes? ", topic: "eggless options" });
    expect(mode).toEqual({ kind: "create", type: "faq", question: "Any eggless cakes?", gapId: "g1" });
  });

  it("falls back to the topic, and needs no gap", () => {
    expect(gapPrefill({ id: "g1", question: "  ", topic: "eggless options" }).question).toBe("eggless options");
    expect(faqPrefill("Do you deliver on Sundays?")).toEqual({
      kind: "create",
      type: "faq",
      question: "Do you deliver on Sundays?",
    });
  });
});
