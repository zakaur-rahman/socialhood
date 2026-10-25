"use client";

import type { Route } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useContactSequences } from "@/lib/api/queries";
import { ENROLMENT_STATUS } from "@/lib/sequences/format";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";
import { META } from "@/styles/tokens";

/**
 * GR-24: the sequences a contact is in or has been in. For each one: its status, the step they are
 * on and when it is due, what happened at each step (sent, or skipped and why), and why a stopped
 * one stopped. The link opens the sequence for owners and admins; the section is for every member.
 */
export function ContactSequences({ contactId }: { contactId: string }) {
  const { id: wid, slug, timezone, role } = useCurrentWorkspace();
  const list = useContactSequences(wid, contactId);

  if (list.isPending) return <Skeleton className="h-10 w-full" aria-label="Loading sequences" />;
  if (list.isError) return <p className="text-sm text-fg-secondary">The sequences did not load.</p>;
  if (list.data.items.length === 0) {
    return <p className="text-sm text-fg-secondary">Not in any sequence.</p>;
  }
  return (
    <ul aria-label="Sequences" className="space-y-3">
      {list.data.items.map(({ enrolment, runs }) => {
        const badge = ENROLMENT_STATUS[enrolment.status];
        const name = enrolment.sequence_name ?? "A sequence";
        return (
          <li key={enrolment.id} className="space-y-1" data-testid="contact-sequence">
            <div className="flex flex-wrap items-center justify-between gap-2">
              {role === "agent" ? (
                <p className="text-sm font-semibold">{name}</p>
              ) : (
                <Link
                  href={`/w/${slug}/sequences/${enrolment.sequence_id}` as Route}
                  className="text-sm font-semibold underline-offset-4 hover:underline"
                >
                  {name}
                </Link>
              )}
              <Badge tone={badge.tone}>{badge.label}</Badge>
            </div>
            <p className={META}>
              {enrolment.entry_event} · joined {formatDayTime(enrolment.enrolled_at, timezone)}
            </p>
            {enrolment.status === "active" && enrolment.next_step ? (
              <p className="text-sm">
                On step {enrolment.next_step} of {enrolment.step_count}
                {enrolment.next_due_at ? `, due ${formatDayTime(enrolment.next_due_at, timezone)}` : ""}
              </p>
            ) : null}
            {enrolment.stop_text ? <p className="text-sm text-warning">{enrolment.stop_text}</p> : null}
            {runs.length > 0 ? (
              <ul className="space-y-0.5 text-sm text-fg-secondary">
                {runs.map((run) => (
                  <li key={run.position}>
                    Step {run.position}: {run.status}
                    {run.reason ? `. ${run.reason}` : ""} ({formatDayTime(run.at, timezone)})
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
