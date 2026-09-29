"use client";

import { Check, Info, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useAiDecision, useAiDecisionFeedback } from "@/lib/api/queries";
import type { AiDecision } from "@/lib/api/types";
import { checkLabel, checkValue } from "@/lib/ai/format";
import { errorMessage } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

const TITLE: Record<AiDecision["outcome"], string> = {
  auto_sent: "Why the AI sent this",
  escalated: "Why the AI didn't reply",
  skipped: "Why the AI didn't reply",
};

/**
 * F-09: the info button on a "Sent by AI" bubble. It opens the decision's checks (TR-AI-07) and
 * "Should not have sent" feedback (FR-SUG-04). The decision loads when the popover opens.
 */
export function DecisionInfo({ messageId }: { messageId: string }) {
  const workspace = useCurrentWorkspace();
  const [open, setOpen] = useState(false);
  const decision = useAiDecision(workspace.id, messageId, open);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Why the AI sent this"
          className="-my-1 ml-0.5 grid size-6 place-items-center rounded-full text-white/90 hover:bg-white/15"
        >
          <Info className="size-3.5" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 border-line bg-panel p-3 text-fg shadow-xl">
        {decision.isPending ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading the decision">
            <Skeleton className="h-3 w-1/2 bg-raised" />
            <Skeleton className="h-3 w-full bg-raised" />
            <Skeleton className="h-3 w-5/6 bg-raised" />
          </div>
        ) : decision.isError ? (
          <p role="alert" className="text-sm text-danger-fg">
            {errorMessage(decision.error)}
          </p>
        ) : (
          <DecisionDetails decision={decision.data} messageId={messageId} />
        )}
      </PopoverContent>
    </Popover>
  );
}

export function DecisionDetails({ decision, messageId }: { decision: AiDecision; messageId: string }) {
  const workspace = useCurrentWorkspace();
  const feedback = useAiDecisionFeedback(workspace.id, messageId);
  const checks = [...decision.checks].sort((a, b) => a.n - b.n);
  const bad = decision.user_feedback === "bad";

  const give = (value: "bad" | null) =>
    feedback.mutate(
      { decisionId: decision.id, feedback: value },
      {
        onSuccess: () => (value ? toast.success("Thanks. Auto learns from this.") : undefined),
        onError: (error) => toast.error(errorMessage(error)),
      },
    );

  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold">{TITLE[decision.outcome]}</p>
      <ul className="space-y-1.5" aria-label="Checks">
        {checks.map((check) => {
          const value = checkValue(check);
          return (
            <li key={check.n} className="flex items-start gap-2 text-sm" data-passed={check.passed}>
              {check.passed ? (
                <Check className="mt-0.5 size-4 shrink-0 text-success" aria-label="Passed" />
              ) : (
                <X className="mt-0.5 size-4 shrink-0 text-danger" aria-label="Failed" />
              )}
              <span className={cn("flex-1", check.passed ? "text-fg" : "text-danger-fg")}>{checkLabel(check)}</span>
              {value ? <span className="shrink-0 text-xs text-fg-secondary tabular-nums">{value}</span> : null}
            </li>
          );
        })}
      </ul>
      {decision.outcome === "auto_sent" ? (
        <div className="border-t border-line pt-3">
          {bad ? (
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-fg-secondary">You marked this as a reply the AI shouldn&apos;t have sent.</p>
              <Button variant="ghost" size="xs" disabled={feedback.isPending} onClick={() => give(null)}>
                Undo
              </Button>
            </div>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              className="w-full"
              disabled={feedback.isPending}
              onClick={() => give("bad")}
            >
              Should not have sent
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
