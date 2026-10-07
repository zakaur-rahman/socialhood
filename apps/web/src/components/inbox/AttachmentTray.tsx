"use client";

import { AlertCircle, FileText, RotateCw, X } from "lucide-react";

import type { MediaAsset } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type TrayItem = {
  id: string;
  file: File;
  /** Object URL for image previews. */
  previewUrl: string | null;
  progress: number;
  status: "uploading" | "done" | "failed";
  asset?: MediaAsset;
  error?: string;
};

function ProgressRing({ value }: { value: number }) {
  const r = 14;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 36 36" className="size-9 -rotate-90" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} aria-label="Uploading">
      <circle cx="18" cy="18" r={r} fill="none" strokeWidth="3" className="stroke-line-strong" />
      <circle
        cx="18"
        cy="18"
        r={r}
        fill="none"
        strokeWidth="3"
        strokeLinecap="round"
        className="stroke-brand transition-[stroke-dashoffset]"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - value)}
      />
    </svg>
  );
}

/** F-07: 64 px thumbnails with a progress ring; Send waits until every upload finishes. */
export function AttachmentTray({
  items,
  onRemove,
  onRetry,
}: {
  items: TrayItem[];
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <ul aria-label="Attachments" className="mb-2 flex gap-2 overflow-x-auto pb-1">
      {items.map((item) => (
        <li
          key={item.id}
          className={cn(
            "relative size-16 shrink-0 overflow-hidden rounded-lg border bg-field",
            item.status === "failed" ? "border-danger" : "border-line",
          )}
          data-status={item.status}
          title={item.error ?? item.file.name}
        >
          {item.previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- a local object URL
            <img src={item.previewUrl} alt={item.file.name} className="size-full object-cover" />
          ) : (
            <span className="flex size-full flex-col items-center justify-center gap-1 p-1 text-fg-secondary">
              <FileText className="size-5" aria-hidden />
              <span className="w-full truncate text-center text-2xs">{item.file.name}</span>
            </span>
          )}
          {item.status === "uploading" ? (
            <span className="absolute inset-0 grid place-items-center bg-media-scrim/50">
              <ProgressRing value={item.progress} />
            </span>
          ) : null}
          {item.status === "failed" ? (
            <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-media-scrim/60 text-danger-fg">
              <AlertCircle className="size-4" aria-hidden />
              <button
                type="button"
                onClick={() => onRetry(item.id)}
                aria-label={`Retry uploading ${item.file.name}`}
                className="grid size-6 place-items-center rounded-full bg-pressed text-fg hover:bg-raised-hover"
              >
                <RotateCw className="size-3" aria-hidden />
              </button>
              <span className="sr-only">{item.error ?? "Upload failed"}</span>
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => onRemove(item.id)}
            aria-label={`Remove ${item.file.name}`}
            className="absolute top-0.5 right-0.5 grid size-5 place-items-center rounded-full bg-media-scrim/70 text-on-brand hover:bg-media-scrim"
          >
            <X className="size-3" aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}
