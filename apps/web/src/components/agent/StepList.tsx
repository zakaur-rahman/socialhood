"use client";

import { Ban, Check, CircleDashed, Hourglass, LoaderCircle, MinusCircle, X, type LucideIcon } from "lucide-react";

import { secondsText, STEP_STATUS_LABEL, WAITING_AFTER_MS } from "@/lib/agent/format";
import type { AgentRunStatus, AgentStep, AgentStepStatus } from "@/lib/api/types";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

const STEP_ICON: Record<AgentStepStatus, { icon: LucideIcon; className: string }> = {
  pending: { icon: CircleDashed, className: "text-fg-secondary" },
  running: { icon: LoaderCircle, className: "text-brand-fg motion-safe:animate-spin" },
  succeeded: { icon: Check, className: "text-success" },
  failed: { icon: X, className: "text-danger" },
  skipped: { icon: MinusCircle, className: "text-fg-secondary" },
  blocked: { icon: Ban, className: "text-warning" },
  awaiting_approval: { icon: Hourglass, className: "text-warning" },
};

function StepRow({ step }: { step: AgentStep }) {
  const { icon: Icon, className: iconClass } = STEP_ICON[step.status];
  return (
    <li className="flex gap-2.5 text-sm leading-6" data-status={step.status}>
      <Icon className={cn("mt-1 size-4 shrink-0", iconClass)} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="text-fg-secondary">
          {step.label}
          <span className="sr-only">: {STEP_STATUS_LABEL[step.status]}</span>
        </span>
        {step.summary ? <span className="block text-xs leading-5 break-words text-fg-secondary">{step.summary}</span> : null}
        {step.status === "failed" && step.error?.message ? (
          <span className="block text-xs leading-5 break-words text-danger-fg">{step.error.message}</span>
        ) : null}
      </span>
    </li>
  );
}

/** A finished run's steps in plain words (agent-architecture.html §12), for the disclosure. */
export function StepList({ steps, className }: { steps: AgentStep[]; className?: string }) {
  return (
    <ol aria-label="Steps" className={cn("space-y-1", className)} data-testid="steps">
      {steps.map((step) => (
        <StepRow key={step.id} step={step} />
      ))}
    </ol>
  );
}

/** What a working run is doing when no step is running: before its first step, or between them. */
function idleLabel(status: AgentRunStatus, steps: AgentStep[], waitedMs: number): string {
  if (status === "queued") return waitedMs > WAITING_AFTER_MS ? "Waiting to start" : "Starting";
  return steps.length === 0 ? "Reading your question" : "Working on it";
}

/**
 * A working run (agent-architecture.html §12): finished steps with their outcome, then the step
 * it is on as a softly shimmering label with the seconds so far. No model reasoning is shown. New
 * steps and labels are announced politely; the ticking seconds are not.
 */
export function WorkingSteps({
  steps,
  status,
  askedAt,
}: {
  steps: AgentStep[];
  status: AgentRunStatus;
  /** When the member asked (the run's created_at): the seconds count from there. */
  askedAt: string;
}) {
  const now = useNow(1_000);
  const waited = Math.max(0, now.getTime() - new Date(askedAt).getTime());
  const running = [...steps].reverse().find((step) => step.status === "running" || step.status === "pending");
  const done = steps.filter((step) => step !== running);
  const label = running?.label ?? idleLabel(status, steps, waited);

  return (
    <ol aria-label="Steps" aria-live="polite" aria-relevant="additions text" className="space-y-1" data-testid="steps">
      {done.map((step) => (
        <StepRow key={step.id} step={step} />
      ))}
      <li className="flex items-center gap-2.5 text-sm leading-6" data-status="current">
        <span className="relative flex size-4 shrink-0 items-center justify-center" aria-hidden>
          <span className="size-2 rounded-full bg-brand motion-safe:animate-pulse" />
        </span>
        <span className="text-shimmer min-w-0 font-medium">{label}…</span>
        <span className="shrink-0 text-xs text-fg-secondary tabular-nums" aria-hidden data-testid="elapsed">
          {secondsText(Math.max(waited, 1000))}
        </span>
      </li>
    </ol>
  );
}
