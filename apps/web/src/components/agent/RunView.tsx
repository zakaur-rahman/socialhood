"use client";

import { AlertTriangle, Ban, ChevronDown, CircleSlash, CreditCard, RotateCw, Square } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { BILLING_HREF } from "@/components/shell/nav";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { creditsText, isActive, runOutcome, type RunOutcome } from "@/lib/agent/format";
import { useAgentRun, useCancelAgentRun } from "@/lib/api/queries";
import type { AgentRun, AgentRunDetail, Role } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { ActionCardView } from "./ActionCardView";
import { AnswerText, SourcesList } from "./AnswerText";
import { StepList } from "./StepList";

export type RunContext = {
  wid: string;
  slug: string;
  timeZone: string;
  role: Role;
  now: Date;
  /** Following a link or action card leaves the panel: the caller closes it. */
  onNavigate?: () => void;
  /** Ask a request again in the same thread (after a failure or a cancel). */
  onAskAgain?: (request: string) => void;
  /** A question is being sent, or another run in the thread is working. */
  busy?: boolean;
};

/**
 * One exchange of a thread: the member's question, then the run's live steps while it works,
 * and its answer (with citations and action cards) or an explicit failed, out-of-credits or
 * cancelled state (FR-AGT-01, FR-AGT-03, FR-AGT-06).
 */
export function RunView({ run: listed, context }: { run: AgentRun; context: RunContext }) {
  const { wid, timeZone, now } = context;
  // A run that was working when it appeared stays watched, so its completion is fetched.
  const [watched] = useState(() => isActive(listed.status));
  const detail = useAgentRun(wid, listed.id, watched || isActive(listed.status));
  const run: AgentRun | AgentRunDetail = detail.data ?? listed;

  return (
    <article aria-label={`Question: ${run.request}`} className="space-y-3" data-testid="run" data-status={run.status}>
      <div className="flex justify-end">
        <div className="bg-brand-gradient max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap text-white">
          {run.request}
          <time dateTime={run.created_at} className="mt-0.5 block text-right text-[11px] text-white/70">
            {formatDayTime(run.created_at, timeZone, now)}
          </time>
        </div>
      </div>
      {isActive(run.status) ? (
        <Working run={run} steps={detail.data?.steps ?? []} context={context} />
      ) : (
        <Finished run={run} detail={detail.data} context={context} />
      )}
    </article>
  );
}

function Working({ run, steps, context }: { run: AgentRun; steps: AgentRunDetail["steps"]; context: RunContext }) {
  const cancel = useCancelAgentRun(context.wid);
  return (
    <div className="space-y-3 rounded-xl border border-line bg-panel p-3" aria-busy="true">
      <StepList steps={steps} status={run.status} live />
      <Button
        variant="secondary"
        size="sm"
        className="min-h-10 md:min-h-7"
        disabled={cancel.isPending}
        onClick={() =>
          cancel.mutate(run.id, {
            onError: (error) => toast.error(errorMessage(error)),
          })
        }
      >
        <Square aria-hidden /> {cancel.isPending ? "Cancelling…" : "Cancel"}
      </Button>
    </div>
  );
}

function Finished({
  run,
  detail,
  context,
}: {
  run: AgentRun;
  detail: AgentRunDetail | undefined;
  context: RunContext;
}) {
  const { slug, timeZone, now, onNavigate } = context;
  const outcome = runOutcome(run.status, run.error);
  const answer = run.answer?.trim() ? run.answer : null;

  return (
    <div className="space-y-3 rounded-xl border border-line bg-panel p-3" data-testid="run-result">
      {outcome ? <OutcomeNotice outcome={outcome} run={run} context={context} /> : null}
      {answer ? (
        <>
          {run.status === "partial" && !outcome ? (
            <p className="flex items-start gap-2 rounded-lg bg-warning/15 px-3 py-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Some steps didn&apos;t finish. The answer says what&apos;s missing.
            </p>
          ) : null}
          <AnswerText answer={answer} refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
          <SourcesList refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
        </>
      ) : !outcome ? (
        // Final, but the answer is still on its way (agent.completed is followed by a fetch).
        <div aria-busy="true" aria-label="Getting the answer" className="space-y-2">
          <Skeleton className="h-3 w-5/6 bg-raised" />
          <Skeleton className="h-3 w-2/3 bg-raised" />
        </div>
      ) : null}
      {run.action_cards.length > 0 ? (
        <div className="space-y-2">
          {run.action_cards.map((card, index) => (
            <ActionCardView
              key={`${card.kind}:${index}`}
              card={card}
              slug={slug}
              timeZone={timeZone}
              now={now}
              onOpen={onNavigate}
            />
          ))}
        </div>
      ) : null}
      <StepsDisclosure run={run} detail={detail} context={context} />
    </div>
  );
}

const OUTCOME_ICON = { quota: CreditCard, failed: AlertTriangle, cancelled: CircleSlash, expired: Ban } as const;

function OutcomeNotice({ outcome, run, context }: { outcome: RunOutcome; run: AgentRun; context: RunContext }) {
  const Icon = OUTCOME_ICON[outcome.kind];
  const tone =
    outcome.kind === "failed" ? "text-danger-fg" : outcome.kind === "quota" ? "text-warning" : "text-fg-secondary";
  const canAskAgain = outcome.kind !== "quota" && context.onAskAgain;
  return (
    <div role={outcome.kind === "cancelled" ? "status" : "alert"} className="space-y-2" data-outcome={outcome.kind}>
      <p className={cn("flex items-center gap-2 text-sm font-medium", tone)}>
        <Icon className="size-4 shrink-0" aria-hidden /> {outcome.title}
      </p>
      <p className="text-sm text-fg-secondary">{outcome.body}</p>
      <div className="flex flex-wrap gap-2">
        {canAskAgain ? (
          <Button
            variant="secondary"
            size="sm"
            className="min-h-10 md:min-h-7"
            disabled={context.busy}
            onClick={() => context.onAskAgain?.(run.request)}
          >
            <RotateCw aria-hidden /> {outcome.kind === "failed" ? "Try again" : "Ask again"}
          </Button>
        ) : null}
        {outcome.kind === "quota" && context.role !== "agent" ? (
          <Button asChild size="sm" className="bg-brand-gradient min-h-10 text-white md:min-h-7">
            <Link href={BILLING_HREF(context.slug)} onClick={context.onNavigate}>
              Upgrade
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

/** A finished run's steps, on request: the same plain words the live list showed. */
function StepsDisclosure({
  run,
  detail,
  context,
}: {
  run: AgentRun;
  detail: AgentRunDetail | undefined;
  context: RunContext;
}) {
  const [open, setOpen] = useState(false);
  const fetched = useAgentRun(context.wid, run.id, open && !detail);
  const steps = (detail ?? fetched.data)?.steps;
  const id = `steps-${run.id}`;
  return (
    <div className="border-t border-line-subtle pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen(!open)}
          className="-ml-1 inline-flex min-h-10 items-center gap-1 rounded-md px-1 text-xs text-fg-secondary hover:text-fg md:min-h-7"
        >
          <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
          {open ? "Hide steps" : "Show steps"}
        </button>
        {run.credits > 0 ? <span className="text-xs text-fg-secondary tabular-nums">{creditsText(run.credits)}</span> : null}
      </div>
      {open ? (
        <div id={id} className="pt-1">
          {steps ? (
            steps.length > 0 ? (
              <StepList steps={steps} status={run.status} />
            ) : (
              <p className="text-xs text-fg-secondary">No steps ran.</p>
            )
          ) : fetched.isError ? (
            <p className="text-xs text-danger-fg">{errorMessage(fetched.error)}</p>
          ) : (
            <div aria-busy="true" aria-label="Loading steps">
              <Skeleton className="h-3 w-1/2 bg-raised" />
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
