"use client";

import type { Route } from "next";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { useSequence } from "@/lib/api/queries";
import { useCurrentWorkspace } from "@/lib/workspace";

import { SequenceForm } from "./SequenceForm";
import { SequenceNumbers } from "./SequenceNumbers";
import { SequencePeople } from "./SequencePeople";

/** GR-24: one sequence, its steps and rules as a form, and the people in it below. */
export function SequenceDetailPage({ id }: { id: string }) {
  const workspace = useCurrentWorkspace();
  const sequence = useSequence(workspace.id, id);
  const back = { href: `/w/${workspace.slug}/sequences` as Route, label: "Sequences" };

  if (sequence.isPending) {
    return (
      <PageFrame title="Sequence" back={back}>
        <Skeleton className="h-64 w-full" />
      </PageFrame>
    );
  }
  if (sequence.isError) {
    return (
      <PageFrame title="Sequence" back={back}>
        <ErrorState error={sequence.error} onRetry={() => void sequence.refetch()} />
      </PageFrame>
    );
  }
  // Keyed by the last save, so the form starts again from what the server holds.
  return (
    <SequenceForm key={`${sequence.data.id}:${sequence.data.updated_at}:${sequence.data.status}`} sequence={sequence.data}>
      <SequenceNumbers sequenceId={sequence.data.id} />
      <SequencePeople sequenceId={sequence.data.id} />
    </SequenceForm>
  );
}
