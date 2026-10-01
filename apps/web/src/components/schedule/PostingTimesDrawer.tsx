"use client";

import { Copy, Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/errors";
import { usePostingSlots, useReplacePostingSlots } from "@/lib/api/queries/calendar";
import type { PostingSlot, SocialAccount } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { errorMessage } from "@/lib/copy";
import { WEEKDAYS_LONG, WEEKDAYS_SHORT, zoneLabel } from "@/lib/schedule/dates";
import { formatDayTime } from "@/lib/tz";

import { useSchedule } from "./schedule-context";

/** Times per weekday, "HH:MM", sorted: 0 = Monday … 6 = Sunday. */
export type WeekTimes = string[][];

export function fromSlots(slots: PostingSlot[]): WeekTimes {
  const week: WeekTimes = Array.from({ length: 7 }, () => []);
  for (const slot of slots) {
    const time = slot.local_time.slice(0, 5);
    if (slot.weekday >= 0 && slot.weekday < 7 && !week[slot.weekday].includes(time)) week[slot.weekday].push(time);
  }
  return week.map((times) => times.sort());
}

export function toSlots(week: WeekTimes): PostingSlot[] {
  return week.flatMap((times, weekday) => times.map((time) => ({ weekday, local_time: time })));
}

function same(a: WeekTimes, b: WeekTimes): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * UX-SCR-14 posting times: a drawer with a tab per account and a 7-day grid (add times per day,
 * copy a day to other days), and a line listing the next 5 free times (FR-PUB-09). Unsaved
 * changes stay while switching tabs.
 */
export function PostingTimesDrawer({
  open,
  onOpenChange,
  accounts,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: SocialAccount[];
}) {
  const [accountId, setAccountId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, WeekTimes>>({});
  const current = accounts.find((a) => a.id === accountId) ?? accounts[0];
  const times = (account: SocialAccount) => (
    <AccountTimes
      key={account.id}
      account={account}
      draft={drafts[account.id]}
      onDraftChange={(week) => setDrafts((all) => ({ ...all, [account.id]: week }))}
      onSaved={() =>
        setDrafts((all) => {
          const next = { ...all };
          delete next[account.id];
          return next;
        })
      }
    />
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 border-line bg-panel sm:max-w-md">
        <SheetHeader className="border-b border-line">
          <SheetTitle className="text-base font-semibold">Posting times</SheetTitle>
          <SheetDescription className="text-fg-secondary">
            Add to queue takes the next free time. Changing these doesn&apos;t move posts already scheduled.
          </SheetDescription>
        </SheetHeader>
        {current && accounts.length > 1 ? (
          <Tabs value={current.id} onValueChange={setAccountId} className="min-h-0 flex-1 gap-0">
            <TabsList className="mx-4 mt-3">
              {accounts.map((account) => (
                <TabsTrigger key={account.id} value={account.id} className="min-h-10 truncate md:min-h-8">
                  {accountLabel(account)}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value={current.id} className="flex min-h-0 flex-1 flex-col">
              {times(current)}
            </TabsContent>
          </Tabs>
        ) : current ? (
          <div className="flex min-h-0 flex-1 flex-col">{times(current)}</div>
        ) : (
          <p className="p-4 text-sm text-fg-secondary">Connect an Instagram account to set posting times.</p>
        )}
      </SheetContent>
    </Sheet>
  );
}

function AccountTimes({
  account,
  draft,
  onDraftChange,
  onSaved,
}: {
  account: SocialAccount;
  draft?: WeekTimes;
  onDraftChange: (week: WeekTimes) => void;
  onSaved: () => void;
}) {
  const schedule = useSchedule();
  const slots = usePostingSlots(schedule.wid, account.id);
  const save = useReplacePostingSlots(schedule.wid);
  const [error, setError] = useState<string | null>(null);

  if (slots.isPending) {
    return (
      <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading posting times">
        {Array.from({ length: 7 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full bg-raised" />
        ))}
      </div>
    );
  }
  if (slots.isError) {
    return (
      <div className="space-y-2 p-4">
        <p className="text-sm text-fg-secondary">{errorMessage(slots.error)}</p>
        <Button variant="secondary" onClick={() => void slots.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  const saved = fromSlots(slots.data.slots);
  const week = draft ?? saved;
  const dirty = !same(week, saved);
  const zone = slots.data.timezone || schedule.timeZone;

  const update = (next: WeekTimes) => {
    setError(null);
    onDraftChange(next.map((times) => [...new Set(times)].sort()));
  };

  const submit = () =>
    save.mutate(
      { accountId: account.id, slots: toSlots(week) },
      {
        onSuccess: () => {
          onSaved();
          toast.success(`Posting times saved for ${accountLabel(account)}`);
        },
        onError: (e) => setError(e instanceof ApiError && e.errors[0] ? e.errors[0].message : errorMessage(e)),
      },
    );

  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <p className="mb-2 text-xs text-fg-secondary">Times in {zoneLabel(zone)}</p>
        <ul className="divide-y divide-line-subtle" aria-label={`Weekly posting times for ${accountLabel(account)}`}>
          {WEEKDAYS_LONG.map((name, weekday) => (
            <DayRow
              key={name}
              weekday={weekday}
              times={week[weekday]}
              onChange={(times) => update(week.map((t, i) => (i === weekday ? times : t)))}
              onCopy={(targets) => update(week.map((t, i) => (targets.includes(i) ? [...week[weekday]] : t)))}
            />
          ))}
        </ul>
        <div className="mt-4 rounded-lg border border-line bg-field p-3">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Next free times</p>
          <p className="mt-1 text-sm tabular-nums" data-testid="next-free-times">
            {slots.data.next_free_at.length > 0
              ? slots.data.next_free_at.map((at) => formatDayTime(at, zone, schedule.now)).join(" · ")
              : "No free times yet. Add a posting time."}
          </p>
          {dirty ? <p className="mt-1 text-xs text-fg-secondary">Save to see the times your changes give.</p> : null}
        </div>
      </div>
      <SheetFooter className="border-t border-line">
        {error ? (
          <p role="alert" className="text-xs text-danger-fg">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          {dirty ? (
            <Button variant="ghost" onClick={() => update(saved)} disabled={save.isPending}>
              Discard changes
            </Button>
          ) : null}
          <Button className="bg-brand-gradient text-white" onClick={submit} disabled={!dirty || save.isPending}>
            {save.isPending ? "Saving…" : "Save posting times"}
          </Button>
        </div>
      </SheetFooter>
    </>
  );
}

function DayRow({
  weekday,
  times,
  onChange,
  onCopy,
}: {
  weekday: number;
  times: string[];
  onChange: (times: string[]) => void;
  onCopy: (weekdays: number[]) => void;
}) {
  const name = WEEKDAYS_LONG[weekday];
  const [adding, setAdding] = useState("");
  const [copyOpen, setCopyOpen] = useState(false);
  const [copyTo, setCopyTo] = useState<number[]>([]);
  const inputId = `posting-time-${weekday}`;

  const add = () => {
    if (!/^\d{2}:\d{2}$/.test(adding)) return;
    onChange([...times, adding]);
    setAdding("");
  };

  return (
    <li className="py-2.5">
      <div className="flex items-start gap-2">
        <span className="w-10 shrink-0 pt-2 text-sm font-medium" aria-hidden>
          {WEEKDAYS_SHORT[weekday]}
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <ul className="flex flex-wrap gap-1.5" aria-label={`${name} times`}>
            {times.length === 0 ? <li className="pt-2 text-xs text-fg-secondary">No times</li> : null}
            {times.map((time) => (
              <li key={time} className="flex items-center gap-0.5 rounded-full bg-raised py-0.5 pr-0.5 pl-2.5 text-sm tabular-nums">
                {time}
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="size-8 rounded-full md:size-6"
                  aria-label={`Remove ${time} on ${name}`}
                  onClick={() => onChange(times.filter((t) => t !== time))}
                >
                  <X aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-1.5">
            <label htmlFor={inputId} className="sr-only">
              New time on {name}
            </label>
            <input
              id={inputId}
              type="time"
              step={60}
              value={adding}
              onChange={(event) => setAdding(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  add();
                }
              }}
              className="h-10 rounded-lg border border-line bg-field px-2 text-sm tabular-nums focus:bg-raised md:h-8"
            />
            <Button variant="secondary" size="sm" className="min-h-10 md:min-h-8" onClick={add} disabled={!adding} aria-label={`Add time on ${name}`}>
              <Plus aria-hidden /> Add
            </Button>
            <Popover
              open={copyOpen}
              onOpenChange={(value) => {
                setCopyOpen(value);
                if (value) setCopyTo([]);
              }}
            >
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto min-h-10 text-fg-secondary md:min-h-8"
                  disabled={times.length === 0}
                  aria-label={`Copy ${name} to other days`}
                >
                  <Copy aria-hidden /> Copy to…
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-56 border-line bg-panel shadow-xl">
                <p className="text-sm font-medium">Copy {name}&apos;s times to</p>
                <div className="grid gap-1">
                  {WEEKDAYS_LONG.map((other, index) =>
                    index === weekday ? null : (
                      <label key={other} className="flex min-h-9 items-center gap-2 text-sm">
                        <Checkbox
                          checked={copyTo.includes(index)}
                          onCheckedChange={(value) =>
                            setCopyTo((list) => (value === true ? [...list, index] : list.filter((d) => d !== index)))
                          }
                        />
                        {other}
                      </label>
                    ),
                  )}
                </div>
                <p className="text-xs text-fg-secondary">Their times are replaced.</p>
                <Button
                  size="sm"
                  className="bg-brand-gradient text-white"
                  disabled={copyTo.length === 0}
                  onClick={() => {
                    onCopy(copyTo);
                    setCopyOpen(false);
                  }}
                >
                  Copy
                </Button>
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>
    </li>
  );
}
