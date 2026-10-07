"use client";

import { MessageSquare } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useMemo } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import type { CalendarMessage, ScheduledPostSummary } from "@/lib/api/types";
import { contactName } from "@/lib/inbox/format";
import { agendaDayLabel } from "@/lib/schedule/dates";
import { captionLine } from "@/lib/schedule/format";
import { dayKey, formatTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

import { postLabel } from "./CalendarPostCard";
import { PostMenu, PostThumbnail, StatusChip, TargetAvatars } from "./post-parts";
import { useSchedule } from "./schedule-context";

type Row =
  | { kind: "post"; at: string; post: ScheduledPostSummary }
  | { kind: "dm"; at: string; message: CalendarMessage };

/**
 * UX-SCR-04 on phones (below 768 px): Month and Week become an agenda, days as headers and posts
 * as rows; moving uses "Move to…" in each row's menu (FR-PUB-08). Rows and buttons are at least
 * 40 px tall (UX-A11Y-05).
 */
export function AgendaView({
  days,
  posts,
  messages,
}: {
  days: string[];
  posts: ScheduledPostSummary[];
  messages: CalendarMessage[];
}) {
  const schedule = useSchedule();
  const { timeZone, now } = schedule;
  const today = dayKey(now, timeZone);
  const groups = useMemo(() => {
    const map = new Map<string, Row[]>(days.map((day) => [day, []]));
    for (const post of posts) {
      if (post.publish_at) map.get(dayKey(post.publish_at, timeZone))?.push({ kind: "post", at: post.publish_at, post });
    }
    for (const message of messages) map.get(dayKey(message.send_at, timeZone))?.push({ kind: "dm", at: message.send_at, message });
    return [...map.entries()]
      .filter(([, rows]) => rows.length > 0)
      .map(([day, rows]) => [day, rows.sort((a, b) => a.at.localeCompare(b.at))] as const);
  }, [days, posts, messages, timeZone]);

  if (groups.length === 0) {
    return (
      <EmptyState
        className="rounded-xl border border-line bg-panel"
        title="Nothing planned for these days"
        body="Drafts and scheduled posts appear here with their times."
        action={
          <Button onClick={() => schedule.actions.newPostAt(null)}>New post</Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="agenda">
      {groups.map(([day, rows]) => {
        return (
          <section key={day} aria-labelledby={`agenda-${day}`}>
            <h2 id={`agenda-${day}`} className={cn(EYEBROW, "mb-2")}>
              {agendaDayLabel(day, today)}
            </h2>
            <ul className="divide-y divide-line-subtle overflow-hidden rounded-xl border border-line bg-panel">
              {rows.map((row) =>
                row.kind === "post" ? (
                  <li key={row.post.id} className="flex min-h-14 items-center gap-3 px-3 py-2">
                    <Link
                      href={schedule.composerHref(row.post)}
                      aria-label={postLabel(row.post, timeZone, now)}
                      className="flex min-w-0 flex-1 items-center gap-3"
                    >
                      <PostThumbnail post={row.post} size={40} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2 text-sm font-semibold tabular-nums">
                          {formatTime(row.at, timeZone)}
                          <StatusChip post={row.post} />
                        </span>
                        <span className="block truncate text-sm text-fg-secondary">{captionLine(row.post.caption)}</span>
                      </span>
                    </Link>
                    <TargetAvatars post={row.post} />
                    <PostMenu post={row.post} size="lg" />
                  </li>
                ) : (
                  <li key={row.message.id}>
                    <Link
                      href={`/w/${schedule.slug}/inbox/${row.message.conversation_id}` as Route}
                      className="flex min-h-14 items-center gap-3 px-3 py-2"
                    >
                      <span className="grid size-10 shrink-0 place-items-center rounded-md border border-dashed border-line-strong bg-field">
                        <MessageSquare className="size-4 text-fg-secondary" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold tabular-nums">
                          {formatTime(row.at, timeZone)} · DM to {contactName(row.message.contact, row.message.platform)}
                        </span>
                        <span className="block truncate text-sm text-fg-secondary">{row.message.text}</span>
                      </span>
                    </Link>
                  </li>
                ),
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
