"use client";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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

/**
 * A time prepared elsewhere (Ask Social Hood's schedule card, FR-AGT-03) as the inputs' values,
 * or null when it is missing or no longer inside the limits.
 */
export function preparedSchedule(
  at: string | null | undefined,
  timeZone: string,
  limits: ScheduleLimits,
): ScheduleValue | null {
  if (!at) return null;
  const instant = new Date(at);
  if (Number.isNaN(instant.getTime()) || instant < limits.min) return null;
  if (limits.max && instant > limits.max) return null;
  return toZonedInputs(instant, timeZone);
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
  // Native date and time pickers through Input (D-04): its edge, focus, 16 px text on phones and
  // 40 px on coarse pointers; `lg` (36 px) is the closest to the old 38 px fields.
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <Field id={`${idPrefix}-date`} density="compact">
          <FieldLabel>Date</FieldLabel>
          <Input
            type="date"
            size="lg"
            value={value.date}
            min={minDay}
            max={maxDay}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange({ ...value, date: event.target.value })}
          />
        </Field>
        <Field id={`${idPrefix}-time`} density="compact">
          <FieldLabel>Time</FieldLabel>
          <Input
            type="time"
            size="lg"
            value={value.time}
            aria-invalid={Boolean(error)}
            onChange={(event) => onChange({ ...value, time: event.target.value })}
          />
        </Field>
      </div>
      <FieldDescription>Times are in {timeZone.replace(/_/g, " ")}.</FieldDescription>
      <FieldError>{error}</FieldError>
    </div>
  );
}
