"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/errors";
import { useApi } from "@/lib/api/provider";
import type { MediaAsset } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { UploadError, uploadAsset } from "@/lib/media/upload";
import { postFileKind, UNSUPPORTED_MEDIA } from "@/lib/publishing/rules";
import { uuid } from "@/lib/uuid";

/** Signed upload of one file (TR-MED-01); tests pass a fake. */
export type Uploader = (
  file: File,
  options: { onProgress: (fraction: number) => void; signal: AbortSignal },
) => Promise<MediaAsset>;

/**
 * One file on its way into the post. "uploading" while bytes go to storage (progress is the
 * share actually sent, FR-PUB-13); "processing" once they are all sent and the API checks and
 * registers the file; "failed" with the reason and Retry.
 */
export type UploadItem = {
  id: string;
  file: File;
  kind: "image" | "video";
  previewUrl: string | null;
  progress: number;
  status: "uploading" | "processing" | "failed";
  error: string | null;
  /** The asset a crop replaces; null for a new file. */
  replaces: string | null;
};

function failureMessage(error: unknown): string {
  if (error instanceof UploadError) return error.message;
  if (error instanceof ApiError && (error.code === "unsupported_media" || error.status === 415)) return UNSUPPORTED_MEDIA;
  return errorMessage(error);
}

/**
 * The composer's uploads (UX-SCR-13 media tray). A finished upload leaves this list and is handed
 * to ``onUploaded``, which puts the asset into the post.
 */
export function useMediaUploads(
  wid: string,
  { upload: injected, onUploaded }: { upload?: Uploader; onUploaded: (asset: MediaAsset, item: UploadItem) => void },
) {
  const api = useApi();
  const [items, setItems] = useState<UploadItem[]>([]);
  const controllers = useRef(new Map<string, AbortController>());
  const itemsRef = useRef(items);
  const done = useRef(onUploaded);
  useEffect(() => {
    itemsRef.current = items;
    done.current = onUploaded;
  });

  const upload: Uploader = useCallback(
    (file, options) => (injected ? injected(file, options) : uploadAsset(api, wid, file, { ...options, purpose: "post" })),
    [api, injected, wid],
  );

  const patch = (id: string, change: Partial<UploadItem>) =>
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...change } : item)));

  const release = (item: UploadItem) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  };

  const start = (item: UploadItem) => {
    const controller = new AbortController();
    controllers.current.set(item.id, controller);
    upload(item.file, {
      signal: controller.signal,
      onProgress: (fraction) =>
        patch(item.id, fraction >= 1 ? { progress: 1, status: "processing" } : { progress: Math.max(0, fraction) }),
    })
      .then((asset) => {
        if (controller.signal.aborted) return;
        const current = itemsRef.current.find((entry) => entry.id === item.id) ?? item;
        release(current);
        setItems((list) => list.filter((entry) => entry.id !== item.id));
        done.current(asset, current);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        patch(item.id, { status: "failed", error: failureMessage(error) });
      })
      .finally(() => controllers.current.delete(item.id));
  };

  /** Start uploading a checked file; ``replaces`` names the asset a crop takes the place of. */
  const add = (file: File, replaces: string | null = null) => {
    let previewUrl: string | null = null;
    const kind = postFileKind(file) ?? "image";
    if (kind === "image") {
      try {
        previewUrl = URL.createObjectURL(file);
      } catch {
        previewUrl = null; // no preview; an icon shows instead
      }
    }
    const item: UploadItem = {
      id: uuid(),
      file,
      kind,
      previewUrl,
      progress: 0,
      status: "uploading",
      error: null,
      replaces,
    };
    setItems((current) => [...current, item]);
    start(item);
  };

  const retry = (id: string) => {
    const item = itemsRef.current.find((entry) => entry.id === id);
    if (!item) return;
    patch(id, { status: "uploading", progress: 0, error: null });
    start({ ...item, status: "uploading", progress: 0, error: null });
  };

  /** Cancel an upload, or drop a failed one. */
  const remove = (id: string) => {
    const item = itemsRef.current.find((entry) => entry.id === id);
    controllers.current.get(id)?.abort();
    if (item) release(item);
    setItems((current) => current.filter((entry) => entry.id !== id));
  };

  useEffect(() => {
    const map = controllers.current;
    return () => {
      for (const controller of map.values()) controller.abort();
      for (const item of itemsRef.current) if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    };
  }, []);

  /** Uploads still sending or processing: Schedule waits for them. */
  const busy = items.some((item) => item.status !== "failed");
  return { items, add, retry, remove, busy };
}
