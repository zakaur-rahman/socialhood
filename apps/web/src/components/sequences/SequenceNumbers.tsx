"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { useSequenceAnalytics } from "@/lib/api/queries";
import type { SequenceAnalytics } from "@/lib/api/types";
import { useCurrentWorkspace } from "@/lib/workspace";
import { CARD_TITLE, ITEM_TITLE, META } from "@/styles/tokens";

/** 0.4 -> "40%"; null (nothing to divide by) -> "none yet". */
export function percent(rate: number | null | undefined): string {
  return rate === null || rate === undefined ? "none yet" : `${Math.round(rate * 100)}%`;
}

function Figure({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="space-y-0.5">
      <dt className={META}>{label}</dt>
      <dd className="text-xl font-semibold tabular-nums">{value}</dd>
      {note ? <p className={META}>{note}</p> : null}
    </div>
  );
}

function Reasons({ title, items }: { title: string; items: SequenceAnalytics["skipped_by"] }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <h3 className={ITEM_TITLE}>{title}</h3>
      <ul className="space-y-1 text-sm">
        {items.map((reason) => (
          <li key={reason.code} className="flex items-baseline justify-between gap-3">
            <span>{reason.text}</span>
            <span className="tabular-nums text-fg-secondary">{reason.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * GR-24: how a sequence is doing. Every number comes from the server (cached there for a few
 * minutes): who entered, what happened to each step, why steps were skipped and people stopped,
 * and a funnel of how many got to each step.
 */
export function SequenceNumbers({ sequenceId }: { sequenceId: string }) {
  const { id: wid } = useCurrentWorkspace();
  const numbers = useSequenceAnalytics(wid, sequenceId);

  if (numbers.isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (numbers.isError) return null; // the numbers are extra; the page works without them
  const stats = numbers.data;
  if (stats.enrolled === 0) {
    return (
      <section aria-labelledby="sequence-numbers" className="mt-8 space-y-3">
        <h2 id="sequence-numbers" className={CARD_TITLE}>
          Numbers
        </h2>
        <Card>
          <p className={META}>Nobody has entered this sequence yet. The numbers appear once someone does.</p>
        </Card>
      </section>
    );
  }
  return (
    <section aria-labelledby="sequence-numbers" className="mt-8 space-y-3">
      <h2 id="sequence-numbers" className={CARD_TITLE}>
        Numbers
      </h2>
      <Card className="space-y-5">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Figure label="Entered" value={stats.enrolled} note={`${stats.active} in it now`} />
          <Figure label="Finished" value={stats.completed} />
          <Figure label="Stopped" value={stats.stopped} />
          <Figure
            label="Replied"
            value={percent(stats.reply_rate)}
            note={`${stats.replied} of ${stats.sent} messages, within ${stats.window_hours} hours`}
          />
        </dl>
        <dl className="grid grid-cols-3 gap-4">
          <Figure label="Sent" value={stats.sent} />
          <Figure label="Skipped" value={stats.skipped} />
          <Figure label="Failed" value={stats.failed} />
        </dl>
        <div className="grid gap-5 sm:grid-cols-2">
          <Reasons title="Why steps were skipped" items={stats.skipped_by} />
          <Reasons title="Why people stopped" items={stats.stopped_by} />
        </div>
        <div className="space-y-3">
          <h3 className={ITEM_TITLE}>Who gets to each step</h3>
          <ol className="space-y-3">
            {stats.steps.map((step) => (
              <li key={step.position} className="space-y-1">
                <Meter
                  label={`Step ${step.position}`}
                  kind="slot"
                  value={step.reached}
                  max={stats.enrolled}
                  valueText={`${step.reached} of ${stats.enrolled} reached it`}
                />
                <p className={META}>
                  {step.sent} sent, {step.skipped} skipped, {step.failed} failed
                  {step.waiting > 0 ? `, ${step.waiting} waiting` : ""}. Replies: {percent(step.reply_rate)}.
                </p>
              </li>
            ))}
          </ol>
        </div>
      </Card>
    </section>
  );
}
