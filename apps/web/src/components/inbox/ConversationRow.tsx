import { FileText, Image as ImageIcon, Mic, Share2, Smile, Video, CircleDashed, type LucideIcon } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { Ref } from "react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { AiMode, ConversationListItem, MessageKind } from "@/lib/api/types";
import { contactName, previewPrefix, previewText, rowBadges } from "@/lib/inbox/format";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

import { ContactAvatar } from "./ContactAvatar";

const KIND_ICON: Partial<Record<MessageKind, LucideIcon>> = {
  image: ImageIcon,
  video: Video,
  audio: Mic,
  file: FileText,
  sticker: Smile,
  story_mention: CircleDashed,
  story_reply: CircleDashed,
  share: Share2,
};

/** Row heights, fixed so the virtualised list can place rows without measuring (TR-FE-08). */
export const ROW_HEIGHT = 68;
export const ROW_HEIGHT_WITH_BADGES = 90;

type Props = {
  item: ConversationListItem;
  href: Route;
  selected: boolean;
  now: Date;
  /** The AI mode that applies (the conversation's own, else its account's): "AI Auto" badge. */
  aiMode?: AiMode | null;
  index?: number;
  onNavigate?: () => void;
  ref?: Ref<HTMLAnchorElement>;
};

/** How tall a row is: two lines, or three with badges. */
export function rowHeight(item: ConversationListItem, now: Date, aiMode: AiMode | null = null): number {
  return rowBadges(item, now, aiMode).length > 0 ? ROW_HEIGHT_WITH_BADGES : ROW_HEIGHT;
}

/** UX-INB-04, restyled (C-063): one conversation, as a link (v1 rows were unfocusable divs). */
export function ConversationRow({ item, href, selected, now, aiMode = null, index, onNavigate, ref }: Props) {
  const name = contactName(item.contact, item.platform);
  const unread = item.unread_count > 0;
  const prefix = previewPrefix(item);
  const text = previewText(item);
  const Icon = item.last_message_kind ? KIND_ICON[item.last_message_kind] : undefined;
  const badges = rowBadges(item, now, aiMode);

  return (
    <Link
      ref={ref}
      href={href}
      onClick={onNavigate}
      aria-current={selected ? "page" : undefined}
      data-index={index}
      data-conversation-row={item.id}
      className={cn(
        "relative flex items-start gap-3 px-4 py-3 hover:bg-hover focus-visible:-outline-offset-2",
        badges.length > 0 ? "h-[90px]" : "h-[68px]",
        selected && "bg-raised hover:bg-raised",
      )}
    >
      {/* The selection bar (DESIGN_SYSTEM §5): 2 px brand on the leading edge, inset 8 px, rounded. */}
      {selected ? (
        <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-brand" data-testid="row-accent" aria-hidden />
      ) : null}
      <ContactAvatar id={item.contact.id} name={name} pictureUrl={item.contact.profile_picture_url} platform={item.platform} size={40} />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className={cn("min-w-0 flex-1 truncate text-sm font-semibold", unread ? "text-fg" : "text-fg-secondary")}>
            {name}
          </span>
          {item.last_message_at ? (
            <time
              dateTime={item.last_message_at}
              className={cn("shrink-0 text-xs tabular-nums", unread ? "font-medium text-brand-fg" : "text-fg-secondary")}
            >
              {relativeTime(item.last_message_at, now)}
            </time>
          ) : null}
        </span>
        <span className="mt-0.5 flex items-center gap-2">
          <span
            className={cn(
              "flex min-w-0 flex-1 items-center gap-1 text-sm",
              unread ? "font-medium text-fg" : "text-fg-secondary",
            )}
          >
            {Icon ? <Icon className="size-3.5 shrink-0" aria-hidden /> : null}
            <span className="truncate">
              {prefix}
              {text}
            </span>
          </span>
          {unread ? (
            <span className="size-2 shrink-0 rounded-full bg-brand" role="img" aria-label="unread" />
          ) : null}
        </span>
        {badges.length > 0 ? (
          // Status Badges (11 px, 20 px tall): 12 + 20 + 2 + 20 + 4 + 20 + 12 = the 90 px row.
          <span className="mt-1 flex gap-1 overflow-hidden">
            {badges.map((badge) => {
              const chip = (
                <Badge key={badge.key} tone={badge.tone} className="tabular-nums" data-badge={badge.key}>
                  {badge.label}
                  {badge.srDetail ? <span className="sr-only">{badge.srDetail}</span> : null}
                </Badge>
              );
              // The hint shows on hover; the row is the link, so the badge itself takes no focus.
              return badge.hint ? (
                <Tooltip key={badge.key}>
                  <TooltipTrigger asChild>{chip}</TooltipTrigger>
                  <TooltipContent side="bottom">{badge.hint}</TooltipContent>
                </Tooltip>
              ) : (
                chip
              );
            })}
          </span>
        ) : null}
      </span>
    </Link>
  );
}
