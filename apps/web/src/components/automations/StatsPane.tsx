"use client";

import { useState } from "react";

import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useAutomationStats } from "@/lib/api/queries";
import type { AutomationStats } from "@/lib/api/types";
import { formatCount, repliedShare } from "@/lib/automations/format";
import { cn } from "@/lib/utils";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const CHART_HEIGHT = 80;

/** "Mon 28 Sep" for a calendar date ("2026-09-28"), which carries no timezone. */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${weekday} ${d} ${MONTHS[m - 1]}`;
}

/** UX-SCR-12 stats: four figures for 7 or 30 days, daily runs with failures stacked, skipped by reason. */
export function StatsPane({ wid, automationId }: { wid: string; automationId: string }) {
  const [days, setDays] = useState<7 | 30>(7);
  const stats = useAutomationStats(wid, automationId, days);

  return (
    <div className="space-y-4">
      <ToggleGroup aria-label="Period" value={String(days)} onValueChange={(value) => setDays(value === "30" ? 30 : 7)}>
        <ToggleGroupItem value="7">7 days</ToggleGroupItem>
        <ToggleGroupItem value="30">30 days</ToggleGroupItem>
      </ToggleGroup>
      {stats.isPending ? (
        <div aria-busy="true" aria-label="Loading results" className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-16 rounded-lg bg-raised" />
            ))}
          </div>
          <Skeleton className="h-20 rounded-lg bg-raised" />
        </div>
      ) : stats.isError ? (
        <ErrorState error={stats.error} onRetry={() => void stats.refetch()} />
      ) : (
        <StatsView stats={stats.data} />
      )}
    </div>
  );
}

export function StatsView({ stats }: { stats: AutomationStats }) {
  const figures = [
    { label: "Runs", value: formatCount(stats.runs) },
    { label: "DMs sent", value: formatCount(stats.dms_sent) },
    { label: "Replied within 24 h", value: repliedShare(stats.replied_24h, stats.dms_sent) },
    { label: "Failures", value: formatCount(stats.failures) },
  ];
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2">
        {figures.map((figure) => (
          <div key={figure.label} className="rounded-lg bg-field p-3">
            <dt className="text-xs text-fg-secondary">{figure.label}</dt>
            <dd className="mt-0.5 text-xl font-semibold tabular-nums">{figure.value}</dd>
          </div>
        ))}
      </dl>
      <DailyChart daily={stats.daily} />
      <p className="text-xs text-fg-secondary">
        {formatCount(stats.public_replies)} public {stats.public_replies === 1 ? "reply" : "replies"} ·{" "}
        {formatCount(stats.queued_now)} queued now
      </p>
      <div className="space-y-1">
        <p className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Skipped</p>
        <ul className="space-y-0.5 text-sm">
          <li className="flex justify-between gap-2">
            <span className="text-fg-secondary">Cooldown</span>
            <span className="tabular-nums">{formatCount(stats.skipped.cooldown)}</span>
          </li>
          <li className="flex justify-between gap-2">
            <span className="text-fg-secondary">Instagram&apos;s 7-day limit passed</span>
            <span className="tabular-nums">{formatCount(stats.skipped.expired)}</span>
          </li>
          <li className="flex justify-between gap-2">
            <span className="text-fg-secondary">Outside the run window</span>
            <span className="tabular-nums">{formatCount(stats.skipped.outside_window)}</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

/** Runs per day in brand with failures stacked on top in danger; hover or focus a day for its numbers. */
function DailyChart({ daily }: { daily: AutomationStats["daily"] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...daily.map((day) => day.runs));
  const total = daily.reduce((sum, day) => sum + day.runs, 0);
  const current = active !== null ? daily[active] : null;

  return (
    <figure className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-xs">
        <figcaption className="text-fg-secondary">Runs per day</figcaption>
        <span className="flex items-center gap-3 text-fg-secondary">
          <span className="flex items-center gap-1">
            <span aria-hidden className="size-2 rounded-sm bg-brand" /> Runs
          </span>
          <span className="flex items-center gap-1">
            <span aria-hidden className="size-2 rounded-sm bg-danger" /> Failures
          </span>
        </span>
      </div>
      <p className="h-4 text-xs tabular-nums" aria-hidden>
        {current
          ? `${dayLabel(current.date)} · ${formatCount(current.runs)} ${current.runs === 1 ? "run" : "runs"} · ${formatCount(current.failures)} failed`
          : ""}
      </p>
      <div
        role="img"
        aria-label={`${formatCount(total)} runs over ${daily.length} days`}
        className="flex items-end gap-0.5 border-b border-line"
        style={{ height: CHART_HEIGHT }}
        onMouseLeave={() => setActive(null)}
      >
        {daily.map((day, index) => {
          const failures = Math.min(day.failures, day.runs);
          const ok = day.runs - failures;
          const okHeight = (ok / max) * CHART_HEIGHT;
          const failHeight = (failures / max) * CHART_HEIGHT;
          return (
            <div
              key={day.date}
              className={cn("flex h-full flex-1 flex-col-reverse gap-0.5", active === index && "opacity-80")}
              onMouseEnter={() => setActive(index)}
            >
              {ok > 0 ? (
                <span
                  className={cn("block w-full bg-brand", failures === 0 && "rounded-t-[4px]")}
                  style={{ height: Math.max(okHeight, 2) }}
                />
              ) : null}
              {failures > 0 ? (
                <span className="block w-full rounded-t-[4px] bg-danger" style={{ height: Math.max(failHeight, 2) }} />
              ) : null}
            </div>
          );
        })}
      </div>
      <table className="sr-only">
        <caption>Runs and failures per day</caption>
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">Runs</th>
            <th scope="col">Failures</th>
          </tr>
        </thead>
        <tbody>
          {daily.map((day) => (
            <tr key={day.date}>
              <th scope="row">{dayLabel(day.date)}</th>
              <td>{day.runs}</td>
              <td>{day.failures}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
