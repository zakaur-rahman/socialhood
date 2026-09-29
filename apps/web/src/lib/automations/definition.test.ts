import { describe, expect, it } from "vitest";

import { automation } from "@/test/api";

import {
  buttonProblems,
  clearFieldErrors,
  DEFAULT_OPENING_BUTTON,
  DEFAULT_OPENING_TEXT,
  fieldErrors,
  firstIncompleteStep,
  followNudgeProblem,
  isHttpsUrl,
  openingProblems,
  stepComplete,
  stepOfField,
  stepsWithErrors,
  tapFirstOn,
  toDefinition,
  toRequestBody,
  triggerPatch,
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

  it("sends tap first for comment triggers and the follow nudge for both (FR-AUT-21, FR-AUT-22)", () => {
    const draft = toDefinition(
      automation({
        confirm_first: true,
        opening_text: "Hi {first_name|there}! Tap below 👇",
        opening_button: "  Send me the link ",
        follow_nudge: true,
        follow_nudge_text: "Enjoying this? Follow us.",
      }),
    );
    expect(toRequestBody(draft)).toMatchObject({
      confirm_first: true,
      opening_text: "Hi {first_name|there}! Tap below 👇",
      opening_button: "Send me the link",
      follow_nudge: true,
      follow_nudge_text: "Enjoying this? Follow us.",
    });
    // A DM already opens the conversation: no tap first, but the nudge stays.
    expect(toRequestBody({ ...draft, trigger: "dm_keyword" })).toMatchObject({
      confirm_first: false,
      opening_text: null,
      opening_button: null,
      follow_nudge: true,
      follow_nudge_text: "Enjoying this? Follow us.",
    });
  });

  it("turns tap first and the nudge off for Reply with AI, and keeps the API's defaults before an action", () => {
    const draft = toDefinition(
      automation({ confirm_first: true, opening_text: "Tap below", opening_button: "Send it", follow_nudge: true }),
    );
    expect(toRequestBody({ ...draft, action: "ai_reply" })).toMatchObject({ confirm_first: false, follow_nudge: false });
    expect(toRequestBody({ ...draft, action: null })).toMatchObject({ confirm_first: true, follow_nudge: true });
  });

  it("sends empty opening and nudge fields as null", () => {
    const draft = { ...toDefinition(automation()), opening_text: "", opening_button: "  ", follow_nudge_text: "" };
    expect(toRequestBody(draft)).toMatchObject({ opening_text: null, opening_button: null, follow_nudge_text: null });
  });
});

describe("tap first defaults (FR-AUT-21)", () => {
  it("fills the default opening and button when switched on, keeping what was typed", () => {
    expect(tapFirstOn({ opening_text: null, opening_button: "" })).toEqual({
      confirm_first: true,
      opening_text: DEFAULT_OPENING_TEXT,
      opening_button: DEFAULT_OPENING_BUTTON,
    });
    expect(tapFirstOn({ opening_text: "Tap below", opening_button: "Go" })).toEqual({
      confirm_first: true,
      opening_text: "Tap below",
      opening_button: "Go",
    });
  });

  it("turns it on when an automation becomes a comment automation for the first time", () => {
    const dm = toDefinition(automation({ trigger: "dm_keyword" }));
    expect(triggerPatch(dm, "comment_keyword")).toEqual({
      trigger: "comment_keyword",
      confirm_first: true,
      opening_text: DEFAULT_OPENING_TEXT,
      opening_button: DEFAULT_OPENING_BUTTON,
    });
    expect(triggerPatch({ ...dm, trigger: null }, "comment_any")).toMatchObject({
      post_scope: "selected",
      confirm_first: true,
    });
    // Already a comment automation, or one that had an opening: left as it is.
    expect(triggerPatch(toDefinition(automation()), "comment_any")).toEqual({
      trigger: "comment_any",
      post_scope: "selected",
    });
    expect(triggerPatch({ ...dm, opening_text: "Tap below" }, "comment_keyword")).toEqual({ trigger: "comment_keyword" });
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

  it("needs tap first's opening and button, and allows an image only with tap first on a comment", () => {
    const def = toDefinition(
      automation({ confirm_first: true, opening_text: DEFAULT_OPENING_TEXT, opening_button: DEFAULT_OPENING_BUTTON }),
    );
    expect(stepComplete("then", def)).toBe(true);
    expect(stepComplete("then", { ...def, opening_text: " " })).toBe(false);
    expect(stepComplete("then", { ...def, opening_button: "" })).toBe(false);
    expect(stepComplete("then", { ...def, opening_text: "x".repeat(1001) })).toBe(false);
    // The disclosure line counts toward the opening's 1,000 bytes.
    expect(stepComplete("then", { ...def, opening_text: "x".repeat(990) })).toBe(true);
    expect(stepComplete("then", { ...def, opening_text: "x".repeat(990) }, "Sent automatically")).toBe(false);
    // C-030: a private reply carries no image; tap first's message is a normal DM, which can.
    expect(stepComplete("then", { ...def, message_media_asset_id: "ma1" })).toBe(true);
    expect(stepComplete("then", { ...def, confirm_first: false, message_media_asset_id: "ma1" })).toBe(false);
    expect(stepComplete("then", { ...def, confirm_first: false, opening_text: null })).toBe(true);
    expect(stepComplete("then", { ...def, trigger: "dm_keyword", confirm_first: false, message_media_asset_id: "ma1" })).toBe(
      true,
    );
  });

  it("needs the follow nudge's text when it is on", () => {
    const def = toDefinition(automation({ follow_nudge: true, follow_nudge_text: "Follow us for more." }));
    expect(stepComplete("then", def)).toBe(true);
    expect(stepComplete("then", { ...def, follow_nudge_text: "" })).toBe(false);
    expect(stepComplete("then", { ...def, follow_nudge: false, follow_nudge_text: "" })).toBe(true);
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

describe("opening and nudge checks (FR-AUT-21, FR-AUT-22)", () => {
  it("names the opening's problems", () => {
    expect(openingProblems({ opening_text: "", opening_button: "" })).toEqual({
      text: "Write the opening message.",
      button: "Add a button title.",
    });
    expect(openingProblems({ opening_text: "x".repeat(1001), opening_button: "a".repeat(21) })).toEqual({
      text: "Instagram allows 1,000 bytes in a DM, counting the longest name. Shorten the opening.",
      button: "Use 20 characters or fewer.",
    });
    expect(openingProblems({ opening_text: DEFAULT_OPENING_TEXT, opening_button: DEFAULT_OPENING_BUTTON })).toEqual({});
  });

  it("names the nudge's problems, counting characters as the API does", () => {
    expect(followNudgeProblem(null)).toBe("Write the follow message.");
    expect(followNudgeProblem("💛".repeat(300))).toBeNull();
    expect(followNudgeProblem("a".repeat(301))).toBe("Use 300 characters or fewer.");
  });
});

describe("API field errors → steps", () => {
  it("maps tap first's and the nudge's fields to Then", () => {
    for (const field of ["confirm_first", "opening_text", "opening_button", "follow_nudge", "follow_nudge_text"]) {
      expect(stepOfField(field)).toBe("then");
    }
  });

  it("clears the problems a switch settles", () => {
    const errors = {
      opening_text: "Write the opening message.",
      opening_button: "Add a button title.",
      message_media_asset_id: "Replies to comments can't carry an image.",
      follow_nudge_text: "Write the follow message.",
    };
    expect(clearFieldErrors(errors, ["confirm_first"])).toEqual({ follow_nudge_text: "Write the follow message." });
    expect(clearFieldErrors(errors, ["follow_nudge"])).toEqual({
      opening_text: "Write the opening message.",
      opening_button: "Add a button title.",
      message_media_asset_id: "Replies to comments can't carry an image.",
    });
  });

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
