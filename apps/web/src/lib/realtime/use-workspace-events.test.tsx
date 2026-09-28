import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, makeQueryClient } from "@/lib/api/provider";
import { keys } from "@/lib/api/queries/keys";
import type { MessagePages } from "@/lib/inbox/cache";
import { fakeApi, message } from "@/test/api";

import { useWorkspaceEvents } from "./use-workspace-events";

/** A text/event-stream response that sends these chunks and then stays open. */
function eventStream(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const queue = [...chunks];
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      const next = queue.shift();
      if (next !== undefined) controller.enqueue(encoder.encode(next));
      // then nothing: the connection stays open like the real stream
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("useWorkspaceEvents (TR-FE-04)", () => {
  it("reads the stream through the API client with the token and patches the cache", async () => {
    const inbound = message({ id: "m-live", conversation_id: "c1", text: "Hello again" });
    const { api, calls } = fakeApi({
      "GET /v1/w/:wid/events": () =>
        eventStream([
          "retry: 3000\n\n",
          `id: 5-0\nevent: message.created\ndata: ${JSON.stringify({ conversation_id: "c1", message: inbound })}\n\n`,
        ]),
    });
    const queryClient = makeQueryClient();
    queryClient.setQueryData<MessagePages>(keys.messages("w1", "c1"), {
      pages: [{ items: [], next_cursor: null }],
      pageParams: [null],
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ApiClientProvider api={api} queryClient={queryClient}>
        {children}
      </ApiClientProvider>
    );

    const { unmount } = renderHook(() => useWorkspaceEvents("w1", "c1"), { wrapper });

    await waitFor(() =>
      expect(queryClient.getQueryData<MessagePages>(keys.messages("w1", "c1"))?.pages[0].items).toEqual([inbound]),
    );
    const call = calls.find((c) => c.path === "/v1/w/w1/events");
    expect(call?.headers.get("Authorization")).toBe("Bearer test-token");
    expect(call?.headers.get("Accept")).toBe("text/event-stream");
    expect(call?.headers.get("Last-Event-ID")).toBeNull();
    unmount();
  });
});
