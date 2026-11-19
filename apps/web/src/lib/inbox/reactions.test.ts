import { describe, expect, it } from "vitest";

import type { Message } from "@/lib/api/types";

import { canActOn, ourReaction, reactionsFor, REACTIONS, withOurReaction } from "./reactions";

function message(over: Partial<Message> = {}): Message {
  return {
    id: "m1",
    conversation_id: "c1",
    direction: "inbound",
    source: "customer",
    kind: "text",
    text: "Hi",
    attachments: [],
    occurred_at: "2026-11-19T10:00:00Z",
    human_agent_tag: false,
    reactions: [{ emoji: "😂", by: "customer", at: "2026-11-19T10:01:00Z" }],
    ...over,
  };
}

describe("reactions", () => {
  it("offers the six on WhatsApp and website chat, a heart on Instagram and Facebook, none on YouTube", () => {
    expect(reactionsFor("whatsapp")).toEqual(REACTIONS);
    expect(reactionsFor("web")).toEqual(REACTIONS);
    expect(reactionsFor("instagram")).toEqual(["❤️"]);
    expect(reactionsFor("facebook")).toEqual(["❤️"]);
    expect(reactionsFor("youtube")).toEqual([]);
  });

  it("sets, replaces and removes our reaction and keeps the customer's", () => {
    const liked = withOurReaction(message(), "👍");
    expect(ourReaction(liked)).toBe("👍");
    const loved = withOurReaction(liked, "❤️");
    expect(loved.reactions.map((r) => r.emoji)).toEqual(["😂", "❤️"]);
    const removed = withOurReaction(loved, null);
    expect(ourReaction(removed)).toBeNull();
    expect(removed.reactions).toHaveLength(1);
  });

  it("acts only on messages that reached the platform", () => {
    expect(canActOn(message())).toBe(true);
    expect(canActOn(message({ direction: "outbound", source: "human", status: "sent" }))).toBe(true);
    expect(canActOn(message({ direction: "outbound", source: "human", status: "queued" }))).toBe(false);
    expect(canActOn(message({ id: "local-1" }))).toBe(false);
    expect(canActOn(message({ deleted_at: "2026-11-19T10:02:00Z" }))).toBe(false);
  });
});
