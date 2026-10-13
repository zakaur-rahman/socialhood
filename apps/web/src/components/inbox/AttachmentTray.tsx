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
    // pt-2 pr-2: room for the remove button's corner overhang, which the scroller would clip.
    <ul aria-label="Attachments" className="mb-2 flex gap-2 overflow-x-auto pt-2 pr-2 pb-1">
      {items.map((item) => (
        <Tooltip key={item.id}>
          <TooltipTrigger asChild>
            <li
              className={cn("relative size-16 shrink-0 rounded-lg border bg-field", item.status === "failed" ? "border-danger" : "border-line")}
              data-status={item.status}
            >
              {/* The tile's picture and overlays are clipped to its rounded corners; the buttons are not,
                  so their 40 px touch areas (a pseudo-element) are not cut off by the tile (UI-051). */}
              <div className="absolute inset-0 overflow-hidden rounded-[inherit]">
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
                  <span className="absolute inset-0 bg-media-scrim/60" aria-hidden />
                ) : null}
              </div>
              {item.status === "failed" ? (
                <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-danger-fg">
                  <AlertCircle className="size-4" aria-hidden />
                  <button
                    type="button"
                    onClick={() => onRetry(item.id)}
                    aria-label={`Retry uploading ${item.file.name}`}
                    className="relative grid size-6 place-items-center rounded-lg bg-pressed text-fg hover:bg-raised-hover after:absolute after:-inset-2 after:content-['']"
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
                className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-lg bg-media-scrim/70 text-on-brand after:absolute after:-inset-2.5 after:content-[''] hover:bg-media-scrim"
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
