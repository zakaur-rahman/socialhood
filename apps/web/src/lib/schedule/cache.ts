/**
 * Cache patching for the Schedule page (TR-FE-04). Moves patch every loaded calendar at once so
 * the card moves before the API answers (F-13 "Calendar moves"); refusals put the snapshot back.
 * Only calendars already loaded are touched.
 */
import type { QueryClient, QueryKey } from "@tanstack/react-query";

import { keys } from "@/lib/api/queries/keys";
import type { Calendar, CalendarMessage, ScheduledMessage, ScheduledPostSummary } from "@/lib/api/types";
import { dayKey } from "@/lib/tz";

export type CalendarSnapshot = [QueryKey, Calendar | undefined][];

function inRange(calendar: Calendar, publishAt: string | null | undefined): boolean {
  if (!publishAt) return false;
  const key = dayKey(publishAt, calendar.timezone);
  return key >= calendar.start && key <= calendar.end;
}

function byTime(a: ScheduledPostSummary, b: ScheduledPostSummary): number {
  return (a.publish_at ?? "").localeCompare(b.publish_at ?? "");
}

/** The calendar with this post in its new place, added or dropped as its time falls in or out. */
export function withPost(calendar: Calendar, post: ScheduledPostSummary): Calendar {
  const rest = calendar.posts.filter((item) => item.id !== post.id);
  const posts = inRange(calendar, post.publish_at) ? [...rest, post].sort(byTime) : rest;
  return { ...calendar, posts };
}

export function patchCalendars(queryClient: QueryClient, wid: string, post: ScheduledPostSummary): void {
  queryClient.setQueriesData<Calendar>({ queryKey: keys.calendars(wid) }, (calendar) =>
    calendar ? withPost(calendar, post) : calendar,
  );
}

export function removeFromCalendars(queryClient: QueryClient, wid: string, id: string): void {
  queryClient.setQueriesData<Calendar>({ queryKey: keys.calendars(wid) }, (calendar) =>
    calendar ? { ...calendar, posts: calendar.posts.filter((item) => item.id !== id) } : calendar,
  );
}

export async function snapshotCalendars(queryClient: QueryClient, wid: string): Promise<CalendarSnapshot> {
  await queryClient.cancelQueries({ queryKey: keys.calendars(wid) });
  return queryClient.getQueriesData<Calendar>({ queryKey: keys.calendars(wid) });
}

export function restoreCalendars(queryClient: QueryClient, snapshot: CalendarSnapshot): void {
  for (const [key, data] of snapshot) queryClient.setQueryData(key, data);
}

/** Lists, the right rail and the calendars' figures read the server again. */
export function refreshSchedule(queryClient: QueryClient, wid: string): Promise<unknown> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: keys.calendars(wid) }),
    queryClient.invalidateQueries({ queryKey: keys.scheduledPostLists(wid) }),
  ]);
}

/** scheduled_post.updated (TR-RT-03): the post moves at once, then the figures refresh. */
export function applyScheduledPost(queryClient: QueryClient, wid: string, post: ScheduledPostSummary): void {
  patchCalendars(queryClient, wid, post);
  void refreshSchedule(queryClient, wid);
}

/** scheduled_message.updated: the Messages layer keeps the DM's new time or status. */
export function applyCalendarMessage(queryClient: QueryClient, wid: string, message: ScheduledMessage): void {
  queryClient.setQueriesData<Calendar>({ queryKey: keys.calendars(wid) }, (calendar) => {
    if (!calendar) return calendar;
    const existing = calendar.messages.find((item) => item.id === message.id);
    if (!existing) return calendar;
    const rest = calendar.messages.filter((item) => item.id !== message.id);
    const keep = message.status !== "canceled" && inRange(calendar, message.send_at);
    const next: CalendarMessage = { ...existing, ...message };
    return { ...calendar, messages: keep ? [...rest, next].sort((a, b) => a.send_at.localeCompare(b.send_at)) : rest };
  });
}
