import { describe, expect, it } from "vitest";

import type { ConversationFilters } from "@/lib/api/queries/keys";
import { listItem } from "@/test/api";

import { matchesFilters } from "./cache";

const filters = (view: ConversationFilters["view"]): ConversationFilters => ({ view, platform: null, accountId: null, q: "" });
const assigned = { user_id: "u2", name: "Sam Rao", avatar_url: null };

describe("matchesFilters: assignment views (GR-20)", () => {
  it("Unassigned holds open conversations nobody has", () => {
    expect(matchesFilters(listItem({ assignee: null }), filters("unassigned"))).toBe(true);
    expect(matchesFilters(listItem({ assignee: assigned }), filters("unassigned"))).toBe(false);
    expect(matchesFilters(listItem({ assignee: null, status: "archived" }), filters("unassigned"))).toBe(false);
  });

  it("Assigned to me is decided by the server for an open conversation, never for an archived one", () => {
    expect(matchesFilters(listItem({ assignee: assigned }), filters("mine"))).toBeNull();
    expect(matchesFilters(listItem({ assignee: assigned, status: "archived" }), filters("mine"))).toBe(false);
  });

  it("the other views are unchanged", () => {
    expect(matchesFilters(listItem(), filters("all"))).toBe(true);
    expect(matchesFilters(listItem({ unread_count: 0 }), filters("unread"))).toBe(false);
  });
});
