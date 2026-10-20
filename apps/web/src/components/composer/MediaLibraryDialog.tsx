"use client";

import { Check, FileVideo } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useMediaLibrary, type MediaLibraryFilters } from "@/lib/api/queries/scheduledPosts";
import type { MediaAsset } from "@/lib/api/types";
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
      <DialogContent size="xl">
        <DialogHeader>
          <DialogTitle>Media library</DialogTitle>
          <DialogDescription>Photos and videos you&apos;ve uploaded for posts.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-end gap-3">
          <ToggleGroup value={type} onValueChange={(value) => setType(value as TypeFilter)} aria-label="Type" className="w-auto">
            <ToggleGroupItem value="all">All</ToggleGroupItem>
            <ToggleGroupItem value="image">Photos</ToggleGroupItem>
            <ToggleGroupItem value="video">Videos</ToggleGroupItem>
          </ToggleGroup>
          {/* Native date pickers through Input (D-04); `lg`, the old 36 px fields. */}
          <Field id="library-since" density="compact" className="w-auto">
            <FieldLabel>Uploaded from</FieldLabel>
            <Input
              type="date"
              size="lg"
              className="w-auto"
              value={since}
              max={until || undefined}
              onChange={(event) => setSince(event.target.value)}
            />
          </Field>
          <Field id="library-until" density="compact" className="w-auto">
            <FieldLabel>To</FieldLabel>
            <Input
              type="date"
              size="lg"
              className="w-auto"
              value={until}
              min={since || undefined}
              onChange={(event) => setUntil(event.target.value)}
            />
          </Field>
        </div>

        {library.isPending ? (
          <ul aria-busy="true" aria-label="Loading media" className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            {Array.from({ length: 10 }, (_, index) => (
              <li key={index}>
                <Skeleton className="aspect-square rounded-lg" />
              </li>
            ))}
          </ul>
        ) : library.isError ? (
          <ErrorState size="compact" error={library.error} onRetry={() => void library.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            size="compact"
            title={filtered ? "Nothing matches these filters" : "No uploads yet"}
            body={filtered ? "Try another type or date." : "Photos and videos you upload for posts are kept here."}
          />
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
                      <span className="absolute right-1 bottom-1 rounded-sm bg-media-scrim/80 px-1 text-2xs tabular-nums">
                        {formatDuration(asset.duration_s)}
                      </span>
                    ) : null}
                    {isPicked ? (
                      <span className="absolute top-1 right-1 grid size-6 place-items-center rounded-full bg-brand text-on-brand">
                        <Check className="size-3.5" aria-hidden />
                      </span>
                    ) : null}
                    {already ? (
                      <span className="absolute inset-x-1 bottom-1 rounded-sm bg-media-scrim/80 px-1 text-2xs">In post</span>
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
            loading={library.isFetchingNextPage}
          >
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
