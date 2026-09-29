"use client";

import { Check, X } from "lucide-react";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import {
  creditsText,
  durationText,
  MODE_LABEL,
  RUN_STATUS_LABEL,
  RUN_STATUS_TONE,
  runDuration,
  runOutcome,
  STEP_STATUS_LABEL,
  TIER_LABEL,
} from "@/lib/agent/format";
import { actionPath } from "@/lib/agent/routes";
import type { AgentRunDetail, AgentStep } from "@/lib/api/types";
import { TONE_CLASS } from "@/lib/inbox/format";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { AnswerText, SourcesList } from "./AnswerText";

const MICRO = "text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase";

export function RunStatusChip({ status }: { status: AgentRunDetail["status"] }) {
  return (
    <span
      className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap", TONE_CLASS[RUN_STATUS_TONE[status]])}
      data-status={status}
    >
      {RUN_STATUS_LABEL[status]}
    </span>
  );
}

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="group">
      <summary className="min-h-8 cursor-pointer py-1 text-xs text-fg-secondary select-none hover:text-fg">{label}</summary>
      {/* Text only: arguments and results are shown, never interpreted. */}
      <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-line bg-canvas p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-fg-secondary">{label}</dt>
      <dd className="text-sm break-words tabular-nums">{children}</dd>
    </div>
  );
}

/**
 * FR-AGT-07 / TR-AGT-08: everything a run kept, for owners and admins: the request, who asked,
 * the answer and what it cited, prepared actions, and each step's tool, arguments, result,
 * outcome, latency and verification; the run's credits, model and prompt version. No model
 * reasoning is stored or shown.
 */
export function RunTrace({
  run,
  slug,
  timeZone,
  now,
  onNavigate,
}: {
  run: AgentRunDetail;
  slug: string;
  timeZone: string;
  now: Date;
  onNavigate?: () => void;
}) {
  const outcome = runOutcome(run.status, run.error);
  return (
    <div className="space-y-5" data-testid="run-trace">
      <section className="space-y-2">
        <p className={MICRO}>Request</p>
        <p className="text-sm break-words whitespace-pre-wrap">{run.request}</p>
        <dl className="grid grid-cols-2 gap-3 pt-1 sm:grid-cols-3">
          <Fact label="Asked by">{run.requested_by?.name ?? (run.source === "standing" ? "Standing instruction" : "Former member")}</Fact>
          <Fact label="Asked">{formatDayTime(run.created_at, timeZone, now)}</Fact>
          <Fact label="Outcome">
            <RunStatusChip status={run.status} />
          </Fact>
          <Fact label="Credits">{creditsText(run.credits)}</Fact>
          <Fact label="Took">{durationText(runDuration(run))}</Fact>
          <Fact label="Mode">{MODE_LABEL[run.mode]}</Fact>
          <Fact label="Model">{run.model ?? "—"}</Fact>
          <Fact label="Prompt">{run.prompt_version ?? "—"}</Fact>
        </dl>
      </section>

      {outcome || run.error ? (
        <section className="space-y-1" role="status">
          <p className={MICRO}>{outcome?.title ?? "Error"}</p>
          <p className="text-sm text-fg-secondary">
            {run.error ? `${run.error.message} (${run.error.code})` : outcome?.body}
          </p>
        </section>
      ) : null}

      {run.answer?.trim() ? (
        <section className="space-y-3">
          <p className={MICRO}>Answer</p>
          <AnswerText answer={run.answer} refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
          <SourcesList refs={run.answer_refs} slug={slug} onNavigate={onNavigate} />
        </section>
      ) : null}

      {run.action_cards.length > 0 ? (
        <section className="space-y-2">
          <p className={MICRO}>Prepared actions</p>
          <ul className="space-y-2">
            {run.action_cards.map((card, index) => (
              <li key={index} className="rounded-lg border border-line bg-field p-2 text-sm">
                <p className="font-medium">{card.label}</p>
                {card.note ? <p className="text-xs text-fg-secondary">{card.note}</p> : null}
                <p className="font-mono text-[11px] break-all text-fg-secondary">{actionPath(card)}</p>
                <Json label="Prefilled values" value={card.prefill} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="space-y-2">
        <p className={MICRO}>Steps</p>
        {run.steps.length === 0 ? (
          <p className="text-sm text-fg-secondary">No steps ran.</p>
        ) : (
          <ol className="space-y-2" aria-label="Steps">
            {run.steps.map((step) => (
              <StepTrace key={step.id} step={step} />
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function StepTrace({ step }: { step: AgentStep }) {
  const failed = step.status === "failed" || step.status === "blocked";
  return (
    <li className="space-y-1 rounded-lg border border-line bg-field p-3" data-testid="step-trace" data-status={step.status}>
      <div className="flex flex-wrap items-start gap-x-2 gap-y-1">
        <span className="text-xs text-fg-secondary tabular-nums">{step.ordinal + 1}.</span>
        <span className="min-w-0 flex-1 text-sm font-medium break-words">{step.label}</span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium",
            failed ? TONE_CLASS.danger : step.status === "succeeded" ? TONE_CLASS.neutral : TONE_CLASS.warning,
          )}
        >
          {STEP_STATUS_LABEL[step.status]}
        </span>
      </div>
      <p className="text-xs text-fg-secondary">
        {[
          step.tool ? step.tool : step.kind === "report" ? "Report" : step.kind === "condition" ? "Condition" : null,
          step.tier ? TIER_LABEL[step.tier] : null,
          durationText(step.latency_ms),
          step.attempts > 1 ? `${step.attempts} attempts` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {step.summary ? <p className="text-sm break-words">{step.summary}</p> : null}
      {step.error ? (
        <p className="text-xs break-words text-danger-fg">
          {step.error.message} ({step.error.code})
        </p>
      ) : null}
      {step.decision ? <p className="text-xs text-fg-secondary">Gateway: {step.decision}</p> : null}
      {step.verification ? (
        <div className="text-xs">
          <p className={cn("flex items-center gap-1", step.verification.verified ? "text-success" : "text-warning")}>
            {step.verification.verified ? <Check className="size-3.5" aria-hidden /> : <X className="size-3.5" aria-hidden />}
            {step.verification.verified ? "Verified" : "Not confirmed"}
          </p>
          {step.verification.checked.length > 0 ? (
            <p className="text-fg-secondary">Checked: {step.verification.checked.join("; ")}</p>
          ) : null}
          {step.verification.external_ids.length > 0 ? (
            <p className="font-mono break-all text-fg-secondary">{step.verification.external_ids.join(", ")}</p>
          ) : null}
        </div>
      ) : null}
      <Json label="Arguments" value={step.args} />
      {step.result ? <Json label="Result" value={step.result} /> : null}
    </li>
  );
}

export function RunTraceSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading the run">
      <Skeleton className="h-4 w-3/4 bg-raised" />
      <Skeleton className="h-16 w-full rounded-lg bg-raised" />
      <Skeleton className="h-16 w-full rounded-lg bg-raised" />
    </div>
  );
}
