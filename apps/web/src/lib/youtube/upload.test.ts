import { describe, expect, it, vi } from "vitest";

import { nextOffset, uploadToYouTube, YouTubeUploadError } from "./upload";

const URL_ = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=abc";

function file(size: number): Blob {
  return new Blob([new Uint8Array(size)]);
}

const resume = (last: number) => new Response(null, { status: 308, headers: { Range: `bytes=0-${last}` } });
const done = (id = "vid123") => new Response(JSON.stringify({ id, kind: "youtube#video" }), { status: 200 });

type Sent = { range: string; bytes: number | null; auth: string | null };

function fakeFetch(answers: (Response | Error)[]) {
  const sent: Sent[] = [];
  const fetch = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers);
    sent.push({
      range: headers.get("Content-Range") ?? "",
      bytes: init?.body instanceof Blob ? init.body.size : null,
      auth: headers.get("Authorization"),
    });
    const next = answers.shift();
    if (!next) throw new Error("no more answers");
    if (next instanceof Error) throw next;
    return next;
  });
  return { fetch: fetch as unknown as typeof globalThis.fetch, sent };
}

describe("nextOffset", () => {
  it("reads YouTube's Range header", () => {
    expect(nextOffset("bytes=0-524287")).toBe(524288);
    expect(nextOffset(null)).toBe(0);
  });
});

describe("uploadToYouTube", () => {
  it("sends the file in pieces, follows 308s and returns the video id", async () => {
    const { fetch, sent } = fakeFetch([resume(3), resume(7), done()]);
    const progress: number[] = [];
    const id = await uploadToYouTube({ uploadUrl: URL_, file: file(10), chunkBytes: 4, fetch, onProgress: (n) => progress.push(n) });
    expect(id).toBe("vid123");
    expect(sent.map((s) => s.range)).toEqual(["bytes 0-3/10", "bytes 4-7/10", "bytes 8-9/10"]);
    expect(sent.map((s) => s.bytes)).toEqual([4, 4, 2]);
    expect(progress).toEqual([4, 8, 10]);
    // Our API's token never goes to Google.
    expect(sent.every((s) => s.auth === null)).toBe(true);
  });

  it("asks how much arrived after a dropped connection, then resumes from there", async () => {
    const sleep = vi.fn(async () => {});
    const { fetch, sent } = fakeFetch([resume(3), new TypeError("Failed to fetch"), resume(5), done("v2")]);
    const id = await uploadToYouTube({ uploadUrl: URL_, file: file(10), chunkBytes: 4, fetch, sleep });
    expect(id).toBe("v2");
    expect(sent.map((s) => s.range)).toEqual(["bytes 0-3/10", "bytes 4-7/10", "bytes */10", "bytes 6-9/10"]);
    expect(sent[2].bytes).toBeNull();
    expect(sleep).toHaveBeenCalledWith(1000);
  });

  it("retries a 5xx with backoff and gives up after the retries", async () => {
    const sleep = vi.fn(async () => {});
    const { fetch } = fakeFetch([new Response(null, { status: 503 }), new Response(null, { status: 503 }), new Response(null, { status: 503 })]);
    await expect(uploadToYouTube({ uploadUrl: URL_, file: file(10), chunkBytes: 4, fetch, sleep, retries: 2 })).rejects.toBeInstanceOf(
      YouTubeUploadError,
    );
    expect(sleep.mock.calls.map((call) => (call as unknown[])[0])).toEqual([1000, 2000]);
  });

  it("stops on an expired session without retrying", async () => {
    const { fetch, sent } = fakeFetch([new Response(null, { status: 404 })]);
    await expect(uploadToYouTube({ uploadUrl: URL_, file: file(10), chunkBytes: 4, fetch })).rejects.toThrow("expired");
    expect(sent).toHaveLength(1);
  });

  it("stops when aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const { fetch, sent } = fakeFetch([done()]);
    await expect(uploadToYouTube({ uploadUrl: URL_, file: file(10), chunkBytes: 4, fetch, signal: controller.signal })).rejects.toThrow();
    expect(sent).toHaveLength(0);
  });
});
