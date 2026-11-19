/**
 * GR-45 snooze times, in the workspace timezone: the three presets and the limits the API holds
 * (in the future, at most 90 days ahead).
 */
import { dayKey, zonedParts, zonedToDate } from "@/lib/tz";

export const SNOOZE_MAX_DAYS = 90;
const WAKE_HOUR = "09:00";
const LATER_HOURS = 3;

export type SnoozePreset = { key: "later" | "tomorrow" | "next_week"; label: string; at: Date };

/** The calendar day ``days`` after a "YYYY-MM-DD" day. */
function addDays(key: string, days: number): string {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

const WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * Later today (three hours on, to the next quarter hour, only while that is still today),
 * tomorrow at 9:00, and next Monday at 9:00.
 */
export function snoozePresets(now: Date, timeZone: string): SnoozePreset[] {
  const today = dayKey(now, timeZone);
  const presets: SnoozePreset[] = [];
  const later = new Date(Math.ceil((now.getTime() + LATER_HOURS * 3_600_000) / 900_000) * 900_000);
  if (dayKey(later, timeZone) === today) presets.push({ key: "later", label: "Later today", at: later });
  const tomorrow = zonedToDate(addDays(today, 1), WAKE_HOUR, timeZone);
  if (tomorrow) presets.push({ key: "tomorrow", label: "Tomorrow", at: tomorrow });
  // Monday is 1; from a Monday "next week" is seven days on, from a Sunday it is tomorrow.
  const weekday = WEEKDAY.indexOf(zonedParts(now, timeZone).weekday) + 1;
  const monday = zonedToDate(addDays(today, weekday === 0 ? 7 : 8 - weekday), WAKE_HOUR, timeZone);
  if (monday) presets.push({ key: "next_week", label: "Next week", at: monday });
  return presets;
}

/** The earliest and latest times a snooze can end (the API checks its own clock too). */
export function snoozeLimits(now: Date): { min: Date; max: Date } {
  return { min: new Date(now.getTime() + 60_000), max: new Date(now.getTime() + (SNOOZE_MAX_DAYS - 1) * 86_400_000) };
}
