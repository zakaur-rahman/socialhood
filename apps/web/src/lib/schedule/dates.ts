/**
 * Calendar ranges and times for the Schedule page (UX-SCR-04, FR-PUB-08). Days are calendar
 * dates in the workspace time zone ("2026-09-30"); arithmetic on them needs no zone. Weeks start
 * on Monday, as posting slots number weekdays (0 = Monday … 6 = Sunday).
 */
import { formatTime, zonedParts, zonedToDate } from "@/lib/tz";

export type CalendarView = "month" | "week" | "list";

export const CALENDAR_VIEWS: readonly CalendarView[] = ["month", "week", "list"];

/** Week rows are 30 minutes; a drag snaps to 15 (UX-SCR-04). */
export const ROW_MINUTES = 30;
export const SNAP_MINUTES = 15;
export const DAY_MINUTES = 24 * 60;
/** FR-PUB-08: a move to less than 5 minutes from now is refused. */
export const MIN_LEAD_MS = 5 * 60_000;
/** The API's calendar range limit: a month grid is six weeks. */
export const MONTH_GRID_DAYS = 42;

export const WEEKDAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
export const WEEKDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const pad = (n: number) => String(n).padStart(2, "0");

function parts(key: string): [number, number, number] {
  const [y, m, d] = key.split("-").map(Number);
  return [y, m, d];
}

function fromUtc(ms: number): string {
  const date = new Date(ms);
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

export function isDayKey(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export function addDays(key: string, days: number): string {
  const [y, m, d] = parts(key);
  return fromUtc(Date.UTC(y, m - 1, d + days));
}

/** 0 = Monday … 6 = Sunday. */
export function weekdayIndex(key: string): number {
  const [y, m, d] = parts(key);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function startOfWeek(key: string): string {
  return addDays(key, -weekdayIndex(key));
}

export function startOfMonth(key: string): string {
  const [y, m] = parts(key);
  return `${y}-${pad(m)}-01`;
}

export function addMonths(key: string, months: number): string {
  const [y, m] = parts(key);
  return fromUtc(Date.UTC(y, m - 1 + months, 1));
}

export function sameMonth(a: string, b: string): boolean {
  return a.slice(0, 7) === b.slice(0, 7);
}

/** Today in the zone. */
export function todayKey(now: Date, timeZone: string): string {
  const p = zonedParts(now, timeZone);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

export type CalendarRange = { from: string; to: string; days: string[] };

/**
 * The days a view shows around the anchor day: Monday to Sunday for Week, six whole weeks from
 * the Monday on or before the 1st for Month (42 days, the API's limit). List has no range.
 */
export function rangeFor(view: CalendarView, anchor: string): CalendarRange {
  const from = view === "month" ? startOfWeek(startOfMonth(anchor)) : startOfWeek(anchor);
  const count = view === "month" ? MONTH_GRID_DAYS : 7;
  const days = Array.from({ length: count }, (_, i) => addDays(from, i));
  return { from, to: days[days.length - 1], days };
}

/** Previous or next week or month. */
export function shiftAnchor(view: CalendarView, anchor: string, direction: -1 | 1): string {
  return view === "month" ? addMonths(anchor, direction) : addDays(anchor, 7 * direction);
}

/** "28 Sep – 4 Oct" for a week (years when not this year), "October 2026" for a month. */
export function rangeLabel(view: CalendarView, anchor: string, today: string): string {
  if (view === "month") {
    const [y, m] = parts(anchor);
    return `${MONTHS_LONG[m - 1]} ${y}`;
  }
  const { from, to } = rangeFor("week", anchor);
  const [fy, fm, fd] = parts(from);
  const [ty, tm, td] = parts(to);
  const thisYear = parts(today)[0];
  if (fy !== ty) return `${fd} ${MONTHS_SHORT[fm - 1]} ${fy} – ${td} ${MONTHS_SHORT[tm - 1]} ${ty}`;
  const year = fy === thisYear ? "" : ` ${fy}`;
  if (fm === tm) return `${fd} – ${td} ${MONTHS_SHORT[tm - 1]}${year}`;
  return `${fd} ${MONTHS_SHORT[fm - 1]} – ${td} ${MONTHS_SHORT[tm - 1]}${year}`;
}

/** "Wed", 30, "Sep", "Wednesday 30 September" for a day key. */
export function dayParts(key: string): { weekday: string; day: number; month: string; long: string } {
  const [, m, d] = parts(key);
  const index = weekdayIndex(key);
  return {
    weekday: WEEKDAYS_SHORT[index],
    day: d,
    month: MONTHS_SHORT[m - 1],
    long: `${WEEKDAYS_LONG[index]} ${d} ${MONTHS_LONG[m - 1]}`,
  };
}

/** "Wed 30 Sep": an agenda header or a dialog line. */
export function shortDay(key: string): string {
  const p = dayParts(key);
  return `${p.weekday} ${p.day} ${p.month}`;
}

/** "Today · Tue 29 Sep", "Tomorrow · Wed 30 Sep", or "Thu 1 Oct": an agenda header. */
export function agendaDayLabel(key: string, today: string): string {
  const relative =
    key === today ? "Today" : key === addDays(today, 1) ? "Tomorrow" : key === addDays(today, -1) ? "Yesterday" : null;
  return relative ? `${relative} · ${shortDay(key)}` : shortDay(key);
}

export function formatMinutes(minutes: number): string {
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
}

/** Minutes since midnight in the zone. */
export function minutesOfDay(instant: string | Date, timeZone: string): number {
  const p = zonedParts(new Date(instant), timeZone);
  return p.hour * 60 + p.minute;
}

/** The instant a day and minutes since midnight mean in the zone. */
export function instantAt(key: string, minutes: number, timeZone: string): Date {
  return zonedToDate(key, formatMinutes(minutes), timeZone) ?? new Date(NaN);
}

/** Month moves keep the post's time of day on the new day. */
export function withTimeOf(key: string, instant: string, timeZone: string): Date {
  return zonedToDate(key, formatTime(instant, timeZone), timeZone) ?? new Date(NaN);
}

/** Round down to the snap step, inside the day. */
export function snapMinutes(raw: number, step = SNAP_MINUTES): number {
  const snapped = Math.floor(raw / step) * step;
  return Math.max(0, Math.min(DAY_MINUTES - step, snapped));
}

/** FR-PUB-08: less than 5 minutes from now. */
export function tooSoon(at: Date, now: Date): boolean {
  return at.getTime() < now.getTime() + MIN_LEAD_MS;
}

export const TOO_SOON_MESSAGE = "Pick a time at least 5 minutes from now.";

/** "Times in Asia/Kolkata" (FR-PUB-08: the page states the workspace time zone). */
export function zoneLabel(timeZone: string): string {
  return timeZone.replace(/_/g, " ");
}
