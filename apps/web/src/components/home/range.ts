/**
 * Home's period (C-065): the last 7 or 30 days, or custom local days `from`..`to` in the
 * workspace's time zone, both included, at most 90 days, `to` no later than today. The API
 * checks the same rules (422); these keep the picker from sending a range it would refuse.
 * Remembered on this device as "7d", "30d" or "custom:{from}:{to}". Pure, tested directly.
 */
import type { OverviewQuery } from "@/lib/api/queries";

export type RangeChoice = "7d" | "30d" | "custom";

export const MAX_CUSTOM_DAYS = 90;

const DAY_MS = 86_400_000;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function dayNumber(day: string): number {
  const [y, m, d] = day.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

function isDay(value: string): boolean {
  if (!ISO_DAY.test(value)) return false;
  const n = dayNumber(value);
  return Number.isFinite(n) && new Date(n * DAY_MS).toISOString().slice(0, 10) === value;
}

/** "2026-09-30" plus `n` days (negative for before). */
export function addDays(day: string, n: number): string {
  return new Date((dayNumber(day) + n) * DAY_MS).toISOString().slice(0, 10);
}

/** Local days from `from` to `to`, both included. */
export function daysBetween(from: string, to: string): number {
  return dayNumber(to) - dayNumber(from) + 1;
}

export type CustomErrors = { from?: string; to?: string };

/** What is wrong with a custom range, per field, or null when the API will take it. */
export function checkCustom(from: string, to: string, today: string): CustomErrors | null {
  const errors: CustomErrors = {};
  if (!isDay(from)) errors.from = "Pick a start date.";
  if (!isDay(to)) errors.to = "Pick an end date.";
  else if (to > today) errors.to = "Pick a date up to today.";
  if (!errors.from && !errors.to) {
    if (from > to) errors.from = "Pick a start date on or before the end date.";
    else if (daysBetween(from, to) > MAX_CUSTOM_DAYS) errors.from = `Pick at most ${MAX_CUSTOM_DAYS} days.`;
  }
  return errors.from || errors.to ? errors : null;
}

export function choiceOf(query: OverviewQuery): RangeChoice {
  return "range" in query ? query.range : "custom";
}

export function storedRange(query: OverviewQuery): string {
  return "range" in query ? query.range : `custom:${query.from}:${query.to}`;
}

/** The remembered period, or the last 7 days when it is missing or no longer valid. */
export function parseStoredRange(value: string, today: string): OverviewQuery {
  if (value === "7d" || value === "30d") return { range: value };
  const [kind, from, to] = value.split(":");
  if (kind === "custom" && from && to && checkCustom(from, to, today) === null) return { from, to };
  return { range: "7d" };
}
