"use client";

import { Ban, Check, CircleDashed, Hourglass, LoaderCircle, MinusCircle, X, type LucideIcon } from "lucide-react";

import { STEP_STATUS_LABEL } from "@/lib/agent/format";
import type { AgentRunStatus, AgentStep, AgentStepStatus } from "@/lib/api/types";
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

/** What the run is doing before its first step (a tool's label says the rest). */
function startingLabel(status: AgentRunStatus): string {
  return status === "queued" ? "Starting" : "Reading your question";
}

/**
 * The steps a run takes, in plain words (agent-architecture.html §12): the tool's label and, when
 * it ends, its outcome. No model reasoning is shown. While the run works, new steps are announced
 * politely to screen readers.
 */
export function StepList({
  steps,
  status,
  live = false,
  className,
}: {
  steps: AgentStep[];
  status: AgentRunStatus;
  live?: boolean;
  className?: string;
}) {
  const showStarting = live && steps.length === 0;
  return (
    <ol
      aria-label="Steps"
      aria-live={live ? "polite" : undefined}
      aria-relevant={live ? "additions text" : undefined}
      className={cn("space-y-1.5", className)}
      data-testid="steps"
    >
      {showStarting ? (
        <li className="flex items-center gap-2 text-sm text-fg-secondary">
          <LoaderCircle className="size-4 shrink-0 text-brand-fg motion-safe:animate-spin" aria-hidden />
          {startingLabel(status)}…
        </li>
      ) : null}
      {steps.map((step) => {
        const { icon: Icon, className: iconClass } = STEP_ICON[step.status];
        const finished = step.status !== "running" && step.status !== "pending";
        return (
          <li key={step.id} className="flex gap-2 text-sm" data-status={step.status}>
            <Icon className={cn("mt-0.5 size-4 shrink-0", iconClass)} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className={cn("block break-words", finished ? "text-fg-secondary" : "text-fg")}>
                {step.label}
                <span className="sr-only">: {STEP_STATUS_LABEL[step.status]}</span>
              </span>
              {step.summary ? <span className="block text-xs break-words text-fg-secondary">{step.summary}</span> : null}
              {step.status === "failed" && step.error?.message ? (
                <span className="block text-xs break-words text-danger-fg">{step.error.message}</span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
