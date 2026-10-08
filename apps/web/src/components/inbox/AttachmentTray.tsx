"use client";

import { AlertCircle, FileText, RotateCw, X } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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

/** F-07: 64 px thumbnails with a progress bar (Progress); Send waits until every upload finishes. */
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
        <Tooltip key={item.id}>
          <TooltipTrigger asChild>
        <li
          className={cn(
            "relative size-16 shrink-0 overflow-hidden rounded-lg border bg-field",
            item.status === "failed" ? "border-danger" : "border-line",
          )}
          data-status={item.status}
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
            <span className="absolute inset-0 flex items-end bg-media-scrim/50 p-2">
              <Progress aria-label={`Uploading ${item.file.name}`} value={Math.round(item.progress * 100)} />
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
          </TooltipTrigger>
          <TooltipContent>{item.error ?? item.file.name}</TooltipContent>
        </Tooltip>
      ))}
    </ul>
  );
}
