"use client";

import { Check, Lock } from "lucide-react";
import Link from "next/link";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ScheduledPostSummary } from "@/lib/api/types";
import { canMove, captionLine, POST_STATUS } from "@/lib/schedule/format";
import { formatDayTime, formatTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { useCalendarDnd, useDragSelector } from "./calendar-dnd";
import { PostMenu, PostThumbnail, PublishedPeek } from "./post-parts";
import { useSchedule } from "./schedule-context";

/** "Linen styles, Scheduled, Wed 30 Sep 18:00" for the card's link. */
export function postLabel(post: ScheduledPostSummary, timeZone: string, now: Date): string {
  const when = post.publish_at ? `, ${formatDayTime(post.publish_at, timeZone, now)}` : "";
  return `${captionLine(post.caption)}, ${POST_STATUS[post.status].label}${when}`;
}

/**
 * A post on the Week or Month grid (UX-SCR-04): 24 px thumbnail with the account ring, time and
 * first caption words, left border by status (`border-l-2`); drafts drawn muted, publishing
 * pulses. Drafts and scheduled posts drag; the link opens the composer; the menu holds "Move to…".
 * On coarse pointers a tap on the card opens the menu (PostMenu's `card` trigger), since a 40 px
 * button doesn't fit beside the title.
 */
export function CalendarPostCard({ post, variant }: { post: ScheduledPostSummary; variant: "week" | "month" }) {
  const schedule = useSchedule();
  const { pointerDown, consumeClick, enabled } = useCalendarDnd();
  const dragging = useDragSelector((state) => state?.source.post.id === post.id);
  const status = POST_STATUS[post.status];
  const movable = canMove(post);
  const published = post.status === "published" || post.status === "partially_published";
  const time = post.publish_at ? formatTime(post.publish_at, schedule.timeZone) : "";
  const badges = (
    <>
      {published ? <Check className="size-3 text-success" aria-hidden /> : null}
      {post.status === "failed" ? <span className="text-danger-fg">· Failed</span> : null}
      {post.status === "publishing" ? <Lock className="size-3 text-fg-secondary" aria-hidden /> : null}
    </>
  );

  const link = (
    <Link
      href={schedule.composerHref(post)}
      draggable={false}
      aria-label={postLabel(post, schedule.timeZone, schedule.now)}
      onClick={(event) => {
        if (consumeClick()) event.preventDefault();
      }}
      // The one focus outline, inset: the grids clip, and cards sit 4 px apart.
      className={cn(
        "flex min-w-0 flex-1 items-center gap-1.5 rounded-[inherit] focus-visible:-outline-offset-2",
        variant === "week" ? "px-1.5 py-1" : "px-1 py-0.5",
      )}
    >
      {variant === "week" ? (
        <>
          <PostThumbnail post={post} size={24} />
          <span className="min-w-0 flex-1 leading-tight">
            <span className="flex items-center gap-1 text-2xs font-semibold tabular-nums">
              {time}
              {badges}
            </span>
            <span className="block truncate text-2xs text-fg-secondary">{captionLine(post.caption)}</span>
          </span>
        </>
      ) : (
        <>
          <span className="flex shrink-0 items-center gap-1 text-2xs font-semibold tabular-nums">
            {time}
            {badges}
          </span>
          <span className="min-w-0 flex-1 truncate text-2xs text-fg-secondary">{captionLine(post.caption)}</span>
        </>
      )}
    </Link>
  );

  return (
    <div
      data-post-id={post.id}
      data-status={post.status}
      onPointerDown={(event) => pointerDown(event, { post, from: "calendar" })}
      className={cn(
        "group/card relative flex min-w-0 items-center rounded-md border border-l-2 border-line-subtle bg-raised select-none",
        status.border,
        variant === "week" ? "h-full" : "h-6",
        post.status === "draft" && "bg-field text-fg-secondary",
        movable && enabled ? "cursor-grab active:cursor-grabbing" : "cursor-pointer",
        dragging && "opacity-40",
      )}
    >
      {published ? (
        <Tooltip>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent side="top" className="max-w-60">
            <PublishedPeek post={post} />
          </TooltipContent>
        </Tooltip>
      ) : (
        link
      )}
      <PostMenu post={post} size="card" />
    </div>
  );
}
