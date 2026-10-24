import { describe, expect, it } from "vitest";

import type { Sequence } from "@/lib/api/types";

import {
  blankState,
  blankStep,
  dayOf,
  describeWait,
  formatDelay,
  fromSequence,
  missingFor,
  splitDelay,
  toBody,
  toSeconds,
} from "./format";

describe("delays", () => {
  it("are shown in the largest unit that divides them evenly", () => {
    expect(splitDelay(86_400)).toEqual({ amount: 1, unit: "days" });
    expect(splitDelay(3 * 86_400)).toEqual({ amount: 3, unit: "days" });
    expect(splitDelay(7_200)).toEqual({ amount: 2, unit: "hours" });
    expect(splitDelay(90 * 60)).toEqual({ amount: 90, unit: "minutes" });
    expect(splitDelay(0)).toEqual({ amount: 0, unit: "minutes" });
  });

  it("are read back to seconds, kept within 30 days", () => {
    expect(toSeconds(2, "days")).toBe(172_800);
    expect(toSeconds(5, "minutes")).toBe(300);
    expect(toSeconds(-4, "hours")).toBe(0);
    expect(toSeconds(90, "days")).toBe(30 * 86_400);
  });

  it("are written in words", () => {
    expect(formatDelay(86_400)).toBe("1 day");
    expect(formatDelay(2 * 86_400)).toBe("2 days");
    expect(formatDelay(3_600)).toBe("1 hour");
    expect(describeWait(0, "entry", 0)).toBe("Right away");
    expect(describeWait(86_400, "previous", 0)).toBe("1 day after they entered");
    expect(describeWait(86_400, "previous", 2)).toBe("1 day after the step before");
    expect(describeWait(3 * 86_400, "entry", 1)).toBe("3 days after they entered");
  });

  it("name the day a preview step falls on", () => {
    expect(dayOf(600)).toBe("10 min");
    expect(dayOf(7_200)).toBe("2 h");
    expect(dayOf(86_400)).toBe("Day 1");
    expect(dayOf(3 * 86_400 + 5)).toBe("Day 3");
  });
});

describe("the editor's state", () => {
  const ready = () => ({
    ...blankState("a1"),
    name: "Three days",
    tagId: "t1",
    steps: [
      blankStep({
        amount: 1,
        unit: "days",
        from: "entry",
        text: "Hi {first_name}",
        templateKey: "sale|en",
        variables: [{ source: "field" as const, field: "first_name", value: "", fallback: " there " }],
      }),
      blankStep({
        amount: 3,
        unit: "days",
        from: "entry",
        templateKey: "sale|en",
        variables: [{ source: "fixed" as const, field: "", value: "31 October", fallback: "" }],
      }),
    ],
  });

  it("says what is missing, step by step", () => {
    const state = blankState();
    expect(missingFor(state)).toEqual([
      "Give the sequence a name.",
      "Choose the account it sends from.",
      "Choose the tag that starts it.",
      "Step 1 needs a message or a template.",
    ]);
    expect(toBody(state)).toBeNull();
    expect(missingFor(ready())).toEqual([]);
  });

  it("becomes the body the API takes", () => {
    const body = toBody(ready());
    expect(body).toEqual({
      name: "Three days",
      social_account_id: "a1",
      entry: { type: "tagged", tag_id: "t1", broadcast_id: null, capture_kind: null },
      stop: { on_reply: true, tag_ids: [], stages: [] },
      allow_reentry: false,
      steps: [
        {
          delay_seconds: 86_400,
          delay_from: "entry",
          text: "Hi {first_name}",
          template_name: "sale",
          template_language: "en",
          variables: [{ source: "field", field: "first_name", fallback: "there" }],
          respect_hours: false,
        },
        {
          delay_seconds: 259_200,
          delay_from: "entry",
          text: null,
          template_name: "sale",
          template_language: "en",
          variables: [{ source: "fixed", value: "31 October" }],
          respect_hours: false,
        },
      ],
    });
  });

  it("counts the first step from entry whatever the editor held, and drops variables without a template", () => {
    const state = ready();
    state.steps[0] = { ...state.steps[0], from: "previous", templateKey: null };
    const body = toBody(state);
    expect(body?.steps[0].delay_from).toBe("entry");
    expect(body?.steps[0].variables).toEqual([]);
    expect(body?.steps[0].template_name).toBeNull();
  });

  it("reads a saved sequence back into the editor", () => {
    const saved = {
      id: "s1",
      name: "After the sale",
      status: "paused",
      social_account_id: "a1",
      entry: { type: "captured", capture_kind: "email", label: "A lead is captured: an email" },
      stop: { on_reply: false, tag_ids: ["t9"], tag_names: ["Bought"], stages: ["won"] },
      allow_reentry: true,
      step_count: 1,
      steps: [
        {
          position: 0,
          delay_seconds: 7_200,
          delay_from: "entry",
          text: "Hello",
          template_name: null,
          template_language: null,
          variables: [],
          respect_hours: true,
        },
      ],
      enrolments: { active: 0, completed: 0, stopped: 0 },
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:00Z",
      problems: [],
    } as unknown as Sequence;
    const state = fromSequence(saved);
    expect(state).toMatchObject({
      name: "After the sale",
      entryType: "captured",
      captureKind: "email",
      stopOnReply: false,
      stopTagIds: ["t9"],
      stopStages: ["won"],
      allowReentry: true,
    });
    expect(state.steps[0]).toMatchObject({ amount: 2, unit: "hours", text: "Hello", respectHours: true, templateKey: null });
  });
});
