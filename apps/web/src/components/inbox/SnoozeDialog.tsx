"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { snoozeLimits, snoozePresets } from "@/lib/inbox/snooze";
import { formatDayTime, zonedToDate } from "@/lib/tz";

import { defaultSchedule, ScheduleFields, type ScheduleValue } from "./ScheduleFields";

/**
 * GR-45: snooze a conversation until a preset (later today, tomorrow 9:00, next Monday 9:00) or a
 * chosen time, at most 90 days ahead. It leaves the list and comes back unread at that time, or when
 * the customer writes again.
 */
export function SnoozeDialog({
  open,
  onOpenChange,
  now,
  timeZone,
  onSnooze,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  now: Date;
  timeZone: string;
  onSnooze: (until: Date) => void;
}) {
  const limits = snoozeLimits(now);
  const [custom, setCustom] = useState<ScheduleValue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const checked = custom ? check(custom) : null;

  function check(value: ScheduleValue): { at: Date } | { error: string } {
    const at = zonedToDate(value.date, value.time, timeZone);
    if (!at) return { error: "Pick a date and time." };
    if (at < limits.min) return { error: "Pick a time at least 1 minute from now." };
    if (at > limits.max) return { error: `Pick a time before ${formatDayTime(limits.max, timeZone, now)}.` };
    return { at };
  }

  function close(next: boolean) {
    if (!next) {
      setCustom(null);
      setError(null);
    }
    onOpenChange(next);
  }

  function choose(until: Date) {
    onSnooze(until);
    close(false);
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Snooze conversation</DialogTitle>
          <DialogDescription>
            It leaves your list and comes back unread at that time. A new message from the customer brings it back sooner.
          </DialogDescription>
        </DialogHeader>
        <ul aria-label="Snooze until" className="space-y-2">
          {snoozePresets(now, timeZone).map((preset) => (
            <li key={preset.key}>
              <Button variant="secondary" className="w-full justify-between" onClick={() => choose(preset.at)}>
                <span>{preset.label}</span>
                <span className="text-fg-secondary">{formatDayTime(preset.at, timeZone, now)}</span>
              </Button>
            </li>
          ))}
        </ul>
        {custom ? (
          <form
            aria-label="Snooze until a chosen time"
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (checked && "error" in checked) setError(checked.error);
              else if (checked) choose(checked.at);
            }}
          >
            <ScheduleFields
              idPrefix="snooze"
              value={custom}
              onChange={(value) => {
                setCustom(value);
                setError(null);
              }}
              timeZone={timeZone}
              limits={limits}
              error={error}
            />
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => close(false)}>
                Cancel
              </Button>
              <Button type="submit">Snooze</Button>
            </DialogFooter>
          </form>
        ) : (
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="button" variant="secondary" onClick={() => setCustom(defaultSchedule(now, timeZone, limits))}>
              Pick a date and time
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
