"use client";

import { useState, type FormEvent } from "react";

import { ScheduleFields, type ScheduleValue } from "@/components/inbox/ScheduleFields";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { ScheduledPostSummary } from "@/lib/api/types";
import { MIN_LEAD_MS, TOO_SOON_MESSAGE, tooSoon } from "@/lib/schedule/dates";
import { captionLine } from "@/lib/schedule/format";
import { formatTime, toZonedInputs, zonedToDate } from "@/lib/tz";

export type MoveRequest = {
  post: ScheduledPostSummary;
  /** A day chosen already (a timeless draft dropped on the Month grid). */
  day?: string;
  /** Where focus goes back when the dialog closes (UX-A11Y-02). */
  returnFocus?: HTMLElement | null;
};

const STEP_MS = 15 * 60_000;

function initialValue(request: MoveRequest, timeZone: string, now: Date): ScheduleValue {
  const current = request.post.publish_at ? new Date(request.post.publish_at) : null;
  if (request.day) return { date: request.day, time: current ? formatTime(current, timeZone) : "09:00" };
  if (current && !tooSoon(current, now)) return toZonedInputs(current, timeZone);
  // An hour from now, on the quarter hour.
  return toZonedInputs(new Date(Math.ceil((now.getTime() + 60 * 60_000) / STEP_MS) * STEP_MS), timeZone);
}

/**
 * "Move to…" (FR-PUB-08): the keyboard and phone alternative to dragging. For a scheduled post it
 * reschedules; for a draft it schedules ("Schedule for…"), with the same checks as Schedule.
 * `onMove` answers an error to show, or null when done. It stays mounted and keeps the last request
 * while it closes, so its exit plays.
 */
export function MoveToDialog({
  open,
  request,
  timeZone,
  now,
  onMove,
  onClose,
}: {
  open: boolean;
  request: MoveRequest | null;
  timeZone: string;
  now: Date;
  onMove: (at: Date) => Promise<string | null>;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent
        className="border-line bg-panel sm:max-w-md"
        onCloseAutoFocus={(event) => {
          if (request?.returnFocus?.isConnected) {
            event.preventDefault();
            request.returnFocus.focus();
          }
        }}
      >
        {request ? (
          <MoveToForm key={request.post.id} request={request} timeZone={timeZone} now={now} onMove={onMove} onClose={onClose} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/** Inside the dialog's content, so each opening starts from the post's own time. */
function MoveToForm({
  request,
  timeZone,
  now,
  onMove,
  onClose,
}: {
  request: MoveRequest;
  timeZone: string;
  now: Date;
  onMove: (at: Date) => Promise<string | null>;
  onClose: () => void;
}) {
  const draft = request.post.status === "draft";
  const [value, setValue] = useState<ScheduleValue>(() => initialValue(request, timeZone, now));
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const at = zonedToDate(value.date, value.time, timeZone);
    if (!at) return setError("Pick a date and time.");
    if (tooSoon(at, now)) return setError(TOO_SOON_MESSAGE);
    setError(null);
    setPending(true);
    const problem = await onMove(at);
    setPending(false);
    if (problem) setError(problem);
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{draft ? "Schedule for…" : "Move to…"}</DialogTitle>
        <DialogDescription className="truncate text-fg-secondary">{captionLine(request.post.caption)}</DialogDescription>
      </DialogHeader>
      <ScheduleFields
        idPrefix="move-to"
        value={value}
        onChange={setValue}
        timeZone={timeZone}
        limits={{ min: new Date(now.getTime() + MIN_LEAD_MS), max: null }}
        error={error}
      />
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" className="bg-brand-gradient text-white" disabled={pending}>
          {draft ? "Schedule" : "Move"}
        </Button>
      </DialogFooter>
    </form>
  );
}
