"use client";

import { useLayoutEffect, useMemo, useRef } from "react";

import { Card } from "@/components/ui/card";
import type { CalendarMessage, CalendarSlot, ScheduledPostSummary } from "@/lib/api/types";
import {
  DAY_MINUTES,
  dayParts,
  formatMinutes,
  instantAt,
  minutesOfDay,
  ROW_MINUTES,
  snapMinutes,
  tooSoon,
} from "@/lib/schedule/dates";
import { dayKey } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { useDragSelector, useDropSurface } from "./calendar-dnd";
import { CalendarPostCard } from "./CalendarPostCard";
import { DmChip, MorePostsButton } from "./cell-extras";
import { useSchedule } from "./schedule-context";

export const ROW_PX = 44;
const ROWS = DAY_MINUTES / ROW_MINUTES;
const SCROLL_TO_ROW = (8 * 60) / ROW_MINUTES; // 08:00 (UX-SCR-04)
const VISIBLE_POSTS = 2;
const EDGE_PX = 32;
export const GRID_COLUMNS = "grid grid-cols-[48px_repeat(7,minmax(0,1fr))] md:grid-cols-[56px_repeat(7,minmax(0,1fr))]";

type Cell = { posts: ScheduledPostSummary[]; messages: CalendarMessage[]; slots: CalendarSlot[] };

function rowOf(instant: string, timeZone: string): number {
  return Math.floor(minutesOfDay(instant, timeZone) / ROW_MINUTES);
}

/**
 * UX-SCR-04 Week (the default on desktop): 7 day columns and 30-minute rows, scrolled to 08:00;
 * a red line at now; post cards; dashed free queue slots (FR-PUB-09); scheduled DMs when the
 * Messages layer is on. Clicking an empty future time starts a post at that time. Posts drag to
 * another time, snapping to 15 minutes (FR-PUB-08).
 */
export function WeekView({
  days,
  posts,
  messages,
  slots,
}: {
  days: string[];
  posts: ScheduledPostSummary[];
  messages: CalendarMessage[];
  slots: CalendarSlot[];
}) {
  const schedule = useSchedule();
  const { timeZone, now } = schedule;
  const scroller = useRef<HTMLDivElement>(null);
  const columns = useRef(new Map<string, HTMLDivElement>());
  const today = dayKey(now, timeZone);

  useLayoutEffect(() => {
    if (scroller.current) scroller.current.scrollTop = SCROLL_TO_ROW * ROW_PX;
  }, []);

  useDropSurface({
    hitTest: (x, y) => {
      const box = scroller.current?.getBoundingClientRect();
      if (!box || y < box.top || y > box.bottom || x < box.left || x > box.right) return null;
      for (const day of days) {
        const rect = columns.current.get(day)?.getBoundingClientRect();
        if (!rect || rect.height === 0 || x < rect.left || x >= rect.right) continue;
        return { day, minutes: snapMinutes(((y - rect.top) / rect.height) * DAY_MINUTES) };
      }
      return null;
    },
    edgeScroll: (x, y) => {
      const el = scroller.current;
      const box = el?.getBoundingClientRect();
      if (!el || !box || x < box.left || x > box.right) return;
      if (y < box.top + EDGE_PX && y > box.top - EDGE_PX) el.scrollTop -= ROW_PX / 2;
      else if (y > box.bottom - EDGE_PX && y < box.bottom + EDGE_PX) el.scrollTop += ROW_PX / 2;
    },
  });

  const cells = useMemo(() => {
    const map = new Map<string, Cell>();
    const cell = (day: string, row: number) => {
      const key = `${day}|${row}`;
      let value = map.get(key);
      if (!value) {
        value = { posts: [], messages: [], slots: [] };
        map.set(key, value);
      }
      return value;
    };
    for (const post of posts) {
      if (post.publish_at) cell(dayKey(post.publish_at, timeZone), rowOf(post.publish_at, timeZone)).posts.push(post);
    }
    for (const message of messages) {
      cell(dayKey(message.send_at, timeZone), rowOf(message.send_at, timeZone)).messages.push(message);
    }
    for (const slot of slots) cell(dayKey(slot.at, timeZone), rowOf(slot.at, timeZone)).slots.push(slot);
    return map;
  }, [posts, messages, slots, timeZone]);

  return (
    <Card className="flex min-h-0 flex-col overflow-hidden p-0">
      <div className={cn(GRID_COLUMNS, "overflow-hidden border-b border-line [scrollbar-gutter:stable]")}>
        <div aria-hidden />
        {days.map((day) => {
          const p = dayParts(day);
          const isToday = day === today;
          return (
            <div key={day} className="flex items-center justify-center gap-1 border-l border-line px-1 py-2 text-xs">
              <span className={isToday ? "text-brand-fg" : "text-fg-secondary"}>{p.weekday}</span>
              <span
                className={cn(
                  "grid min-w-6 place-items-center rounded-full px-1 text-sm font-semibold tabular-nums",
                  isToday && "bg-brand-soft text-brand-fg",
                )}
              >
                {p.day}
              </span>
              {isToday ? <span className="sr-only">(today)</span> : null}
            </div>
          );
        })}
      </div>
      <div
        ref={scroller}
        data-testid="week-scroller"
        className="relative h-[calc(100dvh-260px)] min-h-[420px] overflow-y-auto [scrollbar-gutter:stable]"
      >
        <div className={GRID_COLUMNS} style={{ height: ROWS * ROW_PX }}>
          <div aria-hidden className="relative">
            {Array.from({ length: 24 }, (_, hour) =>
              hour === 0 ? null : (
                <span
                  key={hour}
                  className="absolute right-2 -translate-y-1/2 text-2xs text-fg-secondary tabular-nums"
                  style={{ top: hour * 2 * ROW_PX }}
                >
                  {formatMinutes(hour * 60)}
                </span>
              ),
            )}
          </div>
          {days.map((day) => (
            <DayColumn
              key={day}
              day={day}
              isToday={day === today}
              cells={cells}
              columnRef={(node) => {
                if (node) columns.current.set(day, node);
                else columns.current.delete(day);
              }}
            />
          ))}
        </div>
      </div>
    </Card>
  );
}

function DayColumn({
  day,
  isToday,
  cells,
  columnRef,
}: {
  day: string;
  isToday: boolean;
  cells: Map<string, Cell>;
  columnRef: (node: HTMLDivElement | null) => void;
}) {
  const schedule = useSchedule();
  const { timeZone, now } = schedule;
  const target = useDragSelector((state) => (state?.target?.day === day ? state.target.minutes : null));
  const p = dayParts(day);
  const today = dayKey(now, timeZone);
  const nowMinutes = minutesOfDay(now, timeZone);
  const nowTop = isToday ? (nowMinutes / ROW_MINUTES) * ROW_PX : null;
  // Rows that start at least 5 minutes from now take a click (F-13: a post at that time).
  const firstOpenRow = day > today ? 0 : day < today ? ROWS : Math.ceil((nowMinutes + 5) / ROW_MINUTES);

  return (
    <div
      ref={columnRef}
      data-day={day}
      role="group"
      aria-label={p.long}
      className={cn("relative border-l border-line", isToday && "bg-brand-soft/20")}
    >
      {Array.from({ length: ROWS }, (_, row) => {
        const open = row >= firstOpenRow;
        return (
          <div
            key={row}
            aria-hidden
            data-row={row}
            onClick={open ? () => schedule.actions.newPostAt(instantAt(day, row * ROW_MINUTES, timeZone)) : undefined}
            className={cn(
              "border-t",
              row % 2 === 0 ? "border-line-subtle" : "border-transparent",
              open ? "cursor-pointer hover:bg-hover" : "bg-canvas/20",
            )}
            style={{ height: ROW_PX }}
          />
        );
      })}
      {[...cells.entries()]
        .filter(([key]) => key.startsWith(`${day}|`))
        .map(([key, cell]) => {
          const row = Number(key.split("|")[1]);
          return <CellItems key={key} row={row} cell={cell} />;
        })}
      {nowTop !== null ? (
        <div aria-hidden data-testid="now-line" className="pointer-events-none absolute inset-x-0 z-10" style={{ top: nowTop }}>
          <div className="h-0.5 bg-danger" />
          <div className="absolute -top-[3px] -left-1 size-2 rounded-full bg-danger" />
        </div>
      ) : null}
      {target !== null ? <DropMarker day={day} minutes={target} /> : null}
    </div>
  );
}

function CellItems({ row, cell }: { row: number; cell: Cell }) {
  const schedule = useSchedule();
  const posts = [...cell.posts].sort((a, b) => (a.publish_at ?? "").localeCompare(b.publish_at ?? ""));
  const shown = posts.length > VISIBLE_POSTS ? posts.slice(0, VISIBLE_POSTS - 1) : posts;
  const hidden = posts.slice(shown.length);
  const slotTime = cell.slots[0] ? formatMinutes(minutesOfDay(cell.slots[0].at, schedule.timeZone)) : null;
  return (
    <div
      className="pointer-events-none absolute inset-x-0.5 z-[1] flex min-w-0 gap-0.5 py-0.5"
      style={{ top: row * ROW_PX, height: ROW_PX }}
    >
      {shown.map((post) => (
        <div key={post.id} className="pointer-events-auto min-w-0 flex-1">
          <CalendarPostCard post={post} variant="week" />
        </div>
      ))}
      {hidden.length > 0 ? (
        <div className="pointer-events-auto shrink-0">
          <MorePostsButton
            posts={posts}
            label={`+${hidden.length}`}
            ariaLabel={`All ${posts.length} posts at ${formatMinutes(row * ROW_MINUTES)}`}
            className="h-full"
          />
        </div>
      ) : null}
      {posts.length === 0 && slotTime ? (
        <div
          data-testid="queue-slot"
          className="flex min-w-0 flex-1 items-center justify-center rounded-md border border-dashed border-line-strong px-1 text-2xs text-fg-secondary"
        >
          <span className="truncate">Queue · {slotTime}</span>
        </div>
      ) : null}
      {cell.messages.length > 0 ? (
        <div className={cn("pointer-events-auto min-w-0", posts.length === 0 && !slotTime ? "flex-1" : "shrink-0")}>
          <DmChip messages={cell.messages} compact={posts.length > 0 || Boolean(slotTime)} className="h-full" />
        </div>
      ) : null}
    </div>
  );
}

/** Where the dragged post would land, with its new time (UX-SCR-04). */
function DropMarker({ day, minutes }: { day: string; minutes: number }) {
  const schedule = useSchedule();
  const ok = !tooSoon(instantAt(day, minutes, schedule.timeZone), schedule.now);
  return (
    <div
      aria-hidden
      data-testid="drop-marker"
      className={cn(
        "pointer-events-none absolute inset-x-0.5 z-20 rounded-md border-2 px-1 text-2xs font-semibold tabular-nums",
        ok ? "border-brand bg-brand-soft text-brand-fg" : "border-danger bg-danger-soft text-danger-fg",
      )}
      style={{ top: (minutes / ROW_MINUTES) * ROW_PX, height: ROW_PX }}
    >
      {formatMinutes(minutes)}
    </div>
  );
}
