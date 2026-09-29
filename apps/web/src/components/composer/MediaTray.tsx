"use client";

import { AlertCircle, Crop, FileVideo, GripVertical, ImagePlus, Library, Loader2, RotateCw, X } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  assetLabel,
  cropNeeded,
  formatDuration,
  FORMAT_LABEL,
  MAX_ASSETS,
  POST_FILE_ACCEPT,
  videoTooLong,
  type AssetInfo,
} from "@/lib/publishing/rules";
import type { PostFormat } from "@/lib/publishing/types";
import { cn } from "@/lib/utils";

import { Section } from "./Section";
import type { UploadItem } from "./use-media-uploads";

export const MEDIA_ADD_ID = "composer-media-add";

export function mediaTileId(assetId: string): string {
  return `composer-media-${assetId}`;
}

/** Move one item within the order. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(Math.max(0, Math.min(to, next.length)), 0, item);
  return next;
}

export type TrayEntry = { asset: AssetInfo; replacing: UploadItem | null };

type Drag = { from: number; pointerId: number; drop: number };

function ProgressBar({ item, label }: { item: UploadItem; label: string }) {
  const percent = Math.round(item.progress * 100);
  return (
    <div className="absolute inset-x-0 bottom-0 space-y-1 bg-canvas/80 p-1.5">
      <div
        role="progressbar"
        aria-label={`Uploading ${label}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={item.status === "processing" ? "Processing" : `${percent}%`}
        className="h-1.5 overflow-hidden rounded-full bg-white/15"
      >
        <div className="bg-brand-gradient-decor h-full rounded-full transition-[width]" style={{ width: `${percent}%` }} />
      </div>
      <p className="flex items-center gap-1 text-[11px] text-fg tabular-nums">
        {item.status === "processing" ? (
          <>
            <Loader2 className="size-3 animate-spin" aria-hidden /> Processing…
          </>
        ) : (
          `${percent}%`
        )}
      </p>
    </div>
  );
}

function Thumb({ asset }: { asset: AssetInfo }) {
  if (asset.resource_type === "video" && !asset.thumbnail_url) {
    return asset.url ? (
      <video src={asset.url} muted playsInline preload="metadata" aria-hidden className="size-full object-cover" />
    ) : (
      <span className="grid size-full place-items-center text-fg-secondary">
        <FileVideo className="size-6" aria-hidden />
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element -- uploaded media of any size
  return <img src={asset.thumbnail_url ?? asset.url} alt="" className="size-full object-cover" />;
}

/**
 * UX-SCR-13 Media: uploads with real progress, the library, drag (or arrow keys) to reorder, crop
 * for out-of-range images, remove. The format the media make is shown beside the title.
 */
export function MediaTray({
  entries,
  uploads,
  format,
  notice,
  readOnly = false,
  onFiles,
  onOpenLibrary,
  onRemove,
  onMove,
  onCrop,
  onRetryUpload,
  onRemoveUpload,
}: {
  entries: TrayEntry[];
  /** New files on their way (crops show on the tile they replace). */
  uploads: UploadItem[];
  format: PostFormat | null;
  /** Why the last picked files were refused. */
  notice: string | null;
  readOnly?: boolean;
  onFiles: (files: File[]) => void;
  onOpenLibrary: () => void;
  onRemove: (assetId: string) => void;
  onMove: (from: number, to: number) => void;
  onCrop: (assetId: string) => void;
  onRetryUpload: (id: string) => void;
  onRemoveUpload: (id: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const tiles = useRef(new Map<string, HTMLLIElement>());
  const hintId = useId();
  const [drag, setDrag] = useState<Drag | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const count = entries.length + uploads.length;
  const full = count >= MAX_ASSETS;

  const commit = (from: number, to: number) => {
    if (readOnly || to === from || to < 0 || to >= entries.length) return;
    onMove(from, to);
    setAnnouncement(`Moved ${assetLabel(entries[from].asset, from)} to position ${to + 1} of ${entries.length}.`);
  };

  /** The gap under the pointer in reading order: 0 is before the first tile, n after the last. */
  const dropIndexAt = (x: number, y: number): number => {
    for (let index = 0; index < entries.length; index += 1) {
      const rect = tiles.current.get(entries[index].asset.id)?.getBoundingClientRect();
      if (!rect) continue;
      if (y < rect.top || (y <= rect.bottom && x < rect.left + rect.width / 2)) return index;
    }
    return entries.length;
  };

  const handleProps = (index: number) => ({
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
      const step = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : 0;
      if (!step) return;
      event.preventDefault();
      commit(index, index + step);
    },
    onPointerDown: (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (readOnly || event.button !== 0) return;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      setDrag({ from: index, pointerId: event.pointerId, drop: index });
    },
    onPointerMove: (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      const drop = dropIndexAt(event.clientX, event.clientY);
      if (drop !== drag.drop) setDrag({ ...drag, drop });
    },
    onPointerUp: (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      const to = drag.drop > drag.from ? drag.drop - 1 : drag.drop;
      setDrag(null);
      commit(drag.from, to);
    },
    onPointerCancel: () => setDrag(null),
  });

  const formatText =
    format === "carousel" ? `${FORMAT_LABEL.carousel} · ${entries.length} items` : format ? FORMAT_LABEL[format] : null;

  return (
    <Section
      id="composer-media"
      title="Media"
      aside={
        formatText ? (
          <span data-testid="post-format" className="rounded-full bg-raised px-2.5 py-0.5 text-xs font-medium text-fg-secondary">
            {formatText}
          </span>
        ) : null
      }
    >
      <p id={hintId} className="sr-only">
        Drag a handle, or press the arrow keys on it, to change the order.
      </p>
      {count > 0 ? (
        <ul aria-label="Post media" className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          {entries.map(({ asset, replacing }, index) => {
            const label = assetLabel(asset, index);
            const crop = cropNeeded(asset);
            const tooLong = videoTooLong(asset);
            const dragging = drag?.from === index;
            const gap = drag ? drag.drop : -1;
            const marker = drag && gap !== drag.from && gap !== drag.from + 1 ? (gap === index ? "before" : gap === entries.length && index === entries.length - 1 ? "after" : null) : null;
            return (
              <li
                key={asset.id}
                id={mediaTileId(asset.id)}
                tabIndex={-1}
                ref={(node) => {
                  if (node) tiles.current.set(asset.id, node);
                  else tiles.current.delete(asset.id);
                }}
                data-testid="media-tile"
                data-crop={crop ?? undefined}
                aria-label={label}
                className={cn(
                  "relative flex flex-col rounded-lg border bg-field outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  crop || tooLong ? "border-danger" : "border-line",
                  dragging && "opacity-60",
                  marker === "before" && "before:absolute before:inset-y-1 before:-left-1.5 before:z-10 before:w-0.5 before:rounded-full before:bg-brand",
                  marker === "after" && "after:absolute after:inset-y-1 after:-right-1.5 after:z-10 after:w-0.5 after:rounded-full after:bg-brand",
                )}
              >
                <div className="relative aspect-square overflow-hidden rounded-t-lg">
                  <Thumb asset={asset} />
                  <span className="absolute top-1 left-1 grid min-w-5 place-items-center rounded-md bg-canvas/80 px-1 text-[11px] font-semibold tabular-nums">
                    {index + 1}
                  </span>
                  {asset.resource_type === "video" && asset.duration_s ? (
                    <span className="absolute top-1 right-1 rounded-md bg-canvas/80 px-1 text-[11px] tabular-nums">
                      {formatDuration(asset.duration_s)}
                    </span>
                  ) : null}
                  {crop ? (
                    <button
                      type="button"
                      data-focus-target
                      onClick={() => onCrop(asset.id)}
                      className="absolute inset-x-1 bottom-1 flex min-h-10 items-center justify-center gap-1 rounded-md bg-danger-fill px-1 text-[11px] font-medium text-white sm:min-h-7"
                    >
                      <Crop className="size-3" aria-hidden /> Crop needed
                      <span className="sr-only">: {label}</span>
                    </button>
                  ) : tooLong ? (
                    <span className="absolute inset-x-1 bottom-1 rounded-md bg-danger-fill px-1 py-0.5 text-center text-[11px] font-medium text-white">
                      Over 90 s
                    </span>
                  ) : null}
                  {replacing ? (
                    <UploadOverlay item={replacing} label={`the crop of ${label}`} onRetry={onRetryUpload} onRemove={onRemoveUpload} />
                  ) : null}
                </div>
                <div className="flex items-center justify-between gap-1 p-1">
                  <button
                    type="button"
                    aria-label={`Move ${label}`}
                    aria-describedby={hintId}
                    className="grid size-10 touch-none cursor-grab place-items-center rounded-md text-fg-secondary hover:bg-white/5 hover:text-fg active:cursor-grabbing sm:size-7"
                    {...handleProps(index)}
                  >
                    <GripVertical className="size-3.5" aria-hidden />
                  </button>
                  <div className="flex gap-1">
                    {asset.resource_type === "image" && !crop ? (
                      <button
                        type="button"
                        aria-label={`Crop ${label}`}
                        onClick={() => onCrop(asset.id)}
                        className="grid size-10 place-items-center rounded-md text-fg-secondary hover:bg-white/5 hover:text-fg sm:size-7"
                      >
                        <Crop className="size-3.5" aria-hidden />
                      </button>
                    ) : null}
                    <button
                      type="button"
                      aria-label={`Remove ${label}`}
                      onClick={() => onRemove(asset.id)}
                      className="grid size-10 place-items-center rounded-md text-fg-secondary hover:bg-white/5 hover:text-fg sm:size-7"
                    >
                      <X className="size-3.5" aria-hidden />
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
          {uploads.map((item) => (
            <li
              key={item.id}
              data-testid="upload-tile"
              data-status={item.status}
              aria-label={item.file.name}
              className={cn(
                "relative aspect-square overflow-hidden rounded-lg border bg-field",
                item.status === "failed" ? "border-danger" : "border-line",
              )}
            >
              {item.previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- a local object URL
                <img src={item.previewUrl} alt="" className="size-full object-cover" />
              ) : (
                <span className="flex size-full flex-col items-center justify-center gap-1 p-2 text-fg-secondary">
                  <FileVideo className="size-6" aria-hidden />
                  <span className="w-full truncate text-center text-[11px]">{item.file.name}</span>
                </span>
              )}
              <UploadOverlay item={item} label={item.file.name} onRetry={onRetryUpload} onRemove={onRemoveUpload} />
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={input}
          type="file"
          multiple
          accept={POST_FILE_ACCEPT}
          className="hidden"
          data-testid="composer-media-input"
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (files.length) onFiles(files);
          }}
        />
        <Button
          id={MEDIA_ADD_ID}
          type="button"
          variant="secondary"
          className="h-10 md:h-9"
          disabled={full || readOnly}
          onClick={() => input.current?.click()}
        >
          <ImagePlus aria-hidden /> Add from device
        </Button>
        <Button type="button" variant="ghost" className="h-10 md:h-9" disabled={full || readOnly} onClick={onOpenLibrary}>
          <Library aria-hidden /> Media library
        </Button>
        <span className="text-xs text-fg-secondary tabular-nums">
          {count} of {MAX_ASSETS}
        </span>
      </div>
      <p className="mt-2 text-xs text-fg-secondary">
        {full
          ? "A post can have up to 10 photos and videos."
          : "Photos: JPEG, PNG, WEBP or HEIC up to 8 MB. Videos: MP4 or MOV up to 100 MB and 90 seconds. One video makes a Reel; 2 to 10 items make a carousel."}
      </p>
      {notice ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-xs text-danger-fg">
          <AlertCircle className="mt-px size-3.5 shrink-0" aria-hidden /> {notice}
        </p>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </Section>
  );
}

function UploadOverlay({
  item,
  label,
  onRetry,
  onRemove,
}: {
  item: UploadItem;
  label: string;
  onRetry: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (item.status === "failed") {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-canvas/85 p-2 text-center">
        <AlertCircle className="size-4 text-danger" aria-hidden />
        <p className="line-clamp-3 text-[11px] text-danger-fg">{item.error ?? "The upload didn't finish."}</p>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => onRetry(item.id)}
            aria-label={`Retry uploading ${label}`}
            className="grid size-10 place-items-center rounded-md bg-white/10 text-fg hover:bg-white/20 sm:size-7"
          >
            <RotateCw className="size-3.5" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => onRemove(item.id)}
            aria-label={`Remove ${label}`}
            className="grid size-10 place-items-center rounded-md bg-white/10 text-fg hover:bg-white/20 sm:size-7"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </div>
      </div>
    );
  }
  return (
    <>
      <button
        type="button"
        onClick={() => onRemove(item.id)}
        aria-label={`Cancel uploading ${label}`}
        className="absolute top-1 right-1 z-10 grid size-10 place-items-center rounded-md bg-canvas/80 text-fg hover:bg-canvas sm:size-7"
      >
        <X className="size-3.5" aria-hidden />
      </button>
      <ProgressBar item={item} label={label} />
    </>
  );
}
