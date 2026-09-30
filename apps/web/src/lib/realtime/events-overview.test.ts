import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import { resetInboxStore } from "@/lib/inbox/store";
import { message } from "@/test/api";

import { applyRealtimeEvent, OVERVIEW_REFRESH_MS } from "./events";

const wid = "w1";

function send(queryClient: QueryClient, event: string, data: unknown) {
  applyRealtimeEvent(queryClient, wid, { id: "1-0", event, data: JSON.stringify(data) });
}

let queryClient: QueryClient;

function overviewRefetches(invalidate: { mock: { calls: Parameters<QueryClient["invalidateQueries"]>[] } }) {
  return invalidate.mock.calls.filter(
    ([filters]) => JSON.stringify(filters?.queryKey) === JSON.stringify(["w", wid, "overview"]),
  ).length;
}

beforeEach(() => {
  vi.useFakeTimers();
  queryClient = new QueryClient();
  resetInboxStore();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Home stays fresh (FR-HOME-01)", () => {
  it("a burst of events refetches the overview once, a moment later", () => {
    queryClient.setQueryData(keys.overview(wid, "7d"), { range: "7d" });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    for (let i = 0; i < 5; i++) {
      send(queryClient, "message.created", { conversation_id: "c1", message: message({ id: `m${i}` }) });
    }
    send(queryClient, "comment.created", { comment: { id: "cm1" } });
    expect(overviewRefetches(invalidate)).toBe(0);

    vi.advanceTimersByTime(OVERVIEW_REFRESH_MS);
    expect(overviewRefetches(invalidate)).toBe(1);

    send(queryClient, "conversation.updated", {});
    vi.advanceTimersByTime(OVERVIEW_REFRESH_MS);
    expect(overviewRefetches(invalidate)).toBe(2);
  });

  it("events that don't change Home's numbers, or a Home never opened, refetch nothing", () => {
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    send(queryClient, "message.created", { conversation_id: "c1", message: message() });
    vi.advanceTimersByTime(OVERVIEW_REFRESH_MS);
    expect(overviewRefetches(invalidate)).toBe(0);

    queryClient.setQueryData(keys.overview(wid, "30d"), { range: "30d" });
    send(queryClient, "notification.created", {});
    send(queryClient, "usage.updated", {});
    vi.advanceTimersByTime(OVERVIEW_REFRESH_MS);
    expect(overviewRefetches(invalidate)).toBe(0);
  });

  it("a suggested reply refreshes the priority queue's AI draft ready (a custom range too)", () => {
    queryClient.setQueryData(keys.overview(wid, "custom:2026-09-19:2026-09-30"), { range: "custom" });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    send(queryClient, "suggestion.created", { conversation_id: "c1" });
    send(queryClient, "suggestion.updated", { conversation_id: "c1" });
    vi.advanceTimersByTime(OVERVIEW_REFRESH_MS);

    expect(overviewRefetches(invalidate)).toBe(1);
  });
});
