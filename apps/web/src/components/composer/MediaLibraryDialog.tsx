"use client";

import { Check, FileVideo, Loader2, RotateCw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useMediaLibrary, type MediaLibraryFilters } from "@/lib/api/queries/scheduledPosts";
import type { MediaAsset } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { formatDuration } from "@/lib/publishing/rules";
import { cn } from "@/lib/utils";

type TypeFilter = "all" | "image" | "video";

/**
 * FR-PUB-13: uploads for posts, newest first, filtered by type and upload date, to reuse in this
 * post. Items already in the post are marked; at most the free places can be picked.
 */
export function MediaLibraryDialog({
  open,
  onOpenChange,
  wid,
  inPost,
  slots,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  wid: string;
  /** Asset ids already in the post. */
  inPost: string[];
  /** How many more items the post can take. */
  slots: number;
  onAdd: (assets: MediaAsset[]) => void;
}) {
  const [type, setType] = useState<TypeFilter>("all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [picked, setPicked] = useState<MediaAsset[]>([]);
  const filters: MediaLibraryFilters = { type: type === "all" ? null : type, since: since || null, until: until || null };
  const library = useMediaLibrary(wid, filters, open);
  const items = library.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = type !== "all" || Boolean(since) || Boolean(until);

  const toggle = (asset: MediaAsset) =>
    setPicked((current) =>
      current.some((item) => item.id === asset.id) ? current.filter((item) => item.id !== asset.id) : [...current, asset],
    );

  const close = (next: boolean) => {
    if (!next) setPicked([]);
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto border-line bg-panel sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">Media library</DialogTitle>
          <DialogDescription className="text-fg-secondary">Photos and videos you&apos;ve uploaded for posts.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-end gap-3">
          <ToggleGroup value={type} onValueChange={(value) => setType(value as TypeFilter)} aria-label="Type" className="w-auto">
            <ToggleGroupItem value="all" className="min-h-10 md:min-h-8">
              All
            </ToggleGroupItem>
            <ToggleGroupItem value="image" className="min-h-10 md:min-h-8">
              Photos
            </ToggleGroupItem>
            <ToggleGroupItem value="video" className="min-h-10 md:min-h-8">
              Videos
            </ToggleGroupItem>
          </ToggleGroup>
          <div className="space-y-1">
            <Label htmlFor="library-since" className="text-xs text-fg-secondary">
              Uploaded from
            </Label>
            <input
              id="library-since"
              type="date"
              value={since}
              max={until || undefined}
              onChange={(event) => setSince(event.target.value)}
              className="h-10 rounded-lg border border-line bg-field px-3 text-sm outline-none focus:bg-raised md:h-9"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="library-until" className="text-xs text-fg-secondary">
              To
            </Label>
            <input
              id="library-until"
              type="date"
              value={until}
              min={since || undefined}
              onChange={(event) => setUntil(event.target.value)}
              className="h-10 rounded-lg border border-line bg-field px-3 text-sm outline-none focus:bg-raised md:h-9"
            />
          </div>
        </div>

        {library.isPending ? (
          <ul aria-busy="true" aria-label="Loading media" className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            {Array.from({ length: 10 }, (_, index) => (
              <li key={index}>
                <Skeleton className="aspect-square rounded-lg bg-raised" />
              </li>
            ))}
          </ul>
        ) : library.isError ? (
          <div role="alert" className="flex flex-col items-center gap-2 py-8 text-center text-sm">
            <p className="text-fg-secondary">{errorMessage(library.error)}</p>
            <Button variant="secondary" onClick={() => void library.refetch()}>
              <RotateCw aria-hidden /> Try again
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm font-semibold">{filtered ? "Nothing matches these filters" : "No uploads yet"}</p>
            <p className="mt-1 text-sm text-fg-secondary">
              {filtered ? "Try another type or date." : "Photos and videos you upload for posts are kept here."}
            </p>
          </div>
        ) : (
          <ul aria-label="Uploads" className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            {items.map((asset) => {
              const already = inPost.includes(asset.id);
              const isPicked = picked.some((item) => item.id === asset.id);
              const full = !isPicked && picked.length >= slots;
              const name = asset.original_filename ?? (asset.resource_type === "video" ? "Video" : "Photo");
              return (
                <li key={asset.id}>
                  <button
                    type="button"
                    aria-pressed={isPicked}
                    aria-label={already ? `${name}, already in this post` : name}
                    disabled={already || full}
                    onClick={() => toggle(asset)}
                    className={cn(
                      "relative block aspect-square w-full overflow-hidden rounded-lg border-2 bg-field disabled:cursor-not-allowed",
                      isPicked ? "border-brand" : "border-transparent hover:border-line-strong",
                      (already || full) && "opacity-50",
                    )}
                  >
                    {asset.resource_type === "video" ? (
                      asset.secure_url ? (
                        <video src={asset.secure_url} muted playsInline preload="metadata" aria-hidden className="size-full object-cover" />
                      ) : (
                        <FileVideo className="m-auto size-6 text-fg-secondary" aria-hidden />
                      )
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element -- uploaded media of any size
                      <img src={asset.secure_url ?? ""} alt="" loading="lazy" className="size-full object-cover" />
                    )}
                    {asset.resource_type === "video" && asset.duration_s ? (
                      <span className="absolute right-1 bottom-1 rounded-md bg-canvas/80 px-1 text-[11px] tabular-nums">
                        {formatDuration(asset.duration_s)}
                      </span>
                    ) : null}
                    {isPicked ? (
                      <span className="absolute top-1 right-1 grid size-6 place-items-center rounded-full bg-brand text-white">
                        <Check className="size-3.5" aria-hidden />
                      </span>
                    ) : null}
                    {already ? (
                      <span className="absolute inset-x-1 bottom-1 rounded-md bg-canvas/80 px-1 text-[11px]">In post</span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {library.hasNextPage ? (
          <Button
            variant="ghost"
            className="justify-self-center"
            onClick={() => void library.fetchNextPage()}
            disabled={library.isFetchingNextPage}
          >
            {library.isFetchingNextPage ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Load more
          </Button>
        ) : null}
        <DialogFooter className="items-center sm:justify-between">
          <p className="text-xs text-fg-secondary" aria-live="polite">
            {picked.length} selected · {slots === 0 ? "the post is full" : `room for ${slots}`}
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button
              className="bg-brand-gradient text-white"
              disabled={picked.length === 0}
              onClick={() => {
                onAdd(picked);
                close(false);
              }}
            >
              {picked.length ? `Add ${picked.length}` : "Add"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
