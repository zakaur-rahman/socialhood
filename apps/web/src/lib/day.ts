/**
 * A calendar day as the forms keep it: "YYYY-MM-DD", with no time zone. The date pickers read and
 * write these strings, so what a form submits is what the native date input gave (the zone is
 * applied later by lib/tz, as before). Dates here are local-midnight `Date`s only to hand to the
 * calendar, which draws days, not instants.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** The day as a local-midnight Date, or undefined when it isn't a real "YYYY-MM-DD". */
export function parseDay(value: string | null | undefined): Date | undefined {
  const match = value ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(value) : null;
  if (!match) return undefined;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : undefined;
}

/** A calendar cell's Date as "YYYY-MM-DD". */
export function formatDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${String(date.getFullYear()).padStart(4, "0")}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** "Mon 28 Sep 2026" for the picker's button. */
export function dayLabel(value: string): string | null {
  const date = parseDay(value);
  return date ? `${WEEKDAYS[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}` : null;
}
