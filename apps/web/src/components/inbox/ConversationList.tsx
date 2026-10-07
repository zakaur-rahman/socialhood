"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import type { Route } from "next";
import { useEffect, useRef, useState, type KeyboardEvent, type UIEvent } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { AiMode, ConversationListItem } from "@/lib/api/types";
import { contactName, effectiveAiMode } from "@/lib/inbox/format";

import { ConversationRow, rowHeight } from "./ConversationRow";

/** TR-FE-08: lists are virtualised above 100 rows. */
export const VIRTUALIZE_ABOVE = 100;
const LOAD_MORE_WITHIN_PX = 400;

type Props = {
  items: ConversationListItem[];
  slug: string;
  selectedId: string | null;
  now: Date;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  /** Each account's AI mode, by account id: a row without its own mode shows its account's. */
  accountModes?: Record<string, AiMode>;
};

/** The conversation rows with cursor pagination; arrow keys move between rows (UX-A11Y-02). */
export function ConversationList({
  items,
  slug,
  selectedId,
  now,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  accountModes = {},
}: Props) {
  const aiModeOf = (item: ConversationListItem) => effectiveAiMode(item, accountModes[item.social_account_id]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const virtual = items.length > VIRTUALIZE_ABOVE;
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual returns functions React Compiler must not memoise; this component opts out.
  const virtualizer = useVirtualizer({
    count: virtual ? items.length : 0,
    getScrollElement: () => scrollRef.current,
    // Rows are two lines, or three with badges; both heights are fixed (ConversationRow).
    estimateSize: (index) => (items[index] ? rowHeight(items[index], now, aiModeOf(items[index])) : 68),
    overscan: 8,
    getItemKey: (index) => items[index]?.id ?? index,
  });
  const announcement = useUnreadAnnouncement(items);

  const loadMoreIfNear = (element: HTMLElement) => {
    if (!hasNextPage || isFetchingNextPage) return;
    if (element.scrollTop + element.clientHeight >= element.scrollHeight - LOAD_MORE_WITHIN_PX) fetchNextPage();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const current = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>("[data-index]");
    const index = current ? Number(current.dataset.index) : -1;
    const next = Math.min(items.length - 1, Math.max(0, index + (event.key === "ArrowDown" ? 1 : -1)));
    if (next === index) return;
    event.preventDefault();
    if (virtual) virtualizer.scrollToIndex(next);
    requestAnimationFrame(() => {
      scrollRef.current?.querySelector<HTMLElement>(`[data-index="${next}"]`)?.focus();
    });
    if (next >= items.length - 3 && hasNextPage && !isFetchingNextPage) fetchNextPage();
  };

  const row = (item: ConversationListItem, index: number) => (
    <ConversationRow
      item={item}
      index={index}
      href={`/w/${slug}/inbox/${item.id}` as Route}
      selected={item.id === selectedId}
      now={now}
      aiMode={aiModeOf(item)}
    />
  );

  return (
    <div
      ref={scrollRef}
      onScroll={(event: UIEvent<HTMLDivElement>) => loadMoreIfNear(event.currentTarget)}
      onKeyDown={onKeyDown}
      className="min-h-0 flex-1 overflow-y-auto"
      data-virtual={virtual}
    >
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      {virtual ? (
        <ul aria-label="Conversations" className="relative" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => (
            <li
              key={v.key}
              className="absolute inset-x-0 top-0"
              style={{ height: v.size, transform: `translateY(${v.start}px)` }}
            >
              {row(items[v.index], v.index)}
            </li>
          ))}
        </ul>
      ) : (
        <ul aria-label="Conversations">
          {items.map((item, index) => (
            <li key={item.id}>{row(item, index)}</li>
          ))}
        </ul>
      )}
      {isFetchingNextPage ? <RowSkeletons count={2} /> : null}
    </div>
  );
}

/** §4.7 loading: skeleton rows shaped like the real row, never a spinner. */
export function RowSkeletons({ count = 8 }: { count?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading conversations">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex h-[68px] items-center gap-3 px-4 py-3">
          <Skeleton className="size-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * UX-A11Y-03: announce a conversation that becomes unread, once, politely: one that was read,
 * or a new one with newer activity than anything listed before. (The list is keyed by its
 * filters, so switching views starts over instead of announcing the new view's rows.)
 */
function useUnreadAnnouncement(items: ConversationListItem[]): string {
  const seen = useRef<{ unread: Map<string, number>; newest: string } | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => {
    const previous = seen.current;
    seen.current = {
      unread: new Map(items.map((item) => [item.id, item.unread_count])),
      newest: items.reduce((max, item) => ((item.last_message_at ?? "") > max ? (item.last_message_at ?? "") : max), ""),
    };
    if (!previous) return;
    const fresh = items.find((item) => {
      if (item.unread_count === 0) return false;
      const before = previous.unread.get(item.id);
      return before === undefined ? (item.last_message_at ?? "") > previous.newest : before === 0;
    });
    if (fresh) setMessage(`New message from ${contactName(fresh.contact, fresh.platform)}`);
  }, [items]);
  return message;
}
