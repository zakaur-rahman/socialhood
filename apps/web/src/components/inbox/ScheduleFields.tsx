"use client";

import { Label } from "@/components/ui/label";
import { formatDayTime, toZonedInputs, zonedToDate } from "@/lib/tz";

/** F-10: the earliest time a message can be scheduled, and the margin before the window closes. */
export const MIN_LEAD_MS = 2 * 60_000;
export const WINDOW_MARGIN_MS = 5 * 60_000;

export type ScheduleValue = { date: string; time: string };

export type ScheduleLimits = { min: Date; max: Date | null };

export function scheduleLimits(now: Date, windowClosesAt: string | null | undefined): ScheduleLimits {
  const min = new Date(now.getTime() + MIN_LEAD_MS);
  const max = windowClosesAt ? new Date(new Date(windowClosesAt).getTime() - WINDOW_MARGIN_MS) : null;
  return { min, max };
}

/** The instant chosen, or the reason it can't be used. */
export function checkSchedule(
  value: ScheduleValue,
  timeZone: string,
  limits: ScheduleLimits,
  now: Date,
): { at: Date } | { error: string } {
  const at = zonedToDate(value.date, value.time, timeZone);
  if (!at) return { error: "Pick a date and time." };
  if (at < limits.min) return { error: "Pick a time at least 2 minutes from now." };
  if (limits.max && at > limits.max) {
    return { error: `Pick a time before ${formatDayTime(limits.max, timeZone, now)}, when the reply window closes.` };
  }
  return { at };
}

export function defaultSchedule(now: Date, timeZone: string, limits: ScheduleLimits): ScheduleValue {
  // An hour from now, rounded up to 5 minutes, but inside the window.
  let target = new Date(Math.ceil((now.getTime() + 60 * 60_000) / (5 * 60_000)) * 5 * 60_000);
  if (limits.max && target > limits.max) target = limits.max;
  if (target < limits.min) target = limits.min;
  return toZonedInputs(target, timeZone);
}

/** Date and time inputs in the workspace timezone (F-10), with the zone named. */
export function ScheduleFields({
  idPrefix,
  value,
  onChange,
  timeZone,
  limits,
  error,
}: {
  idPrefix: string;
  value: ScheduleValue;
  onChange: (value: ScheduleValue) => void;
  timeZone: string;
  limits: ScheduleLimits;
  error?: string | null;
}) {
  const minDay = toZonedInputs(limits.min, timeZone).date;
  const maxDay = limits.max ? toZonedInputs(limits.max, timeZone).date : undefined;
  const inputClass =
    "w-full rounded-lg border border-line bg-field px-3 py-2 text-sm outline-none focus:bg-raised aria-invalid:border-danger";
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label htmlFor={`${idPrefix}-date`} className="text-xs text-fg-secondary">
            Date
          </Label>
          <input
            id={`${idPrefix}-date`}
            type="date"
            value={value.date}
            min={minDay}
            max={maxDay}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange({ ...value, date: event.target.value })}
            className={inputClass}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${idPrefix}-time`} className="text-xs text-fg-secondary">
            Time
          </Label>
          <input
            id={`${idPrefix}-time`}
            type="time"
            value={value.time}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange({ ...value, time: event.target.value })}
            className={inputClass}
          />
        </div>
      </div>
      <p className="text-xs text-fg-secondary">Times are in {timeZone.replace(/_/g, " ")}.</p>
      {error ? (
        <p role="alert" className="text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
    </div>
  );
}
