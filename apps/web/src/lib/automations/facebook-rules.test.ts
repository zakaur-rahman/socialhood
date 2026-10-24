import { describe, expect, it } from "vitest";

import { account, automation } from "@/test/api";

import { accountLabel, automationAccounts, instagramAccounts } from "./accounts";
import { openingProblems, stepComplete, toDefinition } from "./definition";
import { FACEBOOK_FLOW_COPY, stepProblems, type AskNode, type BranchNode, type FlowContext, type SendNode } from "./flow";
import { triggerLabel } from "./format";
import { FACEBOOK_MESSAGE_CHARS, messageLimit, messageSize, networkName, overLimitCopy } from "./limits";

const CTX: FlowContext = { disclosure: null, fields: [], tagIds: new Set() };
const PAGE: FlowContext = { ...CTX, platform: "facebook" };

function send(text = "Hi", extra: Partial<SendNode> = {}): SendNode {
  return { kind: "send", id: "s", text, image_asset_id: null, buttons: [], replies: [], typed: { mode: "none" }, ...extra };
}

function ask(extra: Partial<AskNode> = {}): AskNode {
  return {
    kind: "ask",
    id: "q",
    text: "Your email?",
    expect: "email",
    field_key: null,
    retry_text: "",
    tries: 2,
    consent: false,
    consent_text: "",
    confirm_text: "",
    skip: [],
    ...extra,
  };
}

describe("message limits by platform (GR-29)", () => {
  it("Instagram counts bytes, a Page counts characters", () => {
    expect(messageLimit("instagram")).toEqual({ limit: 1000, unit: "bytes" });
    expect(messageLimit(undefined)).toEqual({ limit: 1000, unit: "bytes" });
    expect(messageLimit("facebook")).toEqual({ limit: FACEBOOK_MESSAGE_CHARS, unit: "characters" });
    expect(FACEBOOK_MESSAGE_CHARS).toBe(2000);
    const emoji = "😀".repeat(300); // 1,200 bytes, 300 characters
    expect(messageSize(emoji, null, "instagram")).toBeGreaterThan(1000);
    expect(messageSize(emoji, null, "facebook")).toBeLessThan(2000);
  });

  it("says the same words as the API for each platform", () => {
    expect(overLimitCopy("instagram", "it")).toBe("Instagram allows 1,000 bytes in a DM, counting the longest name. Shorten it.");
    expect(overLimitCopy(undefined, "the opening")).toBe(
      "Instagram allows 1,000 bytes in a DM, counting the longest name. Shorten the opening.",
    );
    expect(overLimitCopy("facebook", "it")).toBe(
      "Facebook allows 2,000 characters in a message, counting the longest name. Shorten it.",
    );
    expect(overLimitCopy("facebook", "it", false)).toBe("Facebook allows 2,000 characters in a message. Shorten it.");
    expect(networkName("facebook")).toBe("Facebook");
    expect(networkName(null)).toBe("Instagram");
  });
});

describe("a flow on a Facebook Page", () => {
  it("allows a message past Instagram's 1,000 bytes, up to 2,000 characters", () => {
    const text = "x".repeat(1500);
    expect(stepProblems(send(text), CTX).text).toMatch(/^Instagram allows 1,000 bytes/);
    expect(stepProblems(send(text), PAGE)).toEqual({});
    expect(stepProblems(send("x".repeat(2001)), PAGE).text).toBe(
      "Facebook allows 2,000 characters in a message, counting the longest name. Shorten it.",
    );
  });

  it("keeps the 640-character limit with link buttons, naming Facebook", () => {
    const node = send("x".repeat(641), { buttons: [{ title: "Shop", url: "https://maple.example", profile: false }] });
    expect(stepProblems(node, PAGE).text).toBe(
      "With link buttons Facebook allows 640 characters, counting the longest name. Shorten it.",
    );
  });

  it("refuses the profile button, which opens an Instagram profile", () => {
    const node = send("Hi", { buttons: [{ title: "View profile", url: null, profile: true }] });
    expect(stepProblems(node, CTX)).toEqual({});
    expect(stepProblems(node, PAGE)).toEqual({ "buttons.0": FACEBOOK_FLOW_COPY.profileButton });
  });

  it("refuses a consent question", () => {
    const node = ask({ consent: true });
    expect(stepProblems(node, CTX)).toEqual({});
    expect(stepProblems(node, PAGE)).toEqual({ consent: FACEBOOK_FLOW_COPY.consent });
    expect(stepProblems(ask(), PAGE)).toEqual({});
  });

  it("refuses a branch on following the Page", () => {
    const node: BranchNode = {
      kind: "branch",
      id: "b",
      rules: [{ when: { kind: "follows_business", follows: false }, steps: [] }],
      otherwise: [],
    };
    expect(stepProblems(node, CTX)).toEqual({});
    expect(stepProblems(node, PAGE)).toEqual({ "rules.0.when": FACEBOOK_FLOW_COPY.follows });
  });

  it("says what the API says", () => {
    expect(FACEBOOK_FLOW_COPY.follows).toBe(
      "Messenger doesn't say whether someone follows your Page. Remove this branch or use another condition.",
    );
    expect(FACEBOOK_FLOW_COPY.profileButton).toBe("The profile button opens an Instagram profile. Give this button a link instead.");
    expect(FACEBOOK_FLOW_COPY.consent).toBe("Facebook doesn't record marketing consent yet. Turn off the consent question.");
  });
});

describe("an automation's message settings on a Facebook Page", () => {
  const draft = () => toDefinition(automation({ trigger: "dm_keyword", public_reply_texts: [], message_buttons: [] }));

  it("the Then step accepts 1,500 characters on a Page but not on Instagram", () => {
    const long = { ...draft(), message_text: "y".repeat(1500) };
    expect(stepComplete("then", long, null, "instagram")).toBe(false);
    expect(stepComplete("then", long, null, "facebook")).toBe(true);
    expect(stepComplete("then", { ...long, message_text: "y".repeat(2001) }, null, "facebook")).toBe(false);
  });

  it("the follow line can't be on", () => {
    const nudging = { ...draft(), follow_nudge: true, follow_nudge_text: "Follow us" };
    expect(stepComplete("then", nudging, null, "instagram")).toBe(true);
    expect(stepComplete("then", nudging, null, "facebook")).toBe(false);
    expect(stepComplete("then", { ...nudging, follow_nudge: false }, null, "facebook")).toBe(true);
  });

  it("tap first's opening is counted in the platform's unit", () => {
    const opening = { opening_text: "o".repeat(1500), opening_button: "Send me the link" };
    expect(openingProblems(opening, null, "instagram").text).toMatch(/^Instagram allows 1,000 bytes/);
    expect(openingProblems(opening, null, "facebook")).toEqual({});
  });
});

describe("accounts and labels", () => {
  const ig = account({ id: "a1", username: "maple.bakery" });
  const page = account({ id: "f1", platform: "facebook", username: "maplebakery", display_name: "Maple Bakery" });
  const wa = account({ id: "w1", platform: "whatsapp", username: null, phone_number: "+91 99999 99999" });
  const gone = account({ id: "f2", platform: "facebook", status: "disconnected" });

  it("automations run on connected Instagram accounts and Facebook Pages", () => {
    expect(automationAccounts([ig, page, wa, gone]).map((a) => a.id)).toEqual(["a1", "f1"]);
  });

  it("story mentions and publishing stay Instagram's", () => {
    expect(instagramAccounts([ig, page, wa]).map((a) => a.id)).toEqual(["a1"]);
  });

  it("a label is the handle, else the name, else what kind of account it is", () => {
    expect(accountLabel(page)).toBe("@maplebakery");
    expect(accountLabel({ username: null, display_name: null, platform: "facebook" })).toBe("Facebook Page");
    expect(accountLabel({ username: null, display_name: null })).toBe("Instagram account");
    expect(accountLabel({ username: null, display_name: "Maple Cafe", platform: "facebook" })).toBe("Maple Cafe");
  });

  it("trigger labels say Facebook for a Page", () => {
    expect(triggerLabel("comment_keyword", "facebook")).toBe("Facebook comment keyword");
    expect(triggerLabel("ice_breaker", "facebook")).toBe("Facebook conversation starter");
    expect(triggerLabel("comment_keyword", "instagram")).toBe("Instagram comment keyword");
    expect(triggerLabel("first_message", "facebook")).toBe("First message (welcome)");
    expect(triggerLabel("dm_keyword")).toBe("Instagram DM keyword");
  });
});
