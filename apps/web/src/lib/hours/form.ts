import type { AutoModeName, BusinessHours, BusinessHoursUpdate, DaySchedule } from "@/lib/api/types";

/** Monday first, as the API numbers the days (0 to 6). */
export const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

export const DEFAULT_RANGE = { start: "09:00", end: "17:00" } as const;
export const MAX_RANGES = 6;

/** What the hours form edits: all seven days, the away message and Auto mode's hours. */
export type HoursForm = {
  enabled: boolean;
  days: DaySchedule[];
  away_enabled: boolean;
  away_message: string;
  auto_mode: AutoModeName;
};

function weekdays(): DaySchedule[] {
  return DAY_NAMES.map((_, day) => ({ day, ranges: day < 5 ? [{ ...DEFAULT_RANGE }] : [] }));
}

/**
 * The form for saved hours. Hours that were never saved start off, but with Monday to Friday 09:00
 * to 17:00 filled in, so switching them on gives a sensible week to adjust.
 */
export function toForm(hours: BusinessHours | null | undefined): HoursForm {
  if (!hours || !hours.configured) {
    return { enabled: false, days: weekdays(), away_enabled: false, away_message: "", auto_mode: "always" };
  }
  return {
    enabled: hours.enabled,
    days: DAY_NAMES.map((_, day) => {
      const saved = hours.days.find((d) => d.day === day);
      return { day, ranges: (saved?.ranges ?? []).map((range) => ({ ...range })) };
    }),
    away_enabled: hours.away_enabled,
    away_message: hours.away_message ?? "",
    auto_mode: hours.auto_mode,
  };
}

/** The request: one entry per day, so an error's `days.3.…` path is the same day in the form. */
export function toBody(form: HoursForm): BusinessHoursUpdate {
  return {
    enabled: form.enabled,
    days: form.days.map((d) => ({ day: d.day, ranges: d.ranges.map((r) => ({ start: r.start, end: r.end })) })),
    away_enabled: form.away_enabled,
    away_message: form.away_message.trim() || null,
    auto_mode: form.auto_mode,
  };
}

/** A time input can't show 24:00, so a closing time at midnight reads 00:00 ... */
export function displayEnd(end: string): string {
  return end === "24:00" ? "00:00" : end;
}

/** ... and a closing time of 00:00 means midnight at the end of that day. */
export function parseEnd(value: string): string {
  return value === "00:00" ? "24:00" : value;
}

/** A problem the form can see before it asks the API, or null. */
export function localProblem(form: HoursForm): string | null {
  if (form.enabled && form.days.every((d) => d.ranges.length === 0)) {
    return "Add at least one opening time, or turn business hours off.";
  }
  if (form.away_enabled && form.away_message.trim() === "") {
    return "Write the message to send when you're closed.";
  }
  return null;
}

const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function rangeText(ranges: DaySchedule["ranges"]): string {
  return ranges.map((r) => `${r.start} to ${displayEnd(r.end) === "00:00" ? "midnight" : displayEnd(r.end)}`).join(", ");
}

/** "Mon to Fri 09:00 to 17:00; Sat 10:00 to 14:00": days with the same hours are grouped. */
export function summary(days: readonly DaySchedule[]): string {
  const open = days.filter((d) => d.ranges.length > 0);
  if (open.length === 0) return "Closed all week";
  const groups: { first: number; last: number; text: string }[] = [];
  for (const d of open) {
    const text = rangeText(d.ranges);
    const last = groups[groups.length - 1];
    if (last && last.text === text && last.last === d.day - 1) last.last = d.day;
    else groups.push({ first: d.day, last: d.day, text });
  }
  return groups
    .map((g) => `${g.first === g.last ? SHORT[g.first] : `${SHORT[g.first]} to ${SHORT[g.last]}`} ${g.text}`)
    .join("; ");
}
