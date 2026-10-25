"use client";

import { Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PEOPLE_PAGE, useSequencePeople, useStopEnrolment } from "@/lib/api/queries";
import type { EnrolmentStatus, SequenceEnrolment } from "@/lib/api/types";
import { ENROLMENT_STATUS } from "@/lib/sequences/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";
import { CARD_TITLE, ITEM_TITLE, META } from "@/styles/tokens";

const FILTERS: { value: EnrolmentStatus | "all"; label: string }[] = [
  { value: "all", label: "Everyone" },
  { value: "active", label: "In it" },
  { value: "completed", label: "Finished" },
  { value: "stopped", label: "Stopped" },
];

function who(person: SequenceEnrolment): string {
  return person.contact.display_name ?? (person.contact.username ? `@${person.contact.username}` : "Customer");
}

/**
 * GR-24: the people in a sequence. Each one's status, the step they are on and when it is due, what
 * happened at the last step (sent, or skipped and why), and, for a stopped one, why it stopped.
 * Someone still in it can be taken out.
 */
export function SequencePeople({ sequenceId }: { sequenceId: string }) {
  const { id: wid, timezone } = useCurrentWorkspace();
  const [status, setStatus] = useState<EnrolmentStatus | null>(null);
  const [page, setPage] = useState(0);
  const people = useSequencePeople(wid, sequenceId, status, page);
  const stop = useStopEnrolment(wid);

  return (
    <section aria-labelledby="sequence-people" className="mt-8 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="sequence-people" className={CARD_TITLE}>
          People
        </h2>
        <ToggleGroup
          aria-label="Show"
          value={status ?? "all"}
          onValueChange={(value) => {
            if (!value) return;
            setStatus(value === "all" ? null : (value as EnrolmentStatus));
            setPage(0);
          }}
        >
          {FILTERS.map((filter) => (
            <ToggleGroupItem key={filter.value} value={filter.value}>
              {filter.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      {people.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : people.isError ? (
        <ErrorState error={people.error} onRetry={() => void people.refetch()} />
      ) : people.data.items.length === 0 ? (
        <Card>
          <EmptyState
            size="compact"
            icon={<Users />}
            title={status ? "Nobody like that" : "Nobody has joined yet"}
            body={status ? "Try another filter." : "People appear here as they enter the sequence."}
          />
        </Card>
      ) : (
        <>
          <ul aria-label="People in this sequence" className="space-y-2">
            {people.data.items.map((person) => {
              const badge = ENROLMENT_STATUS[person.status];
              return (
                <li key={person.id}>
                  <Card className="space-y-1.5" data-testid="person-row">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={ITEM_TITLE}>{who(person)}</p>
                      <div className="flex items-center gap-2">
                        <Badge tone={badge.tone}>{badge.label}</Badge>
                        {person.status === "active" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Take ${who(person)} out of the sequence`}
                            loading={stop.isPending && stop.variables?.enrolmentId === person.id}
                            onClick={() =>
                              stop.mutate(
                                { sequenceId, enrolmentId: person.id },
                                {
                                  onSuccess: () => toast.success("Taken out of the sequence"),
                                  onError: (error) => toastError(error),
                                },
                              )
                            }
                          >
                            Take out
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    <p className={META}>
                      {person.entry_event} · joined {formatDayTime(person.enrolled_at, timezone)}
                    </p>
                    {person.status === "active" && person.next_step ? (
                      <p className="text-sm">
                        On step {person.next_step} of {person.step_count}
                        {person.next_due_at ? `, due ${formatDayTime(person.next_due_at, timezone)}` : ""}
                      </p>
                    ) : null}
                    {person.stop_text ? <p className="text-sm text-warning">{person.stop_text}</p> : null}
                    {person.last_run ? (
                      <p className="text-sm text-fg-secondary">
                        Step {person.last_run.position}: {person.last_run.status}
                        {person.last_run.reason ? `. ${person.last_run.reason}` : ""}
                      </p>
                    ) : null}
                  </Card>
                </li>
              );
            })}
          </ul>
          <div className="flex items-center justify-between gap-2">
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Newer
            </Button>
            <p className={META}>
              {page * PEOPLE_PAGE + 1} to {page * PEOPLE_PAGE + people.data.items.length} of {people.data.total}
            </p>
            <Button variant="secondary" size="sm" disabled={!people.data.has_more} onClick={() => setPage(page + 1)}>
              Older
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
