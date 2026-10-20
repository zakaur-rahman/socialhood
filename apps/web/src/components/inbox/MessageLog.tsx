"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Message } from "@/lib/api/types";
import { dayKey } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { DateSeparator } from "./DateSeparator";

/** TR-FE-08: virtualised above 100 rows. */
const VIRTUALIZE_ABOVE = 100;
/** UX-INB-06: older pages load 200 px from the top. */
const LOAD_OLDER_WITHIN_PX = 200;
const STICK_TO_BOTTOM_PX = 120;
const GROUP_GAP_MS = 5 * 60_000;

export type LogRow =
  | { type: "date"; key: string; at: string }
  | { type: "message"; key: string; message: Message; groupStart: boolean; groupEnd: boolean };

function side(message: Message): "in" | "out" | "system" {
  if (message.direction === "system" || message.kind === "system") return "system";
  return message.direction === "inbound" ? "in" : "out";
}

/**
 * Date separators and groups (UX-INB-06): consecutive bubbles from the same side within
 * 5 minutes stack 4 px apart; the last of a group carries the customer's avatar.
 */
export function buildRows(messages: Message[], timeZone: string): LogRow[] {
  const rows: LogRow[] = [];
  let lastDay = "";
  messages.forEach((message, i) => {
    const day = dayKey(message.occurred_at, timeZone);
    if (day !== lastDay) {
      rows.push({ type: "date", key: `date-${day}`, at: message.occurred_at });
      lastDay = day;
    }
    const previous = messages[i - 1];
    const next = messages[i + 1];
    const joins = (a: Message | undefined, b: Message | undefined) =>
      Boolean(a && b) &&
      side(a!) === side(b!) &&
      side(a!) !== "system" &&
      dayKey(a!.occurred_at, timeZone) === dayKey(b!.occurred_at, timeZone) &&
      Math.abs(new Date(b!.occurred_at).getTime() - new Date(a!.occurred_at).getTime()) <= GROUP_GAP_MS;
    rows.push({
      type: "message",
      key: message.client_id ? `c-${message.client_id}` : message.id,
      message,
      groupStart: !joins(previous, message),
      groupEnd: !joins(message, next),
    });
  });
  return rows;
}

type Props = {
  messages: Message[];
  timeZone: string;
  now: Date;
  label: string;
  loading: boolean;
  hasOlder: boolean;
  loadingOlder: boolean;
  loadOlder: () => void;
  /** The words a screen reader hears for a new inbound message; without it nothing is announced. */
  announce?: (message: Message) => string;
  renderMessage: (message: Message, row: Extract<LogRow, { type: "message" }>) => ReactNode;
};

type Snapshot = { firstKey: string | null; lastKey: string | null; scrollHeight: number; scrollTop: number; atBottom: boolean };

/**
 * The message area (UX-INB-06, UX-A11Y-03): opens at the newest message, loads older pages
 * near the top while keeping the scroll position, follows new messages when already at the
 * bottom, and is a log. The log itself is not live: a polite region beside it announces only a new
 * inbound message, so older pages, virtualised rows and our own sends stay silent (UI-ISS-063).
 */
export function MessageLog({ messages, timeZone, now, label, loading, hasOlder, loadingOlder, loadOlder, announce, renderMessage }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => buildRows(messages, timeZone), [messages, timeZone]);
  const virtual = rows.length > VIRTUALIZE_ABOVE;
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual returns functions React Compiler must not memoise; this component opts out.
  const virtualizer = useVirtualizer({
    count: virtual ? rows.length : 0,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (rows[index]?.type === "date" ? 32 : 64),
    overscan: 10,
    getItemKey: (index) => rows[index]?.key ?? index,
  });
  const snapshot = useRef<Snapshot>({ firstKey: null, lastKey: null, scrollHeight: 0, scrollTop: 0, atBottom: true });

  // The oldest message, not the first row: a date separator keeps its key when older
  // messages from the same day load above.
  const firstKey = rows.find((row) => row.type === "message")?.key ?? null;
  const lastRow = rows[rows.length - 1];
  const lastKey = lastRow?.key ?? null;

  // The last row changed after the first load: say so when it is a customer's message. Set during
  // render (the previous-value pattern), so the text and the row it belongs to change together.
  const [announced, setAnnounced] = useState<{ key: string | null | undefined; text: string }>({ key: undefined, text: "" });
  if (!loading && lastKey !== announced.key) {
    const inbound = lastRow?.type === "message" && lastRow.message.direction === "inbound" ? lastRow.message : null;
    setAnnounced({ key: lastKey, text: announced.key !== undefined && inbound && announce ? announce(inbound) : "" });
  }

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const prev = snapshot.current;
    const toBottom = () => {
      if (virtual && rows.length > 0) virtualizer.scrollToIndex(rows.length - 1, { align: "end" });
      el.scrollTop = el.scrollHeight;
    };
    if (!prev.lastKey && lastKey) {
      toBottom(); // first render with messages: open at the newest
    } else if (firstKey !== prev.firstKey && prev.firstKey && rows.some((row) => row.key === prev.firstKey)) {
      el.scrollTop = prev.scrollTop + (el.scrollHeight - prev.scrollHeight); // older page above: stay put
    } else if (lastKey !== prev.lastKey) {
      const mine = lastRow?.type === "message" && lastRow.message.direction === "outbound";
      if (prev.atBottom || mine) toBottom();
    }
    snapshot.current = {
      firstKey,
      lastKey,
      scrollHeight: el.scrollHeight,
      scrollTop: el.scrollTop,
      atBottom: el.scrollHeight - el.scrollTop - el.clientHeight <= STICK_TO_BOTTOM_PX,
    };
  });

  // A first page shorter than the pane: fetch older ones until it scrolls.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || loading || loadingOlder || !hasOlder) return;
    if (el.scrollHeight <= el.clientHeight && rows.length > 0) loadOlder();
  }, [rows.length, loading, loadingOlder, hasOlder, loadOlder]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    snapshot.current = {
      ...snapshot.current,
      scrollHeight: el.scrollHeight,
      scrollTop: el.scrollTop,
      atBottom: el.scrollHeight - el.scrollTop - el.clientHeight <= STICK_TO_BOTTOM_PX,
    };
    if (el.scrollTop <= LOAD_OLDER_WITHIN_PX && hasOlder && !loadingOlder) loadOlder();
  };

  const renderRow = (row: LogRow) =>
    row.type === "date" ? (
      <DateSeparator at={row.at} timeZone={timeZone} now={now} />
    ) : (
      <div className={cn(row.groupStart ? "pt-3" : "pt-1")}>{renderMessage(row.message, row)}</div>
    );

  return (
    <>
    <div
      ref={scrollRef}
      onScroll={onScroll}
      role="log"
      aria-live="off"
      aria-label={label}
      aria-busy={loading || loadingOlder}
      tabIndex={0}
      className="min-h-0 flex-1 overflow-y-auto bg-canvas focus-visible:-outline-offset-2 px-4 py-3 [overflow-anchor:none]"
      data-virtual={virtual}
    >
      {loadingOlder ? <OlderSkeleton /> : null}
      {loading ? (
        <ThreadSkeleton />
      ) : virtual ? (
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => (
            <div
              key={v.key}
              data-index={v.index}
              ref={virtualizer.measureElement}
              className="absolute inset-x-0 top-0"
              style={{ transform: `translateY(${v.start}px)` }}
            >
              {renderRow(rows[v.index])}
            </div>
          ))}
        </div>
      ) : (
        rows.map((row) => <div key={row.key}>{renderRow(row)}</div>)
      )}
    </div>
    <div role="status" aria-live="polite" aria-atomic="true" className="sr-only" data-testid="message-announcer">
      {announced.text}
    </div>
    </>
  );
}

function OlderSkeleton() {
  return (
    <div className="flex justify-center py-2" aria-hidden>
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

/** Bubble-shaped placeholders while the first page loads (§4.7: never a spinner). */
function ThreadSkeleton() {
  return (
    <div className="flex flex-col gap-3 pt-6" role="status" aria-label="Loading messages">
      <Skeleton className="h-10 w-1/2 rounded-2xl" />
      <Skeleton className="h-14 w-2/5 self-end rounded-2xl" />
      <Skeleton className="h-10 w-3/5 rounded-2xl" />
      <Skeleton className="h-10 w-1/3 self-end rounded-2xl" />
    </div>
  );
}
