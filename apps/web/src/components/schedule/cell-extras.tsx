"use client";

import { MessageSquare } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { CalendarMessage, ScheduledMessage, ScheduledPostSummary } from "@/lib/api/types";
import { contactName } from "@/lib/inbox/format";
import { formatDayTime, formatTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

import { CalendarPostCard } from "./CalendarPostCard";
import { useSchedule } from "./schedule-context";

const DM_STATUS: Record<ScheduledMessage["status"], string | null> = {
  scheduled: null,
  sending: "Sending",
  sent: "Sent",
  failed: "Failed",
  canceled: "Canceled",
  expired: "Expired",
};

export function dmLabel(messages: CalendarMessage[]): string {
  if (messages.length === 1) return `DM to ${contactName(messages[0].contact, messages[0].platform)}`;
  return `${messages.length} scheduled DMs`;
}

/**
 * The Messages layer (FR-PUB-08, FR-SMS-02): scheduled DMs in a chip that opens the list, each
 * linking to its conversation. No violet token exists (§4.2), so the chip is told apart by its
 * icon, label and dashed border rather than colour alone.
 */
export function DmChip({
  messages,
  compact = false,
  className,
}: {
  messages: CalendarMessage[];
  compact?: boolean;
  className?: string;
}) {
  const schedule = useSchedule();
  const label = dmLabel(messages);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="dm-chip"
          aria-label={`${label}, ${formatTime(messages[0].send_at, schedule.timeZone)}`}
          className={cn(
            "flex w-full min-w-0 items-center gap-1 rounded-md border border-dashed border-line-strong bg-field px-1.5 text-2xs text-fg",
            "hover:bg-raised focus-visible:-outline-offset-2",
            className,
          )}
        >
          <MessageSquare className="size-3 shrink-0 text-fg-secondary" aria-hidden />
          {compact ? (
            <span className="tabular-nums">{messages.length}</span>
          ) : (
            <span className="min-w-0 truncate">
              <span className="font-semibold tabular-nums">{formatTime(messages[0].send_at, schedule.timeZone)}</span> {label}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start">
        <p className={EYEBROW}>Scheduled DMs</p>
        <ul className="space-y-1">
          {messages.map((message) => {
            const status = DM_STATUS[message.status];
            return (
              <li key={message.id}>
                <Link
                  href={`/w/${schedule.slug}/inbox/${message.conversation_id}` as Route}
                  className="block rounded-md px-2 py-1.5 hover:bg-hover"
                >
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    <span className="truncate">{contactName(message.contact, message.platform)}</span>
                    <span className="shrink-0 text-xs text-fg-secondary tabular-nums">
                      {formatDayTime(message.send_at, schedule.timeZone, schedule.now)}
                    </span>
                  </span>
                  <span className="line-clamp-2 text-xs text-fg-secondary">{message.text}</span>
                  {status ? <span className="text-xs text-fg-secondary">{status}</span> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

/** "+n more" (UX-SCR-04 Month: opens the posts in a popover; the Week view uses it for crowded cells). */
export function MorePostsButton({
  posts,
  label,
  ariaLabel,
  className,
}: {
  posts: ScheduledPostSummary[];
  label: string;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          className={cn(
            "rounded-md px-1.5 text-2xs font-medium text-fg-secondary hover:bg-hover hover:text-fg focus-visible:-outline-offset-2",
            className,
          )}
        >
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64">
        <ul className="space-y-1">
          {posts.map((post) => (
            <li key={post.id}>
              <CalendarPostCard post={post} variant="month" />
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
