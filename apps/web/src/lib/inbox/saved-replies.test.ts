import { describe, expect, it } from "vitest";

import type { SavedReply } from "@/lib/api/types";

import { insertReply, matchReplies, PICKER_LIMIT, slashToken } from "./saved-replies";

function reply(shortcut: string, title = shortcut): SavedReply {
  return { id: shortcut, shortcut, title, body: `Body of ${shortcut}`, created_at: "", updated_at: "" };
}

describe("slashToken (GR-21)", () => {
  it("finds a slash word at the start of the draft, a line or after a space", () => {
    expect(slashToken("/pri", 4)).toEqual({ start: 0, query: "pri" });
    expect(slashToken("Hi!\n/Price", 10)).toEqual({ start: 4, query: "price" });
    expect(slashToken("Sure, /faq", 10)).toEqual({ start: 6, query: "faq" });
    expect(slashToken("/", 1)).toEqual({ start: 0, query: "" });
  });

  it("ignores slashes inside words and links", () => {
    expect(slashToken("and/or", 6)).toBeNull();
    expect(slashToken("see https://shop.example/pri", 28)).toBeNull();
    expect(slashToken("no slash", 8)).toBeNull();
  });

  it("only looks at the text before the caret", () => {
    expect(slashToken("/price and more", 6)).toEqual({ start: 0, query: "price" });
    expect(slashToken("/price and more", 15)).toBeNull();
  });
});

describe("matchReplies (GR-21)", () => {
  const replies = [reply("hours", "Opening hours"), reply("price", "Prices"), reply("pricing-b2b"), reply("faq", "Price FAQ")];

  it("puts the exact shortcut first, then shortcuts that start with the query, then the rest", () => {
    // "price" is exact; "faq" only has it in its title; "pricing-b2b" doesn't contain "price".
    expect(matchReplies(replies, "price").map((r) => r.shortcut)).toEqual(["price", "faq"]);
  });

  it("matches the start of a shortcut and a word in a title", () => {
    expect(matchReplies(replies, "pri").map((r) => r.shortcut)).toEqual(["price", "pricing-b2b", "faq"]);
    expect(matchReplies(replies, "OPENING").map((r) => r.shortcut)).toEqual(["hours"]);
  });

  it("lists everything in shortcut order for an empty query, up to the limit", () => {
    const many = Array.from({ length: 10 }, (_, i) => reply(`r${i}`));
    expect(matchReplies(many, "")).toHaveLength(PICKER_LIMIT);
    expect(matchReplies(replies, "").map((r) => r.shortcut)).toEqual(["faq", "hours", "price", "pricing-b2b"]);
  });

  it("finds nothing for an unknown word", () => {
    expect(matchReplies(replies, "zzz")).toEqual([]);
  });
});

describe("insertReply (GR-21)", () => {
  it("replaces the slash word and puts the caret after the text", () => {
    const draft = "Hello!\n/price";
    const token = slashToken(draft, draft.length);
    expect(token).not.toBeNull();
    expect(insertReply(draft, token!, "Hi Priya, from 499.")).toEqual({
      draft: "Hello!\nHi Priya, from 499.",
      caret: 26,
    });
  });
});
