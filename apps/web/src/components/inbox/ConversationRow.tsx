import { FileText, Image as ImageIcon, Mic, Share2, Smile, Video, CircleDashed, type LucideIcon } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { Ref } from "react";

import type { ConversationListItem, MessageKind } from "@/lib/api/types";
import { contactName, previewPrefix, previewText, signalChip, TONE_CLASS } from "@/lib/inbox/format";
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

type Props = {
  item: ConversationListItem;
  href: Route;
  selected: boolean;
  now: Date;
  index?: number;
  onNavigate?: () => void;
  ref?: Ref<HTMLAnchorElement>;
};

/** UX-INB-04: one conversation, as a link (v1 rows were unfocusable divs). */
export function ConversationRow({ item, href, selected, now, index, onNavigate, ref }: Props) {
  const name = contactName(item.contact, item.platform);
  const unread = item.unread_count > 0;
  const prefix = previewPrefix(item);
  const text = previewText(item);
  const Icon = item.last_message_kind ? KIND_ICON[item.last_message_kind] : undefined;
  const chip = signalChip(item, now);

  return (
    <Link
      ref={ref}
      href={href}
      onClick={onNavigate}
      aria-current={selected ? "page" : undefined}
      data-index={index}
      data-conversation-row={item.id}
      className={cn(
        "flex h-[72px] items-center gap-3 px-4 py-3 outline-offset-[-2px] hover:bg-white/5",
        selected && "bg-raised shadow-[inset_-2px_0_0_var(--color-brand)] hover:bg-raised",
      )}
    >
      <ContactAvatar id={item.contact.id} name={name} pictureUrl={item.contact.profile_picture_url} platform={item.platform} />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className={cn("min-w-0 flex-1 truncate text-sm font-semibold", unread ? "text-fg" : "text-fg-secondary")}>
            {name}
          </span>
          {item.last_message_at ? (
            <time dateTime={item.last_message_at} className="shrink-0 text-xs text-fg-secondary tabular-nums">
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
          {chip ? (
            <span className={cn("shrink-0 rounded-full px-2 text-[11px] leading-5 font-medium", TONE_CLASS[chip.tone])}>
              {chip.label}
            </span>
          ) : null}
          {unread ? (
            <span className="size-2 shrink-0 rounded-full bg-brand" role="img" aria-label="unread" />
          ) : null}
        </span>
      </span>
    </Link>
  );
}
