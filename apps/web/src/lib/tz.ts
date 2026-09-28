/**
 * Dates in the workspace timezone (UX-INB-06 meta times, date separators, F-10 scheduling).
 * Intl does the conversions; an unknown zone falls back to UTC rather than throwing.
 */

type Parts = { year: number; month: number; day: number; hour: number; minute: number; weekday: string };

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(timeZone: string): Intl.DateTimeFormat {
  let f = formatters.get(timeZone);
  if (!f) {
    try {
      f = new Intl.DateTimeFormat("en-US", {
        timeZone,
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
        weekday: "short",
        hourCycle: "h23",
      });
    } catch {
      f = formatter("UTC");
    }
    formatters.set(timeZone, f);
  }
  return f;
}

export function zonedParts(date: Date, timeZone: string): Parts {
  const out: Record<string, string> = {};
  for (const part of formatter(timeZone).formatToParts(date)) out[part.type] = part.value;
  return {
    year: Number(out.year),
    month: Number(out.month),
    day: Number(out.day),
    hour: Number(out.hour) % 24,
    minute: Number(out.minute),
    weekday: out.weekday,
  };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

/** "18:30" */
export function formatTime(iso: string | Date, timeZone: string): string {
  const p = zonedParts(new Date(iso), timeZone);
  return `${pad(p.hour)}:${pad(p.minute)}`;
}

/** "2026-09-28": the calendar day in the zone, for grouping. */
export function dayKey(iso: string | Date, timeZone: string): string {
  const p = zonedParts(new Date(iso), timeZone);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

function dayNumber(key: string): number {
  const [y, m, d] = key.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

/** Today, Yesterday, Tomorrow, "Mon 3 Mar" this year, "3 Mar 2025" otherwise (UX-INB-06). */
export function formatDay(iso: string | Date, timeZone: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const diff = dayNumber(dayKey(date, timeZone)) - dayNumber(dayKey(now, timeZone));
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  const p = zonedParts(date, timeZone);
  if (p.year === zonedParts(now, timeZone).year) return `${p.weekday} ${p.day} ${MONTHS[p.month - 1]}`;
  return `${p.day} ${MONTHS[p.month - 1]} ${p.year}`;
}

/** "Today 18:30", "Mon 3 Mar 18:30" (UX-INB-10 time chip, F-10). */
export function formatDayTime(iso: string | Date, timeZone: string, now: Date = new Date()): string {
  return `${formatDay(iso, timeZone, now)} ${formatTime(iso, timeZone)}`;
}

/** Minutes the zone is ahead of UTC at this instant. */
function offsetMinutes(instant: number, timeZone: string): number {
  const p = zonedParts(new Date(instant), timeZone);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
  return Math.round((asUtc - Math.floor(instant / 60_000) * 60_000) / 60_000);
}

/** The instant a wall-clock date ("2026-09-28") and time ("18:30") mean in the zone. */
export function zonedToDate(date: string, time: string, timeZone: string): Date | null {
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const tm = /^(\d{2}):(\d{2})$/.exec(time);
  if (!dm || !tm) return null;
  const guess = Date.UTC(Number(dm[1]), Number(dm[2]) - 1, Number(dm[3]), Number(tm[1]), Number(tm[2]));
  const first = offsetMinutes(guess, timeZone);
  let result = guess - first * 60_000;
  const second = offsetMinutes(result, timeZone);
  if (second !== first) result = guess - second * 60_000;
  return new Date(result);
}

/** The date and time inputs' values for an instant in the zone. */
export function toZonedInputs(instant: Date, timeZone: string): { date: string; time: string } {
  const p = zonedParts(instant, timeZone);
  return { date: `${p.year}-${pad(p.month)}-${pad(p.day)}`, time: `${pad(p.hour)}:${pad(p.minute)}` };
}
