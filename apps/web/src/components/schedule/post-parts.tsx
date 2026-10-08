"use client";

import {
  CalendarClock,
  Clapperboard,
  Copy,
  EllipsisVertical,
  ExternalLink,
  GalleryHorizontal,
  ImageOff,
  ListPlus,
  MessageSquare,
  Pencil,
  Trash2,
  Undo2,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePost } from "@/lib/api/queries";
import type { ScheduledPostSummary, SocialAccount } from "@/lib/api/types";
import { formatCount } from "@/lib/automations/format";
import { initial } from "@/lib/inbox/format";
import { captionLine, CHIP_CLASS, POST_STATUS } from "@/lib/schedule/format";
import { IDENTITY_FILL } from "@/lib/ui/identity";
import { cn } from "@/lib/utils";

import { accountColor, useSchedule } from "./schedule-context";

const THUMB_SIZE = { 24: "size-6 rounded-sm", 40: "size-10 rounded-md", 48: "size-12 rounded-lg" } as const;

/**
 * The post's first image with the account's ring colour (UX-SCR-04), or a calm placeholder by
 * format when there is no media yet.
 */
export function PostThumbnail({
  post,
  size,
  className,
}: {
  post: Pick<ScheduledPostSummary, "thumbnail_url" | "format" | "targets">;
  size: keyof typeof THUMB_SIZE;
  className?: string;
}) {
  const schedule = useSchedule();
  const [failed, setFailed] = useState(false);
  const color = accountColor(schedule, post.targets[0]?.social_account_id);
  const Icon = post.format === "reel" ? Clapperboard : post.format === "carousel" ? GalleryHorizontal : ImageOff;
  return (
    <span
      className={cn(
        "relative grid shrink-0 place-items-center overflow-hidden bg-field ring-2 ring-offset-1 ring-offset-panel",
        THUMB_SIZE[size],
        color.ring,
        className,
      )}
    >
      {post.thumbnail_url && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- uploaded media of any size
        <img
          src={post.thumbnail_url}
          alt=""
          loading="lazy"
          draggable={false}
          onError={() => setFailed(true)}
          className="size-full object-cover"
        />
      ) : (
        <Icon className={size === 24 ? "size-3 text-fg-secondary" : "size-4 text-fg-secondary"} aria-hidden />
      )}
    </span>
  );
}

/**
 * The account's picture in its identity ring (UX-SCR-04), or its initial on the same identity's
 * gradient (lib/ui/identity, D-13). The initial is decorative: the name is beside the avatar, or
 * on the button or group that holds it.
 */
export function AccountAvatar({ account, accountId, size = 20 }: { account?: SocialAccount; accountId: string; size?: 20 | 28 | 36 }) {
  const schedule = useSchedule();
  const color = accountColor(schedule, accountId);
  const name = account?.username ?? account?.display_name ?? "Account";
  return (
    <Avatar
      className={cn(
        "ring-2 ring-offset-1 ring-offset-panel",
        color.ring,
        size === 20 ? "size-5" : size === 28 ? "size-7" : "size-9",
      )}
    >
      {account?.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
      <AvatarFallback
        aria-hidden
        className={cn(
          "font-semibold",
          color.gradient ? [IDENTITY_FILL, color.gradient] : "bg-raised text-fg",
          size === 36 ? "text-sm" : "text-2xs",
        )}
      >
        {initial(name)}
      </AvatarFallback>
    </Avatar>
  );
}

/** The post's accounts, named for screen readers. */
export function TargetAvatars({ post }: { post: Pick<ScheduledPostSummary, "targets"> }) {
  const schedule = useSchedule();
  if (post.targets.length === 0) return <span className="text-xs text-fg-secondary">No account yet</span>;
  const names = post.targets
    .map((t) => schedule.accounts.get(t.social_account_id))
    .map((a) => (a?.username ? `@${a.username}` : (a?.display_name ?? "An account")))
    .join(", ");
  return (
    <span className="flex -space-x-1" role="img" aria-label={names}>
      {post.targets.map((target) => (
        <AccountAvatar
          key={target.social_account_id}
          accountId={target.social_account_id}
          account={schedule.accounts.get(target.social_account_id)}
        />
      ))}
    </span>
  );
}

export function StatusChip({ post, className }: { post: Pick<ScheduledPostSummary, "status">; className?: string }) {
  const status = POST_STATUS[post.status];
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", CHIP_CLASS[status.tone], className)}>
      {status.label}
    </span>
  );
}

/** The first published account's Instagram link. */
export function permalinkOf(post: Pick<ScheduledPostSummary, "targets">): string | null {
  return post.targets.find((t) => t.permalink)?.permalink ?? null;
}

function mediaItemOf(post: Pick<ScheduledPostSummary, "targets">): string | null {
  return post.targets.find((t) => t.post_id)?.post_id ?? null;
}

/**
 * The calendar card's menu button (UI-032). With a fine pointer it is a 24 px ⋯ at the card's end
 * (WCAG 2.5.8's minimum; the card's link keeps the rest of the width). With a coarse pointer a
 * 40 px button doesn't fit beside the title of a 24 px month card (it squeezed the title to
 * nothing), so the button becomes the card: transparent, over the whole card, its glyph hidden so
 * the time and title get the full width. A tap anywhere on the card opens the menu, whose Edit or
 * Open item goes to the composer; the card shows pressed while it is open, and the focus outline
 * goes round the card. It never reaches past the card, so it covers no neighbour. Hover, focus and
 * pressed match Button's ghost.
 */
const CARD_TRIGGER =
  "mr-0.5 grid size-6 shrink-0 place-items-center rounded-md text-fg-secondary transition-[color,background-color] duration-fast ease-standard hover:bg-hover hover:text-fg aria-expanded:bg-pressed aria-expanded:text-fg focus-visible:-outline-offset-2 disabled:pointer-events-none disabled:opacity-50 pointer-coarse:absolute pointer-coarse:inset-0 pointer-coarse:mr-0 pointer-coarse:size-auto pointer-coarse:[&_svg]:hidden";

/**
 * The post's actions (UX-A11Y-02: always visible). "Move to…" is the keyboard and phone
 * alternative to dragging (FR-PUB-08). `card` is the calendar card's trigger (CARD_TRIGGER);
 * `sm` (the rail) and `lg` (rows) are Button's `icon-sm` and `icon`, 40 px on coarse pointers.
 */
export function PostMenu({
  post,
  className,
  size = "sm",
}: {
  post: ScheduledPostSummary;
  className?: string;
  size?: "card" | "sm" | "lg";
}) {
  const schedule = useSchedule();
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const touch = useRef(false);
  const { actions } = schedule;
  const busy = schedule.busyIds.has(post.id);
  const status = post.status;
  const permalink = permalinkOf(post);
  const mediaItem = mediaItemOf(post);
  const published = status === "published" || status === "partially_published";
  const label = captionLine(post.caption);
  const triggerProps = {
    ref: trigger,
    "aria-label": `Actions for ${label}`,
    disabled: busy,
    onPointerDown: (event: ReactPointerEvent<HTMLButtonElement>) => {
      // A press on the menu never starts a drag.
      event.stopPropagation();
      // Radix opens a menu on pointerdown. For touch that is the start of every swipe, so a
      // scroll that begins on a card would open its menu: touch opens it on the tap (click).
      touch.current = event.pointerType !== "mouse";
      if (touch.current) event.preventDefault();
    },
    onClick: () => {
      if (touch.current) setOpen((value) => !value);
      touch.current = false;
    },
  };
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        {size === "card" ? (
          <button type="button" className={cn(CARD_TRIGGER, className)} {...triggerProps}>
            <EllipsisVertical className="size-3" aria-hidden />
          </button>
        ) : (
          <Button
            variant="ghost"
            size={size === "sm" ? "icon-sm" : "icon"}
            className={cn("shrink-0 text-fg-secondary hover:text-fg", className)}
            {...triggerProps}
          >
            <EllipsisVertical aria-hidden />
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {status === "scheduled" ? (
          <DropdownMenuItem onSelect={() => actions.moveTo(post, trigger.current)}>
            <CalendarClock aria-hidden /> Move to…
          </DropdownMenuItem>
        ) : null}
        {status === "draft" ? (
          <>
            <DropdownMenuItem onSelect={() => actions.moveTo(post, trigger.current)}>
              <CalendarClock aria-hidden /> Schedule for…
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => actions.queue(post)}>
              <ListPlus aria-hidden /> Add to queue
            </DropdownMenuItem>
          </>
        ) : null}
        {published && permalink ? (
          <DropdownMenuItem asChild>
            <a href={permalink} target="_blank" rel="noreferrer">
              <ExternalLink aria-hidden /> View on Instagram
            </a>
          </DropdownMenuItem>
        ) : null}
        {published && mediaItem ? (
          <DropdownMenuItem asChild>
            <Link href={`/w/${schedule.slug}/comments/${mediaItem}` as Route}>
              <MessageSquare aria-hidden /> Comments and results
            </Link>
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem asChild>
          <Link href={schedule.composerHref(post)}>
            <Pencil aria-hidden />
            {status === "failed" || status === "canceled" ? "Edit and retry" : status === "draft" || status === "scheduled" ? "Edit" : "Open"}
          </Link>
        </DropdownMenuItem>
        {status === "scheduled" ? (
          <DropdownMenuItem onSelect={() => actions.unschedule(post)}>
            <Undo2 aria-hidden /> Move to drafts
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onSelect={() => actions.duplicate(post)}>
          <Copy aria-hidden /> Duplicate
        </DropdownMenuItem>
        {status !== "publishing" ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => actions.remove(post, trigger.current)}>
              <Trash2 aria-hidden /> Delete
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** "Hovering a published card shows its link and first results" (UX-SCR-04). */
export function PublishedPeek({ post }: { post: ScheduledPostSummary }) {
  const schedule = useSchedule();
  const mediaItem = mediaItemOf(post);
  return (
    <span className="flex flex-col gap-0.5">
      <span className="font-medium">{captionLine(post.caption)}</span>
      {mediaItem ? <PeekResults wid={schedule.wid} postId={mediaItem} /> : <span>Results appear once Instagram shares them.</span>}
      {permalinkOf(post) ? <span>View on Instagram from the post&apos;s menu.</span> : null}
    </span>
  );
}

function PeekResults({ wid, postId }: { wid: string; postId: string }) {
  const post = usePost(wid, postId);
  if (post.isPending) return <span>Loading results…</span>;
  if (post.isError) return <span>Results didn&apos;t load.</span>;
  const likes = post.data.like_count;
  const comments = post.data.comments_count;
  return (
    <span className="tabular-nums">
      {likes === null || likes === undefined ? "Likes hidden" : `${formatCount(likes)} likes`} · {formatCount(comments ?? 0)} comments
    </span>
  );
}
