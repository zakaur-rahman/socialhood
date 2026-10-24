/**
 * Best posting times (GR-30): the API suggests an hour per weekday from the account's own posts;
 * these helpers read that answer for the composer's time picker and the Posting times drawer.
 * Weekdays number 0 = Monday … 6 = Sunday, as posting times do.
 */
import { WEEKDAYS_SHORT } from "@/lib/schedule/dates";

import type { BestTimeDay, BestTimes } from "./types";

/** "2026-10-27" (a calendar date) as a weekday, 0 = Monday. */
export function weekdayOf(date: string): number | null {
  const parsed = new Date(`${date}T12:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : (parsed.getUTCDay() + 6) % 7;
}

/** The first date on or after `today` ("2026-10-24") that falls on `weekday`. */
export function nextDateFor(weekday: number, today: string): string {
  const start = new Date(`${today}T12:00:00Z`);
  const current = (start.getUTCDay() + 6) % 7;
  start.setUTCDate(start.getUTCDate() + ((weekday - current + 7) % 7));
  return start.toISOString().slice(0, 10);
}

/** "18:00:00" as "18:00". */
export function clock(time: string): string {
  return time.slice(0, 5);
}

/** The suggestion for a weekday, or null when there is none. */
export function suggestionFor(data: BestTimes | undefined, weekday: number | null): BestTimeDay | null {
  if (!data?.enough_history || weekday === null) return null;
  const day = data.days.find((item) => item.weekday === weekday);
  return day?.local_time ? day : null;
}

/** The suggestions in order of how much they beat a typical post, best first. */
export function topSuggestions(data: BestTimes | undefined, count: number): BestTimeDay[] {
  if (!data?.enough_history) return [];
  return data.days
    .filter((day) => day.local_time)
    .sort((a, b) => (b.lift_percent ?? 0) - (a.lift_percent ?? 0) || a.weekday - b.weekday)
    .slice(0, count);
}

/** "Tue 18:00" */
export function dayTimeLabel(day: BestTimeDay): string {
  return `${WEEKDAYS_SHORT[day.weekday]} ${clock(day.local_time ?? "")}`;
}

/** Why there is nothing to show yet. */
export function notEnoughHistory(data: BestTimes): string {
  return `Not enough history for best times yet: ${data.sample_size} of ${data.min_posts} posts with engagement.`;
}

/** "12 posts, 34% above a typical post" */
export function basis(day: BestTimeDay): string {
  const posts = `${day.posts} ${day.posts === 1 ? "post" : "posts"}`;
  if (day.lift_percent == null) return posts;
  return day.lift_percent >= 0
    ? `${posts}, ${day.lift_percent}% above a typical post`
    : `${posts}, ${Math.abs(day.lift_percent)}% below a typical post`;
}
