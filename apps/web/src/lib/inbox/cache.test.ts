import { describe, expect, it } from "vitest";

import type { ConversationFilters } from "@/lib/api/queries/keys";
import { listItem, message } from "@/test/api";

import { matchesFilters, upsertMessageInPages, upsertQueuedResponse } from "./cache";

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

describe("matchesFilters: snoozed (GR-45)", () => {
  const snoozed = { snoozed_until: "2026-11-20T09:00:00Z" };

  it("a snoozed conversation is only in the Snoozed view", () => {
    expect(matchesFilters(listItem(snoozed), filters("snoozed"))).toBe(true);
    for (const view of ["all", "unread", "needs_reply", "leads", "unassigned", "mine"] as const) {
      expect(matchesFilters(listItem({ ...snoozed, unread_count: 2, awaiting_reply: true, lead_score: 90 }), filters(view))).toBe(false);
    }
  });

  it("a conversation that is not snoozed is not in the Snoozed view", () => {
    expect(matchesFilters(listItem(), filters("snoozed"))).toBe(false);
    expect(matchesFilters(listItem({ status: "archived" }), filters("snoozed"))).toBe(false);
  });

  it("an archived conversation stays in Archived", () => {
    expect(matchesFilters(listItem({ status: "archived" }), filters("archived"))).toBe(true);
  });
});

describe("upsertQueuedResponse: a send's 202 after the worker's update (C-154)", () => {
  const pages = (...items: ReturnType<typeof message>[]) => ({ pages: [{ items, next_cursor: null }], pageParams: [null] });
  const queued = message({ id: "m1", client_id: "c1", direction: "outbound", status: "queued" });

  it("keeps Sent or Failed that arrived before the response", () => {
    for (const status of ["sent", "failed"] as const) {
      const data = pages(message({ id: "m1", client_id: "c1", direction: "outbound", status }));
      expect(upsertQueuedResponse(data, queued).pages[0].items[0].status).toBe(status);
      // An event replaces it as before.
      expect(upsertMessageInPages(data, queued).pages[0].items[0].status).toBe("queued");
    }
  });

  it("replaces the optimistic bubble, a copy still queued, or adds it", () => {
    const local = message({ id: "local-c1", client_id: "c1", direction: "outbound", status: "queued" });
    expect(upsertQueuedResponse(pages(local), queued).pages[0].items.map((m) => m.id)).toEqual(["m1"]);
    expect(upsertQueuedResponse(pages(queued), { ...queued, text: "again" }).pages[0].items[0].text).toBe("again");
    expect(upsertQueuedResponse(pages(), queued).pages[0].items.map((m) => m.id)).toEqual(["m1"]);
  });
});
