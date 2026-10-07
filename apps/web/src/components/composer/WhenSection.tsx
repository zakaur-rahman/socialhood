"use client";

import { CalendarClock, ListOrdered } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { ScheduleFields, type ScheduleValue } from "@/components/inbox/ScheduleFields";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { formatDayTime } from "@/lib/tz";

import { Section } from "./Section";

export const WHEN_PREFIX = "composer-when";
export const WHEN_DATE_ID = `${WHEN_PREFIX}-date`;

export type WhenMode = "time" | "queue";

/** What Add to queue will do (FR-PUB-09), from each selected account's posting times. */
export type QueuePreview =
  | { state: "loading" }
  | { state: "no-accounts" }
  /** These accounts have no posting times: the API would refuse. */
  | { state: "missing"; handles: string[] }
  /** The first free time every selected account shares, among the next few. */
  | { state: "ready"; at: string }
  /** The next free times don't overlap; the API looks further ahead. */
  | { state: "later" }
  | { state: "error" };

/**
 * UX-SCR-13 When: a date and time in the workspace time zone, or Add to queue showing the time it
 * will take. A scheduled post shows its time here; changing it is saved with Update schedule.
 */
export function WhenSection({
  mode,
  onModeChange,
  value,
  onChange,
  timeZone,
  error,
  queue,
  scheduledAt,
  allowQueue,
  slug,
  now,
}: {
  mode: WhenMode;
  onModeChange: (mode: WhenMode) => void;
  value: ScheduleValue;
  onChange: (value: ScheduleValue) => void;
  timeZone: string;
  error: string | null;
  queue: QueuePreview;
  /** The time a scheduled post is set for. */
  scheduledAt: string | null;
  /** Drafts can be queued; a scheduled post already has its time. */
  allowQueue: boolean;
  slug: string;
  now: Date;
}) {
  const limits = { min: new Date(now.getTime() + 5 * 60_000), max: null };
  return (
    <Section id="composer-when" title="When">
      {scheduledAt ? (
        <p className="mb-3 flex items-center gap-2 text-sm">
          <CalendarClock className="size-4 text-brand-fg" aria-hidden />
          Scheduled for {formatDayTime(scheduledAt, timeZone, now)}
        </p>
      ) : null}
      {allowQueue ? (
        <ToggleGroup value={mode} onValueChange={(next) => onModeChange(next as WhenMode)} aria-label="When to publish" className="mb-3">
          <ToggleGroupItem value="time">
            <CalendarClock aria-hidden /> Pick a time
          </ToggleGroupItem>
          <ToggleGroupItem value="queue">
            <ListOrdered aria-hidden /> Add to queue
          </ToggleGroupItem>
        </ToggleGroup>
      ) : null}
      {mode === "time" || !allowQueue ? (
        <ScheduleFields idPrefix={WHEN_PREFIX} value={value} onChange={onChange} timeZone={timeZone} limits={limits} error={error} />
      ) : (
        <div className="space-y-1 text-sm" data-testid="queue-preview">
          <QueueLine queue={queue} timeZone={timeZone} now={now} slug={slug} />
          <p className="text-xs text-fg-secondary">Times are in {timeZone.replace(/_/g, " ")}.</p>
        </div>
      )}
    </Section>
  );
}

function QueueLine({ queue, timeZone, now, slug }: { queue: QueuePreview; timeZone: string; now: Date; slug: string }) {
  const scheduleLink = (
    <Link href={`/w/${slug}/schedule` as Route} className="text-brand-fg underline-offset-4 hover:underline">
      Set posting times
    </Link>
  );
  switch (queue.state) {
    case "loading":
      return (
        <p className="flex items-center gap-2 text-fg-secondary">
          <Spinner /> Finding the next free time…
        </p>
      );
    case "no-accounts":
      return <p className="text-fg-secondary">Choose an account to see its next free posting time.</p>;
    case "missing":
      return (
        <p role="alert" className="text-danger-fg">
          {queue.handles.join(", ")} {queue.handles.length === 1 ? "has" : "have"} no posting times. {scheduleLink}
        </p>
      );
    case "ready":
      return (
        <p>
          It will publish <span className="font-medium">{formatDayTime(queue.at, timeZone, now)}</span>, the next free posting time.
        </p>
      );
    case "later":
      return (
        <p className="text-fg-secondary">
          It will publish at the first posting time free for every selected account.
        </p>
      );
    case "error":
      return <p className="text-fg-secondary">The next free time couldn&apos;t be loaded. Add to queue still picks it.</p>;
  }
}

/**
 * The first time in every account's list of next free times (C-043: a post has one time, so the
 * queue needs a time free for all of them).
 */
export function sharedFreeTime(lists: string[][]): string | null {
  if (lists.length === 0) return null;
  const [first, ...rest] = lists;
  const sets = rest.map((list) => new Set(list.map((at) => new Date(at).getTime())));
  const shared = first.find((at) => sets.every((set) => set.has(new Date(at).getTime())));
  return shared ?? null;
}
