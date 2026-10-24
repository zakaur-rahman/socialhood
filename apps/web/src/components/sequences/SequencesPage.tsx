"use client";

import { ListOrdered, Plus } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSequences } from "@/lib/api/queries";
import type { Sequence } from "@/lib/api/types";
import { SEQUENCE_STATUS } from "@/lib/sequences/format";
import { useCurrentWorkspace } from "@/lib/workspace";
import { META } from "@/styles/tokens";

/**
 * GR-24: Sequences. Timed follow-up messages after something happens (a lead is captured, a tag is
 * added, someone replies to a broadcast). Owners and admins. Each row says what starts it, how many
 * steps it has and where its people are.
 */
export function SequencesPage() {
  const workspace = useCurrentWorkspace();
  const list = useSequences(workspace.id);
  const newHref = `/w/${workspace.slug}/sequences/new` as Route;

  return (
    <PageFrame
      title="Sequences"
      back={{ href: `/w/${workspace.slug}/automations` as Route, label: "Automations" }}
      actions={
        <Button asChild size="lg">
          <Link href={newHref}>
            <Plus aria-hidden /> New <span className="max-[359px]:sr-only">sequence</span>
          </Link>
        </Button>
      }
    >
      <div className="space-y-5">
        {list.data ? (
          <p className={META} data-testid="sequence-limits">
            {list.data.active_limit === null
              ? `${list.data.active} sequences on.`
              : `${list.data.active} of ${list.data.active_limit} sequence${list.data.active_limit === 1 ? "" : "s"} on in your plan.`}{" "}
            A sequence stops for a person when they reply, so nobody gets a follow-up after they have answered.
          </p>
        ) : null}

        {list.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        ) : list.data.items.length === 0 ? (
          <Card>
            <EmptyState
              size="compact"
              icon={<ListOrdered />}
              title="No sequences yet"
              body="A sequence sends a few messages over days after something happens, and stops when the person replies. WhatsApp messages after 24 hours use an approved template and go only to people who agreed to marketing messages."
              action={
                <Button asChild size="sm">
                  <Link href={newHref}>
                    <Plus aria-hidden /> New sequence
                  </Link>
                </Button>
              }
            />
          </Card>
        ) : (
          <ul aria-label="Sequences" className="space-y-3">
            {list.data.items.map((sequence) => (
              <li key={sequence.id}>
                <SequenceRow sequence={sequence} slug={workspace.slug} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageFrame>
  );
}

function SequenceRow({ sequence, slug }: { sequence: Sequence; slug: string }) {
  const status = SEQUENCE_STATUS[sequence.status];
  const people = sequence.enrolments;
  return (
    <Card className="space-y-2" data-testid="sequence-row">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/w/${slug}/sequences/${sequence.id}` as Route}
          className="min-w-0 truncate text-base font-semibold underline-offset-4 hover:underline"
        >
          {sequence.name}
        </Link>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <p className={META}>
        Starts when: {sequence.entry.label}
        {sequence.account_label ? ` · ${sequence.account_label}` : ""} · {sequence.step_count} step
        {sequence.step_count === 1 ? "" : "s"}
      </p>
      <p className="text-sm tabular-nums">
        {people.active} in it · {people.completed} finished · {people.stopped} stopped
      </p>
      {sequence.problems.length > 0 ? <p className="text-sm text-warning">{sequence.problems[0]}</p> : null}
    </Card>
  );
}
