"use client";

import { AlertTriangle, Ban, ChevronRight, CircleSlash, Copy, CreditCard, RotateCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { BILLING_HREF } from "@/components/shell/nav";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { answerToPlainText } from "@/lib/agent/answer";
import { creditsText, followUpsFor, isActive, runOutcome, workedFor, type RunOutcome } from "@/lib/agent/format";
import { useAgentRun } from "@/lib/api/queries";
import type { AgentRun, AgentRunDetail, Role } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { ActionCardView } from "./ActionCardView";
import { AnswerText, SourcesList } from "./AnswerText";
import { StepList, WorkingSteps } from "./StepList";

export type RunContext = {
  wid: string;
  slug: string;
  timeZone: string;
  role: Role;
  now: Date;
  /** Following a link or action card leaves the panel: the caller closes it. */
  onNavigate?: () => void;
  /** Ask in the same thread: again after a failure or a cancel, or a follow-up. */
  onAsk?: (request: string) => void;
  /** A question is being sent, or another run in the thread is working. */
  busy?: boolean;
};

/**
 * One exchange of a thread, as a chat reads: the member's question in a neutral bubble on the
 * right, then Social Hood's side (a small mark, no card): the live steps while it works, and its
 * answer with citations, sources, prepared actions, Copy and follow-ups, or a compact failed,
 * out-of-credits, cancelled or expired notice (FR-AGT-01, FR-AGT-03, FR-AGT-06).
 */
export function RunView({ run: listed, context, latest = false }: { run: AgentRun; context: RunContext; latest?: boolean }) {
  const { wid, timeZone, now } = context;
  // A run that was working when it appeared stays watched, so its completion is fetched.
  const [watched] = useState(() => isActive(listed.status));
  const detail = useAgentRun(wid, listed.id, watched || isActive(listed.status));
  const run: AgentRun | AgentRunDetail = detail.data ?? listed;
  const asked = formatDayTime(run.created_at, timeZone, now);

  return (
    <article aria-label={`Question: ${run.request}`} className="group/run space-y-4" data-testid="run" data-status={run.status}>
      <div className="flex items-end justify-end gap-2">
        <time
          dateTime={run.created_at}
          className="mb-2 shrink-0 text-[11px] text-fg-secondary opacity-0 group-focus-within/run:opacity-100 group-hover/run:opacity-100 motion-safe:transition-opacity"
        >
          {asked}
        </time>
        <div
          title={asked}
          className="max-w-[80%] rounded-2xl bg-raised px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap text-fg"
        >
          {run.request}
        </div>
      </div>
      <div className="flex gap-3">
        <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-brand-fg" aria-hidden>
          <Sparkles className="size-3.5" />
        </span>
        {isActive(run.status) ? (
          <div className="min-w-0 flex-1 pt-0.5" aria-busy="true">
            <WorkingSteps steps={detail.data?.steps ?? []} status={run.status} askedAt={run.created_at} />
          </div>
        ) : (
          <Finished run={run} detail={detail.data} context={context} latest={latest} />
        )}
      </div>
    </article>
  );
}

function Finished({
  run,
  detail,
  context,
  latest,
}: {
  run: AgentRun;
  detail: AgentRunDetail | undefined;
  context: RunContext;
  latest: boolean;
}) {
  const { slug, timeZone, now, onNavigate } = context;
  const outcome = runOutcome(run.status, run.error);
  const answer = run.answer?.trim() ? run.answer : null;
  const followUps = latest && answer && context.onAsk ? followUpsFor(run.answer_refs, run.request) : [];

  return (
    <div className="min-w-0 flex-1 space-y-3" data-testid="run-result">
      <StepsDisclosure run={run} detail={detail} context={context} />
      {outcome ? <OutcomeNotice outcome={outcome} run={run} context={context} /> : null}
      {answer ? (
        <>
          {run.status === "partial" && !outcome ? (
            <p className="flex items-center gap-2 text-xs text-warning">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden />
              Some steps didn&apos;t finish. The answer says what&apos;s missing.
            </p>
          ) : null}
          <AnswerText answer={answer} refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
          <SourcesList refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
        </>
      ) : !outcome ? (
        // Final, but the answer is still on its way (agent.completed is followed by a fetch).
        <div aria-busy="true" aria-label="Getting the answer" className="space-y-2 pt-1">
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
      {answer ? <AnswerActions answer={answer} credits={run.credits} alwaysVisible={latest} /> : null}
      {followUps.length > 0 ? (
        <ul aria-label="Follow-up questions" className="flex flex-wrap gap-2 pt-1">
          {followUps.map((prompt) => (
            <li key={prompt}>
              <button
                type="button"
                disabled={context.busy}
                onClick={() => context.onAsk?.(prompt)}
                className="min-h-10 rounded-full border border-line px-3.5 text-left text-sm text-fg-secondary hover:bg-white/5 hover:text-fg disabled:opacity-50 md:min-h-8"
              >
                {prompt}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Copy and the credits used, under an answer. With a mouse it shows on hover (or keyboard focus)
 * except under the latest answer; on touch screens it is always there.
 */
function AnswerActions({ answer, credits, alwaysVisible }: { answer: string; credits: number; alwaysVisible: boolean }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(answerToPlainText(answer));
      toast.success("Copied");
    } catch {
      toast.error("Couldn't copy. Select the text and copy it instead.");
    }
  };
  return (
    <div
      className={cn(
        "-ml-2 flex items-center gap-1 text-xs text-fg-secondary",
        !alwaysVisible &&
          "motion-safe:transition-opacity pointer-fine:opacity-0 pointer-fine:group-hover/run:opacity-100 pointer-fine:focus-within:opacity-100",
      )}
      data-testid="answer-actions"
    >
      <Button
        variant="ghost"
        size="sm"
        className="min-h-10 px-2 text-fg-secondary hover:text-fg md:min-h-7"
        aria-label="Copy answer"
        onClick={() => void copy()}
      >
        <Copy aria-hidden /> Copy
      </Button>
      {credits > 0 ? <span className="px-1 tabular-nums">{creditsText(credits)}</span> : null}
    </div>
  );
}

const OUTCOME_ICON = { quota: CreditCard, failed: AlertTriangle, cancelled: CircleSlash, expired: Ban } as const;
const OUTCOME_TONE = {
  quota: "bg-warning/10 text-warning",
  failed: "bg-danger/10 text-danger-fg",
  cancelled: "bg-white/5 text-fg-secondary",
  expired: "bg-white/5 text-fg-secondary",
} as const;

/** A compact inline notice: what happened, in one or two lines, with Try again or Upgrade. */
function OutcomeNotice({ outcome, run, context }: { outcome: RunOutcome; run: AgentRun; context: RunContext }) {
  const Icon = OUTCOME_ICON[outcome.kind];
  const canAskAgain = outcome.kind !== "quota" && context.onAsk;
  return (
    <div
      role={outcome.kind === "cancelled" ? "status" : "alert"}
      className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg px-3 py-2 text-sm", OUTCOME_TONE[outcome.kind])}
      data-outcome={outcome.kind}
    >
      <p className="flex min-w-0 flex-1 basis-56 items-start gap-2">
        <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span className="min-w-0">
          <span className="font-medium">{outcome.title}</span>
          <span className="text-fg-secondary"> · </span>
          <span className="text-fg-secondary">{outcome.body}</span>
        </span>
      </p>
      {canAskAgain ? (
        <Button
          variant="ghost"
          size="sm"
          className="min-h-10 px-2 text-fg hover:bg-white/10 md:min-h-7"
          disabled={context.busy}
          onClick={() => context.onAsk?.(run.request)}
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
  );
}

function stepsText(count: number): string {
  if (count === 0) return "No steps";
  return count === 1 ? "1 step" : `${count} steps`;
}

/** "Worked for 6 s · 3 steps", collapsed; open, the steps in plain words. */
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
  const worked = workedFor(run);
  const label = [worked ? `Worked for ${worked}` : null, steps ? stepsText(steps.length) : null].filter(Boolean).join(" · ");
  const id = `steps-${run.id}`;
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="-ml-1 inline-flex min-h-10 items-center gap-1 rounded-md px-1 text-xs text-fg-secondary hover:text-fg md:min-h-6"
        data-testid="steps-toggle"
      >
        {label || "Steps"}
        <ChevronRight className={cn("size-3.5 motion-safe:transition-transform", open && "rotate-90")} aria-hidden />
      </button>
      {open ? (
        <div id={id} className="mt-1 border-l border-line pl-3">
          {steps ? (
            steps.length > 0 ? (
              <StepList steps={steps} />
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
