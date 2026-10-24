"use client";

import { Plus, X } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { TimeField } from "@/components/ui/date-picker";
import { Field, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutoModeName } from "@/lib/api/types";
import { DAY_NAMES, DEFAULT_RANGE, displayEnd, MAX_RANGES, parseEnd, type HoursForm } from "@/lib/hours/form";

/** Field errors from the API, by path ("days.2.ranges.0.end"), shown under the day they name. */
export type HoursErrors = Record<string, string>;

/**
 * GR-22: a weekly schedule, the away message and Auto mode's hours. A day with no ranges is
 * closed; a day can have several ranges (a lunch break is two). Times are on the 24-hour clock in
 * the workspace time zone, and a closing time of 00:00 means midnight at the end of the day. The
 * rows wrap on a phone: the day on its own line, then its ranges.
 */
export function HoursEditor({
  idPrefix,
  form,
  onChange,
  errors,
  disabled = false,
  timeZone,
}: {
  idPrefix: string;
  form: HoursForm;
  onChange: (next: HoursForm) => void;
  errors: HoursErrors;
  disabled?: boolean;
  timeZone: string;
}) {
  const hintId = useId();
  const setDay = (day: number, ranges: HoursForm["days"][number]["ranges"]) =>
    onChange({ ...form, days: form.days.map((d) => (d.day === day ? { ...d, ranges } : d)) });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <label htmlFor={`${idPrefix}-enabled`} className="text-sm font-medium">
            Use business hours
          </label>
          <p className="text-xs text-fg-secondary">
            Off means always open. Times are in {timeZone}.
          </p>
        </div>
        <Switch
          id={`${idPrefix}-enabled`}
          checked={form.enabled}
          disabled={disabled}
          onCheckedChange={(enabled) => onChange({ ...form, enabled })}
        />
      </div>
      {errors.days ? <p className="text-sm text-danger-fg">{errors.days}</p> : null}

      {form.enabled ? (
        <ul aria-label="Opening hours" className="divide-y divide-line-subtle rounded-lg border border-line">
          {form.days.map((day) => (
            <li key={day.day} className="flex flex-wrap items-start gap-x-4 gap-y-2 px-3 py-3">
              <p className="w-28 shrink-0 pt-2 text-sm font-medium">{DAY_NAMES[day.day]}</p>
              <div className="min-w-0 flex-1 space-y-2">
                {day.ranges.length === 0 ? (
                  <p className="pt-2 text-sm text-fg-secondary">Closed</p>
                ) : (
                  day.ranges.map((range, index) => {
                    const startError = errors[`days.${day.day}.ranges.${index}.start`];
                    const endError = errors[`days.${day.day}.ranges.${index}.end`];
                    return (
                      <div key={index} className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="w-36">
                            <TimeField
                              size="lg"
                              aria-label={`${DAY_NAMES[day.day]} opens at`}
                              aria-invalid={startError ? true : undefined}
                              value={range.start}
                              disabled={disabled}
                              onChange={(time) =>
                                setDay(
                                  day.day,
                                  day.ranges.map((r, i) => (i === index ? { ...r, start: time } : r)),
                                )
                              }
                            />
                          </div>
                          <span aria-hidden className="text-fg-secondary">
                            to
                          </span>
                          <div className="w-36">
                            <TimeField
                              size="lg"
                              aria-label={`${DAY_NAMES[day.day]} closes at`}
                              aria-invalid={endError ? true : undefined}
                              value={displayEnd(range.end)}
                              disabled={disabled}
                              onChange={(time) =>
                                setDay(
                                  day.day,
                                  day.ranges.map((r, i) => (i === index ? { ...r, end: parseEnd(time) } : r)),
                                )
                              }
                            />
                          </div>
                          <Button
                            variant="ghost"
                            size="icon-lg"
                            aria-label={`Remove ${DAY_NAMES[day.day]} hours ${index + 1}`}
                            disabled={disabled}
                            onClick={() => setDay(day.day, day.ranges.filter((_, i) => i !== index))}
                          >
                            <X aria-hidden />
                          </Button>
                        </div>
                        {startError || endError ? (
                          <p className="text-xs text-danger-fg">{startError ?? endError}</p>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled || day.ranges.length >= MAX_RANGES}
                onClick={() => {
                  // A second range starts where the last one ended (evening hours); the first is 09:00 to 17:00.
                  const last = day.ranges[day.ranges.length - 1];
                  setDay(day.day, [...day.ranges, last && last.end < "23:00" ? { start: last.end, end: "24:00" } : { ...DEFAULT_RANGE }]);
                }}
                aria-label={`Add ${DAY_NAMES[day.day]} hours`}
              >
                <Plus aria-hidden /> Add hours
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="space-y-3 border-t border-line pt-5">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <label htmlFor={`${idPrefix}-away`} className="text-sm font-medium">
              Away message
            </label>
            <p className="text-xs text-fg-secondary">
              Sent once when someone writes while you are closed, if no automation answered them.
            </p>
          </div>
          <Switch
            id={`${idPrefix}-away`}
            checked={form.away_enabled}
            disabled={disabled || !form.enabled}
            onCheckedChange={(away_enabled) => onChange({ ...form, away_enabled })}
          />
        </div>
        {form.away_enabled && form.enabled ? (
          <Field invalid={Boolean(errors.away_message)}>
            <FieldLabel htmlFor={`${idPrefix}-away-text`}>Message</FieldLabel>
            <Textarea
              id={`${idPrefix}-away-text`}
              maxLength={1000}
              value={form.away_message}
              disabled={disabled}
              placeholder="Thanks for writing, {first_name}. We're closed right now and will reply from 9 am."
              onChange={(event) => onChange({ ...form, away_message: event.target.value })}
            />
            {errors.away_message ? <p className="text-sm text-danger-fg">{errors.away_message}</p> : null}
          </Field>
        ) : null}
      </div>

      <div className="space-y-2 border-t border-line pt-5">
        <p id={`${idPrefix}-auto-label`} className="text-sm font-medium">
          Auto mode
        </p>
        <ToggleGroup
          aria-labelledby={`${idPrefix}-auto-label`}
          aria-describedby={hintId}
          value={form.enabled ? form.auto_mode : "always"}
          onValueChange={(value) => value && onChange({ ...form, auto_mode: value as AutoModeName })}
          className="flex-col sm:flex-row"
          disabled={disabled || !form.enabled}
        >
          <ToggleGroupItem value="always">Works at any hour</ToggleGroupItem>
          <ToggleGroupItem value="out_of_hours">Only when closed</ToggleGroupItem>
        </ToggleGroup>
        <p id={hintId} className="text-xs text-fg-secondary">
          Applies to accounts and chats set to Auto. While you are open, the AI leaves its suggestion for a person to
          send. Your away message is not sent to a chat that Auto answers.
        </p>
      </div>
    </div>
  );
}
