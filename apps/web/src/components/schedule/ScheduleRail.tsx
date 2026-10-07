"use client";

import { Clock, Hash } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { usePostingSlotsFor, type ScheduledPostPages } from "@/lib/api/queries/calendar";
import type { Calendar, ScheduledPostSummary, SocialAccount } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { canMove, captionLine, postFormatLabel, summarizeSlots } from "@/lib/schedule/format";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

import { useCalendarDnd, useDragSelector } from "./calendar-dnd";
import { postLabel } from "./CalendarPostCard";
import { AccountAvatar, PostMenu, PostThumbnail } from "./post-parts";
import { useSchedule } from "./schedule-context";

const RAIL_DRAFTS = 8;

type DraftsQuery = {
  data?: ScheduledPostPages;
  isPending: boolean;
  isError: boolean;
  error?: unknown;
  refetch?: () => unknown;
};

/**
 * UX-SCR-04 right rail (250 px at ≥ 1440 px, a drawer below that): Unscheduled drafts, dragged
 * onto the calendar to schedule them; posts published in the last 24 hours against each account's
 * limit; the next free queue time and posting times, with Edit posting times (UX-SCR-14).
 */
export function ScheduleRail({
  calendar,
  drafts,
  accounts,
  dragEnabled,
  onEditPostingTimes,
  onHashtagGroups,
  onShowAllDrafts,
}: {
  calendar?: Calendar;
  drafts: DraftsQuery;
  accounts: SocialAccount[];
  /** Inline beside the grid; in the drawer the grid is covered, so drafts use their menu. */
  dragEnabled: boolean;
  onEditPostingTimes: () => void;
  onHashtagGroups: () => void;
  onShowAllDrafts: () => void;
}) {
  const schedule = useSchedule();
  const items = drafts.data?.pages.flatMap((page) => page.items) ?? [];
  const figures = new Map((calendar?.accounts ?? []).map((a) => [a.social_account_id, a]));
  const slots = usePostingSlotsFor(
    schedule.wid,
    accounts.map((a) => a.id),
  );

  return (
    <div className="space-y-5 text-sm">
      <RailSection title="Unscheduled drafts" count={drafts.isPending ? undefined : items.length}>
        {drafts.isPending ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading drafts">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : drafts.isError ? (
          <ErrorState size="compact" error={drafts.error} onRetry={drafts.refetch ? () => void drafts.refetch?.() : undefined} />
        ) : items.length === 0 ? (
          <EmptyState size="compact" title="No drafts" body="Posts you start and don't schedule wait here." />
        ) : (
          <>
            <ul className="space-y-1.5" aria-label="Unscheduled drafts">
              {items.slice(0, RAIL_DRAFTS).map((post) => (
                <DraftCard key={post.id} post={post} dragEnabled={dragEnabled} />
              ))}
            </ul>
            {items.length > RAIL_DRAFTS || drafts.data?.pages.at(-1)?.next_cursor ? (
              <Button variant="link" className="h-auto px-0" onClick={onShowAllDrafts}>
                Show all drafts
              </Button>
            ) : null}
          </>
        )}
      </RailSection>

      <RailSection title="Published in the last 24 hours">
        {accounts.length === 0 ? (
          <NoAccounts />
        ) : (
          <ul className="space-y-2">
            {accounts.map((account) => {
              const figure = figures.get(account.id);
              const used = figure?.published_24h ?? 0;
              const limit = figure?.publishing_limit ?? 0;
              return (
                <li key={account.id} className="flex items-start gap-2">
                  <AccountAvatar account={account} accountId={account.id} />
                  {figure && limit > 0 ? (
                    <Meter
                      className="min-w-0 flex-1"
                      label={
                        <>
                          {accountLabel(account)}{" "}
                          <span className="sr-only">published in the last 24 hours</span>
                        </>
                      }
                      value={used}
                      max={limit}
                      valueText={`${used} of ${limit}`}
                    />
                  ) : (
                    <div className="flex min-w-0 flex-1 items-baseline justify-between gap-3 text-xs">
                      <span className="min-w-0 truncate text-fg-secondary">{accountLabel(account)}</span>
                      <span className="text-fg-secondary tabular-nums">–</span>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </RailSection>

      <RailSection title="Queue">
        {accounts.length === 0 ? (
          <NoAccounts />
        ) : (
          <ul className="space-y-3">
            {accounts.map((account, i) => {
              const next = figures.get(account.id)?.next_free_at;
              const posting = slots[i];
              return (
                <li key={account.id} className="space-y-0.5">
                  {accounts.length > 1 ? <p className="text-xs font-medium">{accountLabel(account)}</p> : null}
                  <p className="flex justify-between gap-2 text-xs">
                    <span className="text-fg-secondary">Next free time</span>
                    <span className="text-right tabular-nums">
                      {next ? formatDayTime(next, schedule.timeZone, schedule.now) : calendar ? "None" : "–"}
                    </span>
                  </p>
                  <p className="flex justify-between gap-2 text-xs">
                    <span className="shrink-0 text-fg-secondary">Posting times</span>
                    <span className="text-right">
                      {posting?.data ? summarizeSlots(posting.data.slots) : posting?.isError ? "Didn't load" : "–"}
                    </span>
                  </p>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex flex-col items-start gap-1 pt-1">
          <Button variant="secondary" size="sm" onClick={onEditPostingTimes} disabled={accounts.length === 0}>
            <Clock aria-hidden /> Edit posting times
          </Button>
          <Button variant="ghost" size="sm" className="text-fg-secondary" onClick={onHashtagGroups}>
            <Hash aria-hidden /> Hashtag groups
          </Button>
        </div>
      </RailSection>
    </div>
  );
}

function RailSection({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className={cn(EYEBROW, "flex items-center gap-1.5")}>
        {title}
        {count !== undefined ? <span className="tabular-nums">{count}</span> : null}
      </h2>
      {children}
    </section>
  );
}

function NoAccounts() {
  const schedule = useSchedule();
  return (
    <EmptyState
      size="compact"
      title="No Instagram account"
      action={
        <Link href={`/w/${schedule.slug}/settings/connections` as Route} className="text-brand-fg underline-offset-4 hover:underline">
          Connect an Instagram account
        </Link>
      }
    />
  );
}

/** A draft in the rail: drag it onto the calendar, or use its menu (Schedule for…, Add to queue). */
function DraftCard({ post, dragEnabled }: { post: ScheduledPostSummary; dragEnabled: boolean }) {
  const schedule = useSchedule();
  const { pointerDown, consumeClick } = useCalendarDnd();
  const dragging = useDragSelector((state) => state?.source.post.id === post.id);
  const draggable = dragEnabled && canMove(post);
  return (
    <CardInset
      asChild
      padding="compact"
      className={cn("p-1.5 select-none", draggable && "cursor-grab active:cursor-grabbing", dragging && "opacity-40")}
    >
     <li
      data-draft-id={post.id}
      onPointerDown={draggable ? (event) => pointerDown(event, { post, from: "rail" }) : undefined}
      className="flex items-center gap-2"
     >
      <Link
        href={schedule.composerHref(post)}
        draggable={false}
        aria-label={postLabel(post, schedule.timeZone, schedule.now)}
        onClick={(event) => {
          if (consumeClick()) event.preventDefault();
        }}
        className="flex min-w-0 flex-1 items-center gap-2"
      >
        <PostThumbnail post={post} size={40} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm">{captionLine(post.caption)}</span>
          <span className="block truncate text-xs text-fg-secondary">
            {postFormatLabel(post)}
            {draggable ? " · drag onto the calendar" : ""}
          </span>
        </span>
      </Link>
      <PostMenu post={post} size="sm" />
     </li>
    </CardInset>
  );
}
