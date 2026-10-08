"use client";

import { useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import type { KnowledgeGap } from "@/lib/api/types";
import { emptyStates } from "@/lib/copy";
import { relativeTime } from "@/lib/time";

/** At most five rows before "Show all" (UX-SCR-06). */
export const GAPS_SHOWN = 5;

/** "Asked 14 times · last 2h ago". */
export function askedLine(gap: KnowledgeGap, now: Date): string {
  const when = relativeTime(gap.last_seen_at, now);
  const last = when === "now" ? "just now" : /^\d+[mhd]$/.test(when) ? `${when} ago` : when;
  return `Asked ${gap.occurrences} ${gap.occurrences === 1 ? "time" : "times"} · last ${last}`;
}

/**
 * FR-KB-06 / F-17: questions the AI couldn't answer, most asked first. Add answer opens the FAQ
 * form with a customer's question; Dismiss hides the topic until it is asked again.
 */
export function KnowledgeGapsCard({
  gaps,
  now,
  onAddAnswer,
  onDismiss,
  busyId,
}: {
  gaps: KnowledgeGap[];
  now: Date;
  onAddAnswer: (gap: KnowledgeGap) => void;
  onDismiss: (gap: KnowledgeGap) => void;
  /** The gap whose answer is being added or which is being dismissed. */
  busyId?: string | null;
}) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? gaps : gaps.slice(0, GAPS_SHOWN);

  return (
    <section aria-labelledby="gaps-title" className="rounded-xl border border-line bg-panel">
      <div className="border-b border-line p-5">
        <h2 id="gaps-title" className="text-base font-semibold">
          Questions the AI couldn&apos;t answer
        </h2>
        <p className="text-xs text-fg-secondary">From the last 30 days. Answer one and the AI can use it next time.</p>
      </div>
      {gaps.length === 0 ? (
        <EmptyState title={emptyStates.knowledgeGaps.title} body={emptyStates.knowledgeGaps.body} />
      ) : (
        <>
          <ul className="divide-y divide-line-subtle">
            {shown.map((gap) => {
              const example = gap.examples[0]?.text;
              return (
                <li key={gap.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center" data-gap={gap.id}>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{gap.topic}</p>
                    <p className="text-xs text-fg-secondary tabular-nums">{askedLine(gap, now)}</p>
                    {example ? <p className="mt-1 line-clamp-2 text-sm text-fg-secondary">“{example}”</p> : null}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      size="sm"
                      aria-label={`Add answer: ${gap.topic}`}
                      disabled={busyId === gap.id}
                      onClick={() => onAddAnswer(gap)}
                    >
                      Add answer
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Dismiss: ${gap.topic}`}
                      disabled={busyId === gap.id}
                      onClick={() => onDismiss(gap)}
                    >
                      Dismiss
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
          {gaps.length > GAPS_SHOWN ? (
            <div className="border-t border-line px-5 py-3">
              <Button variant="ghost" size="sm" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
                {showAll ? "Show fewer" : `Show all ${gaps.length}`}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
