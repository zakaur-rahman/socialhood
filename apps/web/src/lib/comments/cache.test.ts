import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import type { CommentFilter, PostComment } from "@/lib/api/types";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import { comment, post, postDetail } from "@/test/api";

import { applyComment, flattenComments, flattenPosts, removeComment, type CommentPages, type PostPages } from "./cache";

const wid = "w1";

function pages<T>(...pageItems: T[][]) {
  return {
    pages: pageItems.map((items, i) => ({ items, next_cursor: i < pageItems.length - 1 ? `cursor-${i + 1}` : null })),
    pageParams: pageItems.map((_, i) => (i === 0 ? null : `cursor-${i}`)),
  };
}

function send(queryClient: QueryClient, event: string, data: unknown) {
  applyRealtimeEvent(queryClient, wid, { id: "1-0", event, data: JSON.stringify(data) });
}

function gridIds(queryClient: QueryClient, accountId: string | null, q = ""): string[] {
  return flattenPosts(queryClient.getQueryData<PostPages>(keys.posts(wid, accountId, q))).map((p) => p.id);
}

function listIds(queryClient: QueryClient, filter: CommentFilter, postId = "po1"): string[] {
  return flattenComments(queryClient.getQueryData<CommentPages>(keys.postComments(wid, postId, filter))).map((c) => c.id);
}

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient();
});

describe("post.updated patches the grid and the open post (F-12)", () => {
  it("replaces the card's counts in every loaded list and the post detail", () => {
    const card = post({ id: "po1" });
    queryClient.setQueryData(keys.posts(wid, null, ""), pages([card, post({ id: "po2", posted_at: "2026-09-20T12:00:00Z" })]));
    queryClient.setQueryData(keys.posts(wid, "a1", ""), pages([card]));
    queryClient.setQueryData(keys.post(wid, "po1"), postDetail({ id: "po1" }));

    const stats = { total: 13, analysed: 12, positive: 7, neutral: 3, negative: 1, spam: 1 };
    send(queryClient, "post.updated", { post: postDetail({ id: "po1", stats, summary: "New summary" }) });

    const all = queryClient.getQueryData<PostPages>(keys.posts(wid, null, ""))!;
    expect(all.pages[0].items[0].stats).toEqual(stats);
    // the grid keeps the list projection, without the summary and topics
    expect(all.pages[0].items[0]).not.toHaveProperty("summary");
    expect(queryClient.getQueryData<PostPages>(keys.posts(wid, "a1", ""))!.pages[0].items[0].stats.total).toBe(13);
    expect(queryClient.getQueryData<{ summary: string }>(keys.post(wid, "po1"))?.summary).toBe("New summary");
    expect(gridIds(queryClient, null)).toEqual(["po1", "po2"]);
  });

  it("adds a new post to lists it belongs in, newest first, and never to searches or other accounts", () => {
    queryClient.setQueryData(keys.posts(wid, null, ""), pages([post({ id: "po1" })]));
    queryClient.setQueryData(keys.posts(wid, "a2", ""), pages([]));
    queryClient.setQueryData(keys.posts(wid, "a1", "linen"), pages([post({ id: "po1" })]));

    send(queryClient, "post.updated", { post: postDetail({ id: "po9", posted_at: "2026-09-28T09:00:00Z" }) });

    expect(gridIds(queryClient, null)).toEqual(["po9", "po1"]);
    expect(gridIds(queryClient, "a2")).toEqual([]);
    expect(gridIds(queryClient, "a1", "linen")).toEqual(["po1"]);
  });

  it("leaves an older unknown post for the page that will bring it", () => {
    // One page loaded, more to come.
    queryClient.setQueryData<PostPages>(keys.posts(wid, null, ""), {
      pages: [{ items: [post({ id: "po1", posted_at: "2026-09-27T12:00:00Z" })], next_cursor: "cursor-1" }],
      pageParams: [null],
    });
    send(queryClient, "post.updated", { post: postDetail({ id: "po8", posted_at: "2026-09-01T12:00:00Z" }) });
    expect(gridIds(queryClient, null)).toEqual(["po1"]);
  });

  it("ignores a post that is not loaded anywhere", () => {
    send(queryClient, "post.updated", { post: postDetail({ id: "po5" }) });
    expect(queryClient.getQueryData(keys.post(wid, "po5"))).toBeUndefined();
  });
});

describe("comment events patch the post's lists by filter", () => {
  function seed(filter: CommentFilter, items: PostComment[]) {
    queryClient.setQueryData(keys.postComments(wid, "po1", filter), pages(items));
  }

  it("comment.created inserts the comment, newest first, where it matches", () => {
    const older = comment({ id: "c-old", commented_at: "2026-09-28T09:00:00Z" });
    seed("all", [older]);
    seed("negative", []);
    seed("positive", []);
    const fresh = comment({ id: "c-new", commented_at: "2026-09-28T12:00:00Z", analysis: null, analysis_status: "pending" });
    send(queryClient, "comment.created", { comment: fresh });
    send(queryClient, "comment.created", { comment: fresh }); // replayed after a reconnect

    expect(listIds(queryClient, "all")).toEqual(["c-new", "c-old"]);
    expect(listIds(queryClient, "positive")).toEqual([]);

    // analysed as positive: joins Positive, stays in All
    send(queryClient, "comment.updated", {
      comment: {
        ...fresh,
        analysis_status: "done",
        analysis: { sentiment: "positive", sentiment_score: 0.8, intent: "greeting", is_spam: false, topic: null },
      },
    });
    expect(listIds(queryClient, "positive")).toEqual(["c-new"]);
    expect(listIds(queryClient, "negative")).toEqual([]);
    const row = flattenComments(queryClient.getQueryData<CommentPages>(keys.postComments(wid, "po1", "all")))[0];
    expect(row.analysis?.sentiment).toBe("positive");
  });

  it("unhiding removes a comment from Hidden but keeps it in All", () => {
    const hidden = comment({ id: "c1", hidden: true });
    seed("all", [hidden]);
    seed("hidden", [hidden]);
    applyComment(queryClient, wid, { ...hidden, hidden: false });
    expect(listIds(queryClient, "hidden")).toEqual([]);
    expect(listIds(queryClient, "all")).toEqual(["c1"]);
  });

  it("comment.updated with deleted_at drops the row everywhere; removeComment does the same", () => {
    const a = comment({ id: "c1" });
    const b = comment({ id: "c2", commented_at: "2026-09-28T10:00:00Z" });
    seed("all", [a, b]);
    seed("questions", [a]);
    send(queryClient, "comment.updated", { comment: { ...a, deleted_at: "2026-09-28T12:00:00Z" } });
    expect(listIds(queryClient, "all")).toEqual(["c2"]);
    expect(listIds(queryClient, "questions")).toEqual([]);

    removeComment(queryClient, wid, "po1", "c2");
    expect(listIds(queryClient, "all")).toEqual([]);
  });

  it("touches only the comment's own post", () => {
    seed("all", []);
    send(queryClient, "comment.created", { comment: comment({ id: "x1", post_id: "po2" }) });
    expect(listIds(queryClient, "all")).toEqual([]);
  });
});
