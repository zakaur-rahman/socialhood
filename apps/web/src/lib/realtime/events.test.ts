import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";

import { keys, type ConversationFilters } from "@/lib/api/queries/keys";
import type { Conversation, ScheduledMessage } from "@/lib/api/types";
import type { ConversationPages, MessagePages, ScheduledPages } from "@/lib/inbox/cache";
import { flattenMessages } from "@/lib/inbox/cache";
import { resetInboxStore, useInboxStore } from "@/lib/inbox/store";
import { conversation, listItem, message } from "@/test/api";

import { applyRealtimeEvent } from "./events";

const wid = "w1";
const all: ConversationFilters = { view: "all", platform: null, accountId: null, q: "" };
const unread: ConversationFilters = { ...all, view: "unread" };
const archived: ConversationFilters = { ...all, view: "archived" };

function send(queryClient: QueryClient, event: string, data: unknown, openConversationId: string | null = null) {
  applyRealtimeEvent(queryClient, wid, { id: "1-0", event, data: JSON.stringify(data) }, { openConversationId });
}

function pages<T>(...pageItems: T[][]): { pages: { items: T[]; next_cursor: string | null }[]; pageParams: (string | null)[] } {
  return {
    pages: pageItems.map((items, i) => ({ items, next_cursor: i < pageItems.length - 1 ? `cursor-${i + 1}` : null })),
    pageParams: pageItems.map((_, i) => (i === 0 ? null : `cursor-${i}`)),
  };
}

function ids(queryClient: QueryClient, filters: ConversationFilters): string[] {
  const data = queryClient.getQueryData<ConversationPages>(keys.conversations(wid, filters));
  return data?.pages.flatMap((page) => page.items.map((item) => item.id)) ?? [];
}

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient();
  resetInboxStore();
});

describe("message events patch the thread (TR-FE-04)", () => {
  it("message.created inserts once, newest first, and replaces the optimistic bubble by client_id", () => {
    const older = message({ id: "m1", occurred_at: "2026-09-28T10:00:00Z" });
    const optimistic = message({
      id: "local-k1",
      client_id: "k1",
      direction: "outbound",
      source: "human",
      status: "queued",
      occurred_at: "2026-09-28T11:00:00Z",
    });
    queryClient.setQueryData<MessagePages>(keys.messages(wid, "c1"), pages([optimistic, older]));
    useInboxStore.getState().putOutbox({
      clientId: "k1",
      conversationId: "c1",
      body: { client_id: "k1", text: "Hi" },
      message: optimistic,
    });

    const stored = { ...optimistic, id: "m2", status: "queued" as const };
    send(queryClient, "message.created", { conversation_id: "c1", message: stored });
    send(queryClient, "message.created", { conversation_id: "c1", message: stored }); // replayed after a reconnect

    const inbound = message({ id: "m3", occurred_at: "2026-09-28T11:30:00Z", text: "Thanks" });
    send(queryClient, "message.created", { conversation_id: "c1", message: inbound });

    const list = flattenMessages(queryClient.getQueryData<MessagePages>(keys.messages(wid, "c1")));
    expect(list.map((m) => m.id)).toEqual(["m1", "m2", "m3"]);
    expect(useInboxStore.getState().outbox).toEqual({});
  });

  it("message.updated replaces by id in whichever page holds it", () => {
    const sent = message({ id: "m1", direction: "outbound", source: "human", status: "sending" });
    queryClient.setQueryData<MessagePages>(keys.messages(wid, "c1"), pages([message({ id: "m9" })], [sent]));
    send(queryClient, "message.updated", {
      conversation_id: "c1",
      message: { ...sent, status: "failed", error: { code: "platform_unavailable", message: "Timeout" } },
    });
    const data = queryClient.getQueryData<MessagePages>(keys.messages(wid, "c1"))!;
    expect(data.pages[1].items[0]).toMatchObject({ id: "m1", status: "failed", error: { code: "platform_unavailable" } });
    expect(data.pages[0].items).toHaveLength(1);
  });

  it("leaves conversations that are not loaded alone", () => {
    send(queryClient, "message.created", { conversation_id: "c2", message: message({ conversation_id: "c2" }) });
    expect(queryClient.getQueryData(keys.messages(wid, "c2"))).toBeUndefined();
  });
});

describe("conversation.updated patches every list (TR-FE-04)", () => {
  it("moves a conversation with a new message to the top and marks it unread", () => {
    queryClient.setQueryData(
      keys.conversations(wid, all),
      pages([
        listItem({ id: "c1", last_message_at: "2026-09-28T11:00:00Z" }),
        listItem({ id: "c2", last_message_at: "2026-09-28T10:00:00Z" }),
      ]),
    );
    send(queryClient, "conversation.updated", {
      conversation: listItem({ id: "c2", last_message_at: "2026-09-28T12:00:00Z", unread_count: 1 }),
    });
    expect(ids(queryClient, all)).toEqual(["c2", "c1"]);
    const top = queryClient.getQueryData<ConversationPages>(keys.conversations(wid, all))!.pages[0].items[0];
    expect(top.unread_count).toBe(1);
  });

  it("inserts a new conversation that matches, and ignores one that doesn't", () => {
    queryClient.setQueryData(keys.conversations(wid, unread), pages([listItem({ id: "c1", unread_count: 2 })]));
    send(queryClient, "conversation.updated", {
      conversation: listItem({ id: "c3", unread_count: 1, last_message_at: "2026-09-28T12:30:00Z" }),
    });
    send(queryClient, "conversation.updated", {
      conversation: listItem({ id: "c4", unread_count: 0, last_message_at: "2026-09-28T12:40:00Z" }),
    });
    expect(ids(queryClient, unread)).toEqual(["c3", "c1"]);
  });

  it("removes it from lists it no longer matches, except the one on screen", () => {
    queryClient.setQueryData(keys.conversations(wid, all), pages([listItem({ id: "c1" }), listItem({ id: "c2" })]));
    queryClient.setQueryData(keys.conversations(wid, archived), pages([]));
    send(queryClient, "conversation.updated", { conversation: listItem({ id: "c1", status: "archived" }) });
    expect(ids(queryClient, all)).toEqual(["c2"]);
    expect(ids(queryClient, archived)).toEqual(["c1"]);

    send(queryClient, "conversation.updated", { conversation: listItem({ id: "c2", status: "archived" }) }, "c2");
    expect(ids(queryClient, all)).toEqual(["c2"]);
  });

  it("does not insert past the loaded range, where the next page would hold it", () => {
    queryClient.setQueryData(
      keys.conversations(wid, all),
      pages([listItem({ id: "c1", last_message_at: "2026-09-28T11:00:00Z" })], [listItem({ id: "c2", last_message_at: "2026-09-28T10:00:00Z" })]),
    );
    // Make the last page claim there is more.
    const data = queryClient.getQueryData<ConversationPages>(keys.conversations(wid, all))!;
    data.pages[1].next_cursor = "more";
    send(queryClient, "conversation.updated", {
      conversation: listItem({ id: "c0", last_message_at: "2026-09-20T10:00:00Z" }),
    });
    expect(ids(queryClient, all)).toEqual(["c1", "c2"]);
  });

  it("merges into the conversation detail, keeping its detail-only fields", () => {
    const detail = conversation({ id: "c1", unread_count: 0 });
    queryClient.setQueryData(keys.conversation(wid, "c1"), detail);
    send(queryClient, "conversation.updated", {
      conversation: listItem({ id: "c1", unread_count: 3, contact: { ...detail.contact, display_name: "Priya N." } }),
    });
    const merged = queryClient.getQueryData<Conversation>(keys.conversation(wid, "c1"))!;
    expect(merged.unread_count).toBe(3);
    expect(merged.contact.display_name).toBe("Priya N.");
    expect(merged.contact.first_seen_at).toBe(detail.contact.first_seen_at);
    expect(merged.reply_window).toEqual(detail.reply_window);
  });

  it("refreshes the unread badge", () => {
    queryClient.setQueryData(keys.inboxCounts(wid), { unread: 1, needs_reply: 1, needs_you: 0 });
    send(queryClient, "conversation.updated", { conversation: listItem({ id: "c1", unread_count: 1 }) });
    expect(queryClient.getQueryState(keys.inboxCounts(wid))?.isInvalidated).toBe(true);
  });
});

describe("other events", () => {
  it("resync invalidates everything in the workspace, and nothing outside it", () => {
    queryClient.setQueryData(keys.conversations(wid, all), pages([listItem()]));
    queryClient.setQueryData(keys.messages(wid, "c1"), pages([message()]));
    queryClient.setQueryData(keys.me, { id: "u1" });
    send(queryClient, "resync", {});
    expect(queryClient.getQueryState(keys.conversations(wid, all))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(keys.messages(wid, "c1"))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(keys.me)?.isInvalidated).toBe(false);
  });

  it("scheduled_message.updated replaces by id and drops canceled ones", () => {
    const pending: ScheduledMessage = {
      id: "s1",
      conversation_id: "c1",
      text: "Following up",
      attachment_asset_ids: [],
      send_at: "2026-09-28T13:00:00Z",
      status: "scheduled",
      error: null,
      contact: { display_name: "Priya", username: null, profile_picture_url: null },
      platform: "instagram",
    };
    queryClient.setQueryData<ScheduledPages>(keys.scheduled(wid), pages([pending]));
    send(queryClient, "scheduled_message.updated", { scheduled_message: { ...pending, status: "sent" } });
    expect(queryClient.getQueryData<ScheduledPages>(keys.scheduled(wid))!.pages[0].items[0].status).toBe("sent");
    send(queryClient, "scheduled_message.updated", { scheduled_message: { ...pending, status: "canceled" } });
    expect(queryClient.getQueryData<ScheduledPages>(keys.scheduled(wid))!.pages[0].items).toEqual([]);
  });

  it("ignores malformed payloads and unknown events", () => {
    queryClient.setQueryData(keys.conversations(wid, all), pages([listItem()]));
    applyRealtimeEvent(queryClient, wid, { id: null, event: "conversation.updated", data: "{not json" });
    applyRealtimeEvent(queryClient, wid, { id: null, event: "comment.created", data: "{}" });
    expect(ids(queryClient, all)).toEqual(["c1"]);
  });
});
