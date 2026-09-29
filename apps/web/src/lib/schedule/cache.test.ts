import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import type { Calendar, ScheduledMessage } from "@/lib/api/types";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import { calendar, calendarMessage, detail, ist, scheduledPost } from "@/test/schedule";

import { restoreCalendars, snapshotCalendars, withPost } from "./cache";

const wid = "w1";
const week = keys.calendar(wid, "2026-09-28", "2026-10-04");
const nextWeek = keys.calendar(wid, "2026-10-05", "2026-10-11");

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient();
});

function send(event: string, data: unknown) {
  applyRealtimeEvent(queryClient, wid, { id: "1-0", event, data: JSON.stringify(data) });
}

function postIds(key: readonly unknown[]): string[] {
  return queryClient.getQueryData<Calendar>(key)?.posts.map((post) => post.id) ?? [];
}

describe("schedule cache (TR-FE-04)", () => {
  it("moves a post within the range, and drops it when it leaves", () => {
    const post = scheduledPost({ id: "p1" });
    const base = calendar({ posts: [post] });
    expect(withPost(base, { ...post, publish_at: ist("2026-10-01", "15:00") }).posts[0].publish_at).toBe(ist("2026-10-01", "15:00"));
    expect(withPost(base, { ...post, publish_at: ist("2026-10-06", "15:00") }).posts).toHaveLength(0);
    expect(withPost(calendar(), { ...post, publish_at: ist("2026-10-04", "23:59") }).posts).toHaveLength(1);
  });

  it("scheduled_post.updated moves the post between loaded weeks", () => {
    const post = scheduledPost({ id: "p1", publish_at: ist("2026-09-30", "18:00") });
    queryClient.setQueryData(week, calendar({ posts: [post] }));
    queryClient.setQueryData(nextWeek, calendar({ start: "2026-10-05", end: "2026-10-11" }));
    send("scheduled_post.updated", { scheduled_post: detail({ ...post, publish_at: ist("2026-10-07", "09:00") }) });
    expect(postIds(week)).toEqual([]);
    expect(postIds(nextWeek)).toEqual(["p1"]);
  });

  it("restores every calendar from a snapshot when a move is refused", async () => {
    const post = scheduledPost({ id: "p1" });
    queryClient.setQueryData(week, calendar({ posts: [post] }));
    const snapshot = await snapshotCalendars(queryClient, wid);
    queryClient.setQueryData(week, calendar({ posts: [] }));
    restoreCalendars(queryClient, snapshot);
    expect(postIds(week)).toEqual(["p1"]);
  });

  it("scheduled_message.updated keeps the Messages layer's DM in step", () => {
    const dm = calendarMessage({ id: "dm1" });
    queryClient.setQueryData(week, calendar({ messages: [dm] }));
    const moved: ScheduledMessage = { ...dm, send_at: ist("2026-10-02", "08:00") };
    send("scheduled_message.updated", { scheduled_message: moved });
    expect(queryClient.getQueryData<Calendar>(week)?.messages[0].send_at).toBe(ist("2026-10-02", "08:00"));
    send("scheduled_message.updated", { scheduled_message: { ...moved, status: "canceled" } });
    expect(queryClient.getQueryData<Calendar>(week)?.messages).toHaveLength(0);
  });
});
