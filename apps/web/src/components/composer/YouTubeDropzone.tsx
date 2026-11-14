"use client";

import { AlertCircle, CheckCircle2, FileVideo, RotateCw, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";

import { YouTubeGlyph } from "@/components/connections/YouTubeGlyph";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { youtubeCopy } from "@/lib/copy";
import { checkYouTubeFile, YOUTUBE_VIDEO_EXTENSIONS } from "@/lib/publishing/rules";
import { cn } from "@/lib/utils";
import { uploadToYouTube, type Uploader } from "@/lib/youtube/upload";

export const YOUTUBE_DROPZONE_ID = "composer-youtube-file";

export type YouTubeUploadPhase = "idle" | "uploading" | "done" | "failed";

export type YouTubeUploadState = {
  phase: YouTubeUploadPhase;
  sent: number;
  total: number;
  /** Bytes a second since this upload started, once there is something to measure. */
  speed: number | null;
  error: string | null;
};

const IDLE: YouTubeUploadState = { phase: "idle", sent: 0, total: 0, speed: null, error: null };

/**
 * One video on its way to YouTube (S-4): the picked file, the upload's progress and speed, and a
 * warning before the tab closes mid-upload. ``run`` sends the file to an upload address the API
 * opened and resolves with the video id; it rejects (and the state says why) when it fails.
 */
export function useYouTubeUpload(uploader: Uploader = uploadToYouTube) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<YouTubeUploadState>(IDLE);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    if (state.phase !== "uploading") return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [state.phase]);

  // Leaving the page stops the upload; YouTube keeps what arrived until the session expires.
  useEffect(() => () => controller.current?.abort(), []);

  const pick = useCallback((next: File | null) => {
    controller.current?.abort();
    setFile(next);
    setState(IDLE);
  }, []);

  const run = useCallback(
    async (uploadUrl: string, chunkBytes: number, chosen: File | null = file): Promise<string> => {
      if (!chosen) throw new Error("Choose a video first.");
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;
      const started = Date.now();
      let first: number | null = null;
      setState({ phase: "uploading", sent: 0, total: chosen.size, speed: null, error: null });
      try {
        const videoId = await uploader({
          uploadUrl,
          file: chosen,
          chunkBytes,
          signal: abort.signal,
          onProgress: (sent, total) => {
            // A resumed upload starts past zero: speed counts only what this run sent.
            first ??= sent;
            const seconds = (Date.now() - started) / 1000;
            setState({ phase: "uploading", sent, total, speed: seconds > 0.5 ? (sent - first) / seconds : null, error: null });
          },
        });
        setState({ phase: "done", sent: chosen.size, total: chosen.size, speed: null, error: null });
        return videoId;
      } catch (error) {
        if (!abort.signal.aborted) {
          setState((current) => ({ ...current, phase: "failed", speed: null, error: error instanceof Error ? error.message : "The upload didn't finish." }));
        }
        throw error;
      } finally {
        if (controller.current === abort) controller.current = null;
      }
    },
    [file, uploader],
  );

  /** A failure outside the upload itself (opening the session, confirming it) shows in the same box. */
  const failWith = useCallback((message: string) => setState((current) => ({ ...current, phase: "failed", speed: null, error: message })), []);

  return { file, state, pick, run, failWith, busy: state.phase === "uploading" };
}

export type YouTubeUpload = ReturnType<typeof useYouTubeUpload>;

const MB = 1024 * 1024;

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * MB) return `${(bytes / (1024 * MB)).toFixed(1)} GB`;
  if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

const ACCEPT = ["video/*", ...YOUTUBE_VIDEO_EXTENSIONS.map((extension) => `.${extension}`)].join(",");

/**
 * The YouTube dropzone (S-4): drop or pick one video; it uploads straight to YouTube from the
 * browser, never through Amplychat or Cloudinary. Shows the file's name and size, then progress and
 * speed, then the channel it reached; a failed upload offers Try again. The composer starts the
 * upload with Schedule (the post is saved first); the AI-app upload page starts it on pick.
 */
export function YouTubeDropzone({
  upload,
  channelName,
  onRetry,
  onPicked,
  readOnly = false,
  uploaded = false,
  notice,
}: {
  upload: YouTubeUpload;
  channelName: string;
  /** Try again after a failure (the caller opens a new session and runs the upload). */
  onRetry?: () => void;
  /** Called with a valid file once it is picked; the AI-app page starts the upload here. */
  onPicked?: (file: File) => void;
  readOnly?: boolean;
  /** The video is already on YouTube (a scheduled direct upload): no file is needed. */
  uploaded?: boolean;
  notice?: string | null;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const { file, state } = upload;
  const busy = state.phase === "uploading";
  const percent = state.total ? Math.floor((state.sent / state.total) * 100) : 0;

  const take = (files: File[]) => {
    if (readOnly || busy) return;
    if (files.length > 1) {
      setProblem("YouTube takes one video per post. Choose one file.");
      return;
    }
    const next = files[0];
    if (!next) return;
    const why = checkYouTubeFile(next);
    setProblem(why);
    if (why) return;
    upload.pick(next);
    onPicked?.(next);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setOver(false);
    take(Array.from(event.dataTransfer.files));
  };

  if (uploaded && state.phase !== "uploading") {
    return (
      <div id={YOUTUBE_DROPZONE_ID} tabIndex={-1} className="flex items-center gap-3 rounded-xl border border-line bg-field p-4" data-testid="youtube-dropzone">
        <CheckCircle2 className="size-5 shrink-0 text-success" aria-hidden />
        <p className="text-sm">
          The video is on YouTube, on <span className="font-medium">{channelName}</span>. Changes to the title, description, privacy or time
          are sent to YouTube when you save.
        </p>
      </div>
    );
  }

  return (
    <div id={YOUTUBE_DROPZONE_ID} tabIndex={-1} className="space-y-2" data-testid="youtube-dropzone">
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        aria-label="Choose a video for YouTube"
        data-testid="youtube-file-input"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          take(files);
        }}
      />
      <div
        onDragOver={(event) => {
          if (readOnly || busy) return;
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-xl border border-dashed p-4 transition-[background-color,border-color] duration-fast ease-standard",
          over ? "border-brand bg-hover" : "border-line-strong bg-field",
        )}
      >
        {file ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <FileVideo className="size-5 shrink-0 text-fg-secondary" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium" data-testid="youtube-file-name">
                  {file.name}
                </p>
                <p className="text-xs text-fg-secondary tabular-nums">{formatBytes(file.size)}</p>
              </div>
              {!busy && !readOnly && state.phase !== "done" ? (
                <Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove ${file.name}`} onClick={() => upload.pick(null)}>
                  <X className="size-3.5" aria-hidden />
                </Button>
              ) : null}
            </div>
            {busy ? (
              <div className="space-y-1">
                <Progress aria-label={`Uploading ${file.name} to YouTube`} value={percent} valueText={`${percent}%`} />
                <p className="text-xs text-fg-secondary tabular-nums" role="status" aria-live="polite">
                  Uploading to YouTube: {percent}% · {formatBytes(state.sent)} of {formatBytes(state.total)}
                  {state.speed ? ` · ${formatBytes(state.speed)}/s` : ""}. Keep this tab open.
                </p>
              </div>
            ) : state.phase === "done" ? (
              <p className="flex items-center gap-1.5 text-sm" role="status">
                <CheckCircle2 className="size-4 text-success" aria-hidden /> Uploaded to {channelName}.
              </p>
            ) : state.phase === "failed" ? (
              <div className="flex flex-wrap items-center gap-2" role="alert">
                <AlertCircle className="size-4 text-danger" aria-hidden />
                <p className="flex-1 text-sm text-danger-fg">{state.error ?? "The upload didn't finish."}</p>
                {onRetry ? (
                  <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
                    <RotateCw aria-hidden /> Try again
                  </Button>
                ) : null}
              </div>
            ) : (
              <p className="text-xs text-fg-secondary">Ready. It uploads to {channelName} when you schedule the post.</p>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <YouTubeGlyph className="size-6 text-youtube" />
            <p className="text-sm font-medium">Drop a video here</p>
            <Button type="button" variant="secondary" size="lg" disabled={readOnly} onClick={() => input.current?.click()} data-focus-target>
              <Upload aria-hidden /> Choose a video
            </Button>
            <p className="text-xs text-fg-secondary">One video, any size YouTube takes. It goes straight to {channelName}.</p>
          </div>
        )}
      </div>
      {problem || notice ? (
        <p role="alert" className="text-xs text-danger-fg">
          {problem ?? notice}
        </p>
      ) : null}
      {busy ? <p className="sr-only">{youtubeCopy.leaveWarning}</p> : null}
    </div>
  );
}
