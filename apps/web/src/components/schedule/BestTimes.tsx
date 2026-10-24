"use client";

import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBestTimes } from "@/lib/api/queries/scheduledPosts";
import {
  basis,
  clock,
  dayTimeLabel,
  nextDateFor,
  notEnoughHistory,
  suggestionFor,
  topSuggestions,
  weekdayOf,
} from "@/lib/publishing/best-times";
import { WEEKDAYS_LONG, WEEKDAYS_SHORT } from "@/lib/schedule/dates";
import { EYEBROW } from "@/styles/tokens";

/**
 * GR-30, beside the composer's time picker: the account's best time for the chosen day (or its
 * best days, before one is chosen), with a button to use it. Worked out from the account's own
 * posts; says so when there is too little history.
 */
export function BestTimeHint({
  wid,
  accountId,
  handle,
  date,
  today,
  onUse,
}: {
  wid: string;
  accountId: string;
  handle: string;
  /** The picked date ("2026-10-27"), or "" before one is picked. */
  date: string;
  /** Today in the workspace time zone, to find a weekday's next date. */
  today: string;
  onUse: (value: { date: string; time: string }) => void;
}) {
  const query = useBestTimes(wid, accountId);
  if (query.isPending) return <Skeleton className="mt-3 h-5 w-64" aria-label="Loading best times" />;
  if (query.isError) return null; // a hint: the picker works without it
  const data = query.data;
  if (!data.enough_history) {
    return (
      <p className="mt-3 flex items-start gap-2 text-xs text-fg-secondary" data-testid="best-times-hint">
        <Sparkles className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        {notEnoughHistory(data)}
      </p>
    );
  }
  const weekday = date ? weekdayOf(date) : null;
  const day = suggestionFor(data, weekday);
  if (date && weekday !== null && !day) {
    return (
      <p className="mt-3 flex items-start gap-2 text-xs text-fg-secondary" data-testid="best-times-hint">
        <Sparkles className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        No best time for {handle} on {WEEKDAYS_LONG[weekday]}s yet: it hasn&apos;t posted then often enough.
      </p>
    );
  }
  if (day && day.local_time) {
    const time = clock(day.local_time);
    return (
      <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-secondary" data-testid="best-times-hint">
        <Sparkles className="size-3.5 shrink-0" aria-hidden />
        <span>
          Best time for {handle} on {WEEKDAYS_LONG[day.weekday]}s: <span className="font-medium text-fg">{time}</span> ({basis(day)})
        </span>
        <Button type="button" variant="ghost" size="sm" onClick={() => onUse({ date, time })}>
          Use {time}
        </Button>
      </p>
    );
  }
  const top = topSuggestions(data, 3);
  if (top.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-fg-secondary" data-testid="best-times-hint">
      <Sparkles className="size-3.5 shrink-0" aria-hidden />
      <span>Best times for {handle}:</span>
      {top.map((item) => (
        <Button
          key={item.weekday}
          type="button"
          variant="secondary"
          size="sm"
          aria-label={`Use ${WEEKDAYS_LONG[item.weekday]} ${clock(item.local_time ?? "")}`}
          onClick={() => onUse({ date: nextDateFor(item.weekday, today), time: clock(item.local_time ?? "") })}
        >
          {dayTimeLabel(item)}
        </Button>
      ))}
    </div>
  );
}

/**
 * GR-30, in the Posting times drawer: the suggested hour for each weekday, with a button that
 * adds it to the account's times.
 */
export function BestTimesPanel({
  wid,
  accountId,
  existing,
  onAdd,
}: {
  wid: string;
  accountId: string;
  /** The week's times as edited: "HH:MM" per weekday. */
  existing: string[][];
  onAdd: (weekday: number, time: string) => void;
}) {
  const query = useBestTimes(wid, accountId);
  return (
    <section aria-label="Best times" className="mt-4" data-testid="best-times-panel">
      <p className={EYEBROW}>Best times</p>
      {query.isPending ? (
        <Skeleton className="mt-2 h-24 w-full" aria-label="Loading best times" />
      ) : query.isError ? (
        <p className="mt-1 text-sm text-fg-secondary">Best times couldn&apos;t be loaded.</p>
      ) : !query.data.enough_history ? (
        <p className="mt-1 text-sm text-fg-secondary">{notEnoughHistory(query.data)}</p>
      ) : (
        <>
          <ul className="mt-1 divide-y divide-line-subtle" aria-label="Best time per weekday">
            {query.data.days.map((day) => {
              const time = day.local_time ? clock(day.local_time) : null;
              const added = time ? existing[day.weekday]?.includes(time) : false;
              return (
                <li key={day.weekday} className="flex items-center gap-2 py-1.5 text-sm">
                  <span className="w-10 shrink-0 font-medium">{WEEKDAYS_SHORT[day.weekday]}</span>
                  {time ? (
                    <>
                      <span className="tabular-nums">{time}</span>
                      <span className="min-w-0 flex-1 truncate text-xs text-fg-secondary">{basis(day)}</span>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={added}
                        aria-label={`Add ${time} on ${WEEKDAYS_LONG[day.weekday]}`}
                        onClick={() => onAdd(day.weekday, time)}
                      >
                        {added ? "Added" : "Add"}
                      </Button>
                    </>
                  ) : (
                    <span className="text-xs text-fg-secondary">Not enough posts at one hour</span>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-2 text-xs text-fg-secondary">{query.data.method}</p>
        </>
      )}
    </section>
  );
}
