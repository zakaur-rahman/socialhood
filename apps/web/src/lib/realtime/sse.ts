/**
 * A fetch-based Server-Sent Events client (TR-FE-04, TR-RT-02). EventSource cannot send the
 * Authorization header, so the stream is read from a fetch response body: a text/event-stream
 * parser, Last-Event-ID resume, the server's `retry:` value, and backoff from 1 s to 30 s.
 */

export type SseEvent = {
  /** The last event id seen when this event was dispatched (the stream id). */
  id: string | null;
  /** The `event:` field; "message" when absent. */
  event: string;
  data: string;
};

/**
 * Incremental parser for the event-stream format (WHATWG HTML §9.2.6). Feed it text as it
 * arrives, in chunks of any size; complete events go to onEvent.
 */
export class SseParser {
  private buffer = "";
  private data: string[] = [];
  private type = "";
  private started = false;
  lastEventId: string | null = null;

  constructor(
    private readonly onEvent: (event: SseEvent) => void,
    private readonly onRetry: (ms: number) => void = () => {},
  ) {}

  feed(chunk: string): void {
    if (!this.started) {
      this.started = true;
      if (chunk.startsWith("﻿")) chunk = chunk.slice(1);
    }
    this.buffer += chunk;
    let start = 0;
    for (let i = 0; i < this.buffer.length; i++) {
      const ch = this.buffer[i];
      if (ch !== "\n" && ch !== "\r") continue;
      if (ch === "\r" && i === this.buffer.length - 1) break; // wait: it may be half of \r\n
      this.line(this.buffer.slice(start, i));
      if (ch === "\r" && this.buffer[i + 1] === "\n") i++;
      start = i + 1;
    }
    this.buffer = this.buffer.slice(start);
  }

  /** The stream ended: a trailing lone \r still ends a line; an unfinished event is dropped. */
  end(): void {
    if (this.buffer.endsWith("\r")) this.line(this.buffer.slice(0, -1));
    this.buffer = "";
    this.data = [];
    this.type = "";
  }

  private line(line: string): void {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return; // comment (": ping")
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    switch (field) {
      case "data":
        this.data.push(value);
        break;
      case "event":
        this.type = value;
        break;
      case "id":
        if (!value.includes("\0")) this.lastEventId = value;
        break;
      case "retry":
        if (/^\d+$/.test(value)) this.onRetry(Number(value));
        break;
      default:
        break; // unknown fields are ignored
    }
  }

  private dispatch(): void {
    if (this.data.length === 0) {
      this.type = "";
      return;
    }
    const event = { id: this.lastEventId, event: this.type || "message", data: this.data.join("\n") };
    this.data = [];
    this.type = "";
    this.onEvent(event);
  }
}

export type StreamOpenInfo = {
  /** Not the first connection of this run. */
  reconnect: boolean;
  /** Sent a Last-Event-ID, so the server replays what was missed (or sends resync). */
  resumed: boolean;
};

export type EventStreamOptions = {
  /** Opens the stream; throws (or rejects) for a failed response. Called with a fresh token each time. */
  open: (lastEventId: string | null, signal: AbortSignal) => Promise<ReadableStream<Uint8Array>>;
  onEvent: (event: SseEvent) => void;
  onOpen?: (info: StreamOpenInfo) => void;
  onError?: (error: unknown) => void;
  /** The stream dropped, or an attempt failed: it waits, then tries again. */
  onReconnecting?: () => void;
  signal: AbortSignal;
  minDelayMs?: number;
  maxDelayMs?: number;
  /** Injected in tests. */
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
  random?: () => number;
};

function abortableSleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
    signal.addEventListener("abort", done, { once: true });
  });
}

/** Delay before reconnect attempt n (0-based): the server's retry value or 1 s, doubling, at most 30 s, ±20 %. */
export function reconnectDelay(attempt: number, baseMs: number, maxMs: number, random: () => number): number {
  const exact = Math.min(maxMs, baseMs * 2 ** attempt);
  return Math.round(exact * (0.8 + 0.4 * random()));
}

/** Keep a stream open until the signal aborts, reconnecting with Last-Event-ID after any drop. */
export async function runEventStream(options: EventStreamOptions): Promise<void> {
  const { open, onEvent, onOpen, onError, onReconnecting, signal } = options;
  const minDelay = options.minDelayMs ?? 1_000;
  const maxDelay = options.maxDelayMs ?? 30_000;
  const sleep = options.sleep ?? abortableSleep;
  const random = options.random ?? Math.random;

  let lastEventId: string | null = null;
  let serverRetry: number | null = null;
  let attempt = 0;
  let connections = 0;

  while (!signal.aborted) {
    try {
      const stream = await open(lastEventId, signal);
      onOpen?.({ reconnect: connections > 0, resumed: lastEventId !== null });
      connections++;
      attempt = 0;
      const parser = new SseParser(
        (event) => {
          lastEventId = event.id ?? lastEventId;
          onEvent(event);
        },
        (ms) => {
          serverRetry = ms;
        },
      );
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          parser.feed(decoder.decode(value, { stream: true }));
          lastEventId = parser.lastEventId ?? lastEventId;
        }
        parser.feed(decoder.decode());
        parser.end();
      } finally {
        reader.releaseLock?.();
      }
    } catch (error) {
      if (signal.aborted) return;
      onError?.(error);
    }
    if (signal.aborted) return;
    onReconnecting?.();
    const base = Math.max(minDelay, serverRetry ?? minDelay);
    await sleep(reconnectDelay(attempt, base, maxDelay, random), signal);
    attempt++;
  }
}
