"use client";

import { useMemo, useRef } from "react";

import { Card } from "@/components/ui/card";
import type { CalendarMessage, ScheduledPostSummary } from "@/lib/api/types";
import { dayParts, sameMonth, shortDay, WEEKDAYS_SHORT } from "@/lib/schedule/dates";
import { dayKey } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { useDragSelector, useDropSurface } from "./calendar-dnd";
import { CalendarPostCard } from "./CalendarPostCard";
import { DmChip, MorePostsButton } from "./cell-extras";
import { useSchedule } from "./schedule-context";

const VISIBLE_POSTS = 3;

/**
 * UX-SCR-04 Month: six weeks of day cells with up to 3 posts and "+n more"; a post dragged to
 * another day keeps its time. The day number opens that week.
 */
export function MonthView({
  anchor,
  days,
  posts,
  messages,
  onOpenWeek,
}: {
  anchor: string;
  days: string[];
  posts: ScheduledPostSummary[];
  messages: CalendarMessage[];
  onOpenWeek: (day: string) => void;
}) {
  const schedule = useSchedule();
  const { timeZone, now } = schedule;
  const cellRefs = useRef(new Map<string, HTMLDivElement>());
  const today = dayKey(now, timeZone);

  useDropSurface({
    hitTest: (x, y) => {
      for (const day of days) {
        const rect = cellRefs.current.get(day)?.getBoundingClientRect();
        if (rect && rect.width > 0 && x >= rect.left && x < rect.right && y >= rect.top && y < rect.bottom) {
          return { day, minutes: null };
        }
      }
      return null;
    },
  });

  const byDay = useMemo(() => {
    const map = new Map<string, { posts: ScheduledPostSummary[]; messages: CalendarMessage[] }>();
    const entry = (day: string) => {
      let value = map.get(day);
      if (!value) {
        value = { posts: [], messages: [] };
        map.set(day, value);
      }
      return value;
    };
    for (const post of posts) if (post.publish_at) entry(dayKey(post.publish_at, timeZone)).posts.push(post);
    for (const message of messages) entry(dayKey(message.send_at, timeZone)).messages.push(message);
    for (const value of map.values()) value.posts.sort((a, b) => (a.publish_at ?? "").localeCompare(b.publish_at ?? ""));
    return map;
  }, [posts, messages, timeZone]);

  return (
    <Card className="overflow-hidden p-0">
      <div className="grid grid-cols-7 border-b border-line" aria-hidden>
        {WEEKDAYS_SHORT.map((weekday) => (
          <div key={weekday} className="px-2 py-2 text-center text-xs text-fg-secondary">
            {weekday}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day, index) => (
          <MonthCell
            key={day}
            day={day}
            inMonth={sameMonth(day, anchor)}
            isToday={day === today}
            lastColumn={index % 7 === 6}
            items={byDay.get(day)}
            onOpenWeek={onOpenWeek}
            cellRef={(node) => {
              if (node) cellRefs.current.set(day, node);
              else cellRefs.current.delete(day);
            }}
          />
        ))}
      </div>
    </Card>
  );
}

function MonthCell({
  day,
  inMonth,
  isToday,
  lastColumn,
  items,
  onOpenWeek,
  cellRef,
}: {
  day: string;
  inMonth: boolean;
  isToday: boolean;
  lastColumn: boolean;
  items?: { posts: ScheduledPostSummary[]; messages: CalendarMessage[] };
  onOpenWeek: (day: string) => void;
  cellRef: (node: HTMLDivElement | null) => void;
}) {
  const targeted = useDragSelector((state) => state?.target?.day === day);
  const p = dayParts(day);
  const posts = items?.posts ?? [];
  const shown = posts.length > VISIBLE_POSTS ? posts.slice(0, VISIBLE_POSTS - 1) : posts;
  const hidden = posts.slice(shown.length);
  return (
    <div
      ref={cellRef}
      data-month-day={day}
      role="group"
      aria-label={p.long}
      className={cn(
        "relative flex min-h-28 min-w-0 flex-col gap-1 border-b border-line p-1.5",
        !lastColumn && "border-r",
        !inMonth && "bg-canvas/30",
        targeted && "outline-2 -outline-offset-2 outline-brand",
      )}
    >
      <button
        type="button"
        onClick={() => onOpenWeek(day)}
        aria-label={`Show the week of ${shortDay(day)}`}
        className={cn(
          "grid size-7 place-items-center self-start rounded-full text-xs font-semibold tabular-nums hover:bg-hover",
          isToday ? "bg-brand-soft text-brand-fg" : inMonth ? "text-fg" : "text-fg-secondary",
        )}
      >
        {p.day}
      </button>
      <ul className="flex min-w-0 flex-col gap-1">
        {shown.map((post) => (
          <li key={post.id} className="min-w-0">
            <CalendarPostCard post={post} variant="month" />
          </li>
        ))}
        {hidden.length > 0 ? (
          <li>
            <MorePostsButton
              posts={posts}
              label={`+${hidden.length} more`}
              ariaLabel={`All ${posts.length} posts on ${shortDay(day)}`}
              className="h-6"
            />
          </li>
        ) : null}
      </ul>
      {items && items.messages.length > 0 ? <DmChip messages={items.messages} className="h-6" /> : null}
    </div>
  );
}
