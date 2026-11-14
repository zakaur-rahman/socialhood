/**
 * The browser's half of a direct YouTube upload (S-4): the API opens a resumable session and hands
 * back its one-time address; this sends the file there in pieces. Plain fetch to Google, never the
 * API client, so our auth headers never reach Google (the address itself is the credential).
 *
 * Each piece is a PUT with ``Content-Range: bytes start-end/total``. YouTube answers 308 with a
 * ``Range`` header saying how much it holds, until the last piece, answered 200/201 with the video
 * resource. After a dropped connection or a 5xx, an empty PUT with ``bytes * /total`` asks how much
 * arrived, and the upload carries on from there (Google's resumable upload protocol).
 */

export type UploadToYouTubeOptions = {
  uploadUrl: string;
  file: Blob;
  /** The piece size the API asked for (a multiple of 256 KiB, 8 MB by default). */
  chunkBytes: number;
  onProgress?: (sent: number, total: number) => void;
  signal?: AbortSignal;
  /** Retries in a row after network errors or 5xx before giving up. */
  retries?: number;
  /** Tests pass fakes. */
  fetch?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
};

export class YouTubeUploadError extends Error {
  constructor(
    message: string,
    readonly status: number | null = null,
  ) {
    super(message);
    this.name = "YouTubeUploadError";
  }
}

export type Uploader = (options: UploadToYouTubeOptions) => Promise<string>;

const realSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** "bytes=0-524287" → 524288, the offset to send next; no header means nothing arrived. */
export function nextOffset(range: string | null): number {
  const match = range ? /bytes=\d+-(\d+)/.exec(range) : null;
  return match ? Number(match[1]) + 1 : 0;
}

async function videoIdOf(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { id?: unknown } | null;
  if (typeof body?.id !== "string" || !body.id) throw new YouTubeUploadError("YouTube finished the upload but sent no video id.", response.status);
  return body.id;
}

/** Sends the file and resolves with YouTube's video id. Rejects with an AbortError when aborted. */
export async function uploadToYouTube({
  uploadUrl,
  file,
  chunkBytes,
  onProgress,
  signal,
  retries = 5,
  fetch: send = globalThis.fetch.bind(globalThis),
  sleep = realSleep,
}: UploadToYouTubeOptions): Promise<string> {
  const total = file.size;
  if (total === 0) throw new YouTubeUploadError("The file is empty.");
  const chunk = Math.max(1, chunkBytes);
  let offset = 0;
  let failures = 0;
  // After a failure we don't know what arrived: ask before sending again.
  let ask = false;

  while (true) {
    signal?.throwIfAborted();
    let response: Response;
    try {
      if (ask) {
        response = await send(uploadUrl, { method: "PUT", headers: { "Content-Range": `bytes */${total}` }, signal });
      } else {
        const end = Math.min(offset + chunk, total);
        response = await send(uploadUrl, {
          method: "PUT",
          headers: { "Content-Range": `bytes ${offset}-${end - 1}/${total}` },
          body: file.slice(offset, end),
          signal,
        });
      }
    } catch (error) {
      if (signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) throw error;
      response = new Response(null, { status: 599 }); // a dropped connection: retried like a 5xx
    }

    if (response.status === 200 || response.status === 201) {
      onProgress?.(total, total);
      return videoIdOf(response);
    }
    if (response.status === 308) {
      offset = nextOffset(response.headers.get("Range"));
      ask = false;
      failures = 0;
      onProgress?.(offset, total);
      continue;
    }
    if (response.status >= 500) {
      failures += 1;
      if (failures > retries) throw new YouTubeUploadError("The connection to YouTube keeps dropping. Try again.", response.status);
      await sleep(Math.min(30_000, 1000 * 2 ** (failures - 1)));
      ask = true;
      continue;
    }
    // 404/410: the session expired; anything else 4xx won't get better by retrying.
    throw new YouTubeUploadError(
      response.status === 404 || response.status === 410
        ? "This upload link expired. Try again to start a new one."
        : "YouTube didn't accept the file.",
      response.status,
    );
  }
}

/** Width, height and length of a local video, read by the browser; null when it can't tell. */
export function readVideoMeta(file: Blob): Promise<{ width: number; height: number; duration_s: number } | null> {
  if (typeof document === "undefined" || typeof URL.createObjectURL !== "function") return Promise.resolve(null);
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    const done = (value: { width: number; height: number; duration_s: number } | null) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    video.preload = "metadata";
    video.onloadedmetadata = () =>
      done({ width: video.videoWidth, height: video.videoHeight, duration_s: Number.isFinite(video.duration) ? video.duration : 0 });
    video.onerror = () => done(null);
    video.src = url;
  });
}
