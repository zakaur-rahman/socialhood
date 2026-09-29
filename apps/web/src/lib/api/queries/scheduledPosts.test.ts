import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { applyRealtimeEvent } from "@/lib/realtime/events";
import { automation } from "@/test/api";
import { readyPost } from "@/test/composer-fixtures";

import { applyComposerPost, composerKeys, linkedDefinition } from "./scheduledPosts";

describe("scheduled post cache", () => {
  it("scheduled_post.updated replaces the composer's copy and refreshes lists and the calendar", () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(composerKeys.post("w1", "sp1"), readyPost());
    queryClient.setQueryData([...composerKeys.lists("w1"), "scheduled"], { items: [] });
    queryClient.setQueryData([...composerKeys.calendar("w1"), "2026-09-28"], { posts: [] });
    applyRealtimeEvent(queryClient, "w1", {
      id: "1-0",
      event: "scheduled_post.updated",
      data: JSON.stringify({ scheduled_post: readyPost({ status: "published" }) }),
    });
    expect(queryClient.getQueryData<{ status: string }>(composerKeys.post("w1", "sp1"))?.status).toBe("published");
    expect(queryClient.getQueryState([...composerKeys.lists("w1"), "scheduled"])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState([...composerKeys.calendar("w1"), "2026-09-28"])?.isInvalidated).toBe(true);
  });

  it("ignores a malformed event", () => {
    const queryClient = new QueryClient();
    applyRealtimeEvent(queryClient, "w1", { id: "1-0", event: "scheduled_post.updated", data: "{" });
    expect(queryClient.getQueryData(composerKeys.post("w1", "sp1"))).toBeUndefined();
    applyComposerPost(queryClient, "w1", readyPost());
    expect(queryClient.getQueryData(composerKeys.post("w1", "sp1"))).toBeDefined();
  });
});

describe("linkedDefinition (FR-AUT-18)", () => {
  it("scopes a template's automation to the scheduled post only", () => {
    const definition = linkedDefinition(automation({ post_scope: "all", posts: [{ media_item_id: "m1" }] }), "sp1");
    expect(definition).toMatchObject({
      trigger: "comment_keyword",
      post_scope: "selected",
      media_item_ids: [],
      scheduled_post_ids: ["sp1"],
    });
  });

  it("gives a blank automation a comment trigger and tap first's defaults", () => {
    const definition = linkedDefinition(automation({ trigger: null, keywords: [], opening_text: null, opening_button: null }), "sp1");
    expect(definition.trigger).toBe("comment_keyword");
    expect(definition.confirm_first).toBe(true);
    expect(definition.scheduled_post_ids).toEqual(["sp1"]);
  });

  it("keeps an any-comment template's trigger", () => {
    expect(linkedDefinition(automation({ trigger: "comment_any", keywords: [] }), "sp1").trigger).toBe("comment_any");
  });
});
