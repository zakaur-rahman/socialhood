"use client";

import { Download, ExternalLink, FileText, ImageOff } from "lucide-react";
import { useState } from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { Attachment, MessageKind } from "@/lib/api/types";
import { formatBytes } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

type Props = {
  attachment: Attachment;
  kind: MessageKind;
  /** On the gradient (business) side: link colours change. */
  outbound: boolean;
};

/** A platform image that may have expired: a placeholder instead of a broken image. */
function MediaImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed || !src) return <Unavailable label="Media no longer available" />;
  // eslint-disable-next-line @next/next/no-img-element -- platform and storage URLs of any size; next/image needs known hosts and sizes
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} className={className} />;
}

function Unavailable({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-2 rounded-lg bg-black/20 px-3 py-2 text-xs">
      <ImageOff className="size-4 shrink-0" aria-hidden />
      {label}
    </span>
  );
}

/** UX-INB-06: every attachment type (FR-INB-02). */
export function AttachmentView({ attachment, kind, outbound }: Props) {
  const [lightbox, setLightbox] = useState(false);
  const linkClass = outbound ? "text-white underline" : "text-brand-fg";

  switch (attachment.type) {
    case "image":
      if (attachment.expired) return <Unavailable label="Photo no longer available" />;
      return (
        <>
          <button
            type="button"
            onClick={() => setLightbox(true)}
            aria-label="Open photo"
            className="block overflow-hidden rounded-lg"
          >
            <MediaImage src={attachment.url} alt="Photo" className="max-h-64 w-auto rounded-lg object-cover" />
          </button>
          <Dialog open={lightbox} onOpenChange={setLightbox}>
            <DialogContent className="border-line bg-panel p-2 sm:max-w-3xl">
              <DialogTitle className="sr-only">Photo</DialogTitle>
              <MediaImage src={attachment.url} alt="Photo" className="max-h-[80dvh] w-full rounded-lg object-contain" />
            </DialogContent>
          </Dialog>
        </>
      );
    case "video":
      if (attachment.expired) return <Unavailable label="Video no longer available" />;
      return (
        <video
          controls
          preload="metadata"
          src={attachment.url}
          poster={attachment.thumbnail_url ?? undefined}
          className="max-h-64 max-w-full rounded-lg"
        >
          <track kind="captions" />
        </video>
      );
    case "audio":
      if (attachment.expired) return <Unavailable label="Voice message no longer available" />;
      return <audio controls preload="metadata" src={attachment.url} className="max-w-full" aria-label="Voice message" />;
    case "sticker":
      return <MediaImage src={attachment.url} alt="Sticker" className="size-32 object-contain" />;
    case "story": {
      const label = kind === "story_mention" ? "Mentioned you in their story" : kind === "story_reply" ? "Replied to your story" : "Story";
      return (
        <span className="flex w-48 flex-col gap-1.5 rounded-lg bg-black/20 p-2 text-xs">
          <span className="font-medium">{label}</span>
          {attachment.expired ? (
            <Unavailable label="Story expired" />
          ) : (
            <MediaImage
              src={attachment.thumbnail_url ?? attachment.url}
              alt="Story"
              className="aspect-[9/16] w-full rounded-md object-cover"
            />
          )}
          {attachment.permalink && !attachment.expired ? (
            <a href={attachment.permalink} target="_blank" rel="noreferrer" className={cn("inline-flex items-center gap-1", linkClass)}>
              View story <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : null}
        </span>
      );
    }
    case "share":
      return (
        <span className="flex w-56 flex-col gap-1.5 rounded-lg bg-black/20 p-2 text-xs">
          {attachment.thumbnail_url ? (
            <MediaImage src={attachment.thumbnail_url} alt="Shared post" className="aspect-square w-full rounded-md object-cover" />
          ) : null}
          <a
            href={attachment.permalink ?? attachment.url}
            target="_blank"
            rel="noreferrer"
            className={cn("inline-flex items-center gap-1 font-medium", linkClass)}
          >
            View post <ExternalLink className="size-3" aria-hidden />
          </a>
        </span>
      );
    case "file":
    default:
      return (
        <span className="flex items-center gap-3 rounded-lg bg-black/20 px-3 py-2">
          <FileText className="size-5 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm">{attachment.filename ?? "File"}</span>
            {attachment.size_bytes ? <span className="block text-xs opacity-75">{formatBytes(attachment.size_bytes)}</span> : null}
          </span>
          {attachment.expired ? null : (
            <a
              href={attachment.url}
              target="_blank"
              rel="noreferrer"
              download={attachment.filename ?? true}
              aria-label={`Download ${attachment.filename ?? "file"}`}
              className="grid size-8 shrink-0 place-items-center rounded-md hover:bg-white/10"
            >
              <Download className="size-4" aria-hidden />
            </a>
          )}
        </span>
      );
  }
}
