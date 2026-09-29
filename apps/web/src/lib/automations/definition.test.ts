import { describe, expect, it } from "vitest";

import { automation } from "@/test/api";

import {
  buttonProblems,
  clearFieldErrors,
  fieldErrors,
  firstIncompleteStep,
  isHttpsUrl,
  stepComplete,
  stepOfField,
  stepsWithErrors,
  toDefinition,
  toRequestBody,
  visibleSteps,
} from "./definition";

describe("toDefinition", () => {
  it("splits posts into synced and scheduled ids", () => {
    const def = toDefinition(
      automation({
        post_scope: "selected",
        posts: [{ media_item_id: "m1" }, { scheduled_post_id: "s1" }, { media_item_id: "m2", scheduled_post_id: "s2" }],
      }),
    );
    expect(def.media_item_ids).toEqual(["m1", "m2"]);
    expect(def.scheduled_post_ids).toEqual(["s1"]);
  });
});

describe("toRequestBody", () => {
  it("sends only what the trigger uses and leaves out unfinished rows", () => {
    const draft = {
      ...toDefinition(automation()),
      trigger: "dm_keyword" as const,
      name: "  ",
      public_reply_texts: ["Sent!", " "],
      message_buttons: [
        { title: "Shop", url: "https://maple.example" },
        { title: "Half", url: "" },
      ],
      post_scope: "selected" as const,
      media_item_ids: ["m1"],
    };
    const body = toRequestBody(draft);
    expect(body.name).toBe("Untitled automation");
    expect(body.public_reply_texts).toEqual([]);
    expect(body.post_scope).toBe("all");
    expect(body.media_item_ids).toEqual([]);
    expect(body.message_buttons).toEqual([{ title: "Shop", url: "https://maple.example" }]);
  });

  it("sends no keywords for Any comment", () => {
    const body = toRequestBody({ ...toDefinition(automation()), trigger: "comment_any" });
    expect(body.keywords).toEqual([]);
  });
});

describe("steps and completeness (FR-AUT-02)", () => {
  it("shows the steps each trigger uses", () => {
    expect(visibleSteps("dm_keyword")).toEqual(["when", "keywords", "then", "settings"]);
    expect(visibleSteps("comment_keyword")).toEqual(["when", "posts", "keywords", "then", "settings"]);
    expect(visibleSteps("comment_any")).toEqual(["when", "posts", "then", "settings"]);
  });

  it("marks steps complete from the draft", () => {
    const def = toDefinition(automation());
    expect(visibleSteps(def.trigger).every((step) => stepComplete(step, def))).toBe(true);
    expect(stepComplete("keywords", { ...def, keywords: [] })).toBe(false);
    expect(stepComplete("when", { ...def, social_account_id: null })).toBe(false);
    expect(stepComplete("posts", { ...def, trigger: "comment_any", post_scope: "all" })).toBe(false);
    expect(stepComplete("posts", { ...def, post_scope: "selected", media_item_ids: [] })).toBe(false);
    expect(stepComplete("then", { ...def, message_text: "", message_media_asset_id: null })).toBe(false);
    expect(stepComplete("then", { ...def, message_buttons: [{ title: "Go", url: "http://x.com" }] })).toBe(false);
    expect(stepComplete("then", { ...def, message_text: "x".repeat(1001) })).toBe(false);
    expect(stepComplete("then", { ...def, action: "ai_reply", ai_instructions: "Be brief" })).toBe(true);
    expect(stepComplete("settings", { ...def, starts_at: "2026-10-02T00:00:00Z", ends_at: "2026-10-01T00:00:00Z" })).toBe(
      false,
    );
  });

  it("finds the first incomplete step", () => {
    const def = toDefinition(automation({ keywords: [], message_text: null, message_buttons: [] }));
    expect(firstIncompleteStep(def)).toBe("keywords");
    expect(firstIncompleteStep(toDefinition(automation()))).toBeNull();
  });
});

describe("link buttons (FR-AUT-13)", () => {
  it("accepts only full https links", () => {
    expect(isHttpsUrl("https://maple.example/shop")).toBe(true);
    expect(isHttpsUrl("http://maple.example")).toBe(false);
    expect(isHttpsUrl("maple.example")).toBe(false);
    expect(isHttpsUrl("https://localhost")).toBe(false);
  });

  it("names each problem", () => {
    expect(buttonProblems({ title: "", url: "ftp://x" })).toEqual({
      title: "Add a button title.",
      url: "Use a full link that starts with https://",
    });
    expect(buttonProblems({ title: "Shop", url: "https://maple.example" })).toEqual({});
  });
});

describe("API field errors → steps", () => {
  it("maps nested fields to their step", () => {
    expect(stepOfField("message_buttons.0.url")).toBe("then");
    expect(stepOfField("keywords")).toBe("keywords");
    expect(stepOfField("media_item_ids")).toBe("posts");
    expect(stepOfField("social_account_id")).toBe("when");
    expect(stepOfField("cooldown_hours")).toBe("settings");
    expect(stepOfField("something_else")).toBeNull();
  });

  it("keeps the first message per field and clears fields the user edits", () => {
    const errors = fieldErrors([
      { field: "keywords", message: "Add at least one keyword." },
      { field: "keywords", message: "Second" },
      { field: "message_buttons.0.url", message: "Use https." },
    ]);
    expect(errors).toEqual({ keywords: "Add at least one keyword.", "message_buttons.0.url": "Use https." });
    expect([...stepsWithErrors(errors)].sort()).toEqual(["keywords", "then"]);
    expect(clearFieldErrors(errors, ["message_buttons"])).toEqual({ keywords: "Add at least one keyword." });
  });
});
