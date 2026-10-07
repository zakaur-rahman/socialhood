"use client";

import { Clapperboard, GalleryHorizontal, ImageOff, Play } from "lucide-react";
import { useState } from "react";

import type { PostSummary } from "@/lib/api/types";
import { mediaTypeLabel } from "@/lib/comments/format";
import { cn } from "@/lib/utils";

const TYPE_ICON = { reel: Clapperboard, video: Play, carousel: GalleryHorizontal } as const;

/** A square thumbnail with the format in the corner; a calm placeholder when Instagram gave none. */
export function PostThumb({
  post,
  className,
}: {
  post: Pick<PostSummary, "thumbnail_url" | "media_url" | "media_type">;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  // Images have no thumbnail_url on Instagram; their media_url is the picture.
  const src = post.thumbnail_url ?? (post.media_type === "image" || post.media_type === "carousel" ? post.media_url : null);
  const Icon = TYPE_ICON[post.media_type.toLowerCase() as keyof typeof TYPE_ICON];
  return (
    <div className={cn("relative grid aspect-square place-items-center overflow-hidden bg-raised", className)}>
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- Instagram CDN thumbnails of any size
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className="size-full object-cover" />
      ) : (
        <ImageOff className="size-5 text-fg-secondary" aria-hidden />
      )}
      {Icon ? (
        <span
          className="absolute top-1.5 right-1.5 grid size-6 place-items-center rounded-md bg-media-scrim/70 text-fg"
          title={mediaTypeLabel(post.media_type)}
          aria-hidden
        >
          <Icon className="size-3.5" />
        </span>
      ) : null}
    </div>
  );
}
