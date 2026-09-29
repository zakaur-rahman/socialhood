import { describe, expect, it, vi } from "vitest";

import { reconnectDelay, runEventStream, SseParser, type SseEvent } from "./sse";

function parse(chunks: string[]) {
  const events: SseEvent[] = [];
  const retries: number[] = [];
  const parser = new SseParser((e) => events.push(e), (ms) => retries.push(ms));
  for (const chunk of chunks) parser.feed(chunk);
  parser.end();
  return { events, retries, parser };
}

describe("SseParser (text/event-stream)", () => {
  it("parses id, event and data, as the API sends them (TR-RT-02)", () => {
    const { events } = parse([
      'id: 1727520000000-0\nevent: message.created\ndata: {"conversation_id":"c1"}\n\n',
    ]);
    expect(events).toEqual([{ id: "1727520000000-0", event: "message.created", data: '{"conversation_id":"c1"}' }]);
  });

  it("joins multi-line data and defaults the type to message", () => {
    expect(parse(["data: a\ndata: b\n\n"]).events).toEqual([{ id: null, event: "message", data: "a\nb" }]);
  });

  it("handles any chunking, including a CRLF split across chunks", () => {
    const text = "id: 7\r\nevent: resync\r\ndata: {}\r\n\r\nid: 8\r\ndata: x\r\n\r\n";
    const whole = parse([text]).events;
    const bytewise = parse(text.split("")).events;
    const crSplit = parse(["id: 7\r", "\nevent: resync\r", "\ndata: {}\r\n\r", "\nid: 8\r\ndata: x\r\n\r\n"]).events;
    expect(whole).toEqual([
      { id: "7", event: "resync", data: "{}" },
      { id: "8", event: "message", data: "x" },
    ]);
    expect(bytewise).toEqual(whole);
    expect(crSplit).toEqual(whole);
  });

  it("ignores comments (: ping) and unknown fields, and reports retry", () => {
    const { events, retries } = parse([": ping\n\nretry: 3000\n\nfoo: bar\ndata: ok\n\n"]);
    expect(events).toEqual([{ id: null, event: "message", data: "ok" }]);
    expect(retries).toEqual([3000]);
  });

  it("keeps the last id even for an event without data, and strips a BOM", () => {
    const { events, parser } = parse(["﻿data: first\n\n", "id: 42\n\n"]);
    expect(events).toEqual([{ id: null, event: "message", data: "first" }]);
    expect(parser.lastEventId).toBe("42");
  });

  it("drops an unfinished event at the end of the stream", () => {
    expect(parse(["data: done\n\ndata: half"]).events).toHaveLength(1);
  });
});

/** A fake response body that yields the given chunks, then ends (or errors). */
function stream(chunks: string[], { error = false }: { error?: boolean } = {}): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const queue = [...chunks];
  return new ReadableStream({
    // pull, not start: erroring a stream drops chunks still queued, and a real drop comes after them.
    pull(controller) {
      const next = queue.shift();
      if (next !== undefined) controller.enqueue(encoder.encode(next));
      else if (error) controller.error(new TypeError("network error"));
      else controller.close();
    },
  });
}

describe("runEventStream (TR-FE-04)", () => {
  it("resumes with Last-Event-ID after a drop, backs off and honours retry:", async () => {
    const controller = new AbortController();
    const opened: (string | null)[] = [];
    const delays: number[] = [];
    const events: string[] = [];
    const infos: { reconnect: boolean; resumed: boolean }[] = [];
    const states: string[] = [];
    const bodies = [
      () => stream(["retry: 3000\n\n", "id: 1-0\nevent: message.created\ndata: {}\n\n"], { error: true }),
      () => {
        throw new Error("503");
      },
      () => stream(["id: 2-0\nevent: conversation.updated\ndata: {}\n\n"]),
    ];

    await runEventStream({
      signal: controller.signal,
      random: () => 0.5, // no jitter
      open: async (lastEventId) => {
        opened.push(lastEventId);
        const next = bodies.shift();
        if (!next) {
          controller.abort();
          throw new Error("done");
        }
        return next();
      },
      onOpen: (info) => {
        infos.push(info);
        states.push("open");
      },
      onReconnecting: () => states.push("reconnecting"),
      onEvent: (event) => events.push(`${event.id} ${event.event}`),
      sleep: async (ms) => {
        delays.push(ms);
      },
    });

    expect(events).toEqual(["1-0 message.created", "2-0 conversation.updated"]);
    expect(opened).toEqual([null, "1-0", "1-0", "2-0"]);
    expect(infos).toEqual([
      { reconnect: false, resumed: false },
      { reconnect: true, resumed: true },
    ]);
    // The server's retry (3 s) is the base; the failed open doubles it; a good open resets.
    expect(delays).toEqual([3000, 6000, 3000]);
    // Every drop or failed attempt says so before the wait; an abort does not.
    expect(states).toEqual(["open", "reconnecting", "reconnecting", "open", "reconnecting"]);
  });

  it("stops when aborted", async () => {
    const controller = new AbortController();
    const open = vi.fn(async () => {
      controller.abort();
      throw new DOMException("aborted", "AbortError");
    });
    await runEventStream({ signal: controller.signal, open, onEvent: () => {}, sleep: async () => {} });
    expect(open).toHaveBeenCalledOnce();
  });

  it("caps the backoff at 30 s with ±20 % jitter", () => {
    expect(reconnectDelay(0, 1000, 30_000, () => 0.5)).toBe(1000);
    expect(reconnectDelay(3, 1000, 30_000, () => 0.5)).toBe(8000);
    expect(reconnectDelay(10, 1000, 30_000, () => 0.5)).toBe(30_000);
    expect(reconnectDelay(10, 1000, 30_000, () => 1)).toBe(36_000);
    expect(reconnectDelay(0, 1000, 30_000, () => 0)).toBe(800);
  });
});
