"use client";

import { Pencil } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useCorrectAnalysis } from "@/lib/api/queries";
import type { AnalysisCorrection, Intent, MessageAnalysis, Sentiment } from "@/lib/api/types";
import {
  INTENT_LABEL,
  INTENTS,
  PRIORITY_LABEL,
  PRIORITY_TONE,
  SENTIMENT_DOT,
  SENTIMENT_LABEL,
  SENTIMENTS,
} from "@/lib/ai/format";
import { TONE_CLASS } from "@/lib/inbox/format";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";
import { EYEBROW } from "@/styles/tokens";

const CHIP = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium";

/**
 * A 24 px icon button inside a line of chips or meta text (Correct, and DecisionInfo's info): the
 * hover and open fills from the tokens, the global focus outline, and on coarse pointers a 40 px
 * hit area from a pseudo-element instead of a 40 px box (DESIGN_SYSTEM §8.4, the chip-remove rule).
 */
export const INLINE_ICON_BUTTON =
  "relative grid size-6 shrink-0 place-items-center rounded-full text-fg-secondary transition-[color,background-color] duration-fast ease-standard after:absolute after:inset-0 hover:bg-hover hover:text-fg aria-expanded:bg-pressed aria-expanded:text-fg pointer-coarse:after:-inset-2";

export function IntentChip({ intent }: { intent: Intent }) {
  return <span className={cn(CHIP, TONE_CLASS.brand)}>{INTENT_LABEL[intent]}</span>;
}

export function SentimentChip({ sentiment }: { sentiment: Sentiment }) {
  return (
    <span className={cn(CHIP, TONE_CLASS.neutral)}>
      <span className={cn("size-1.5 rounded-full", SENTIMENT_DOT[sentiment])} aria-hidden />
      {SENTIMENT_LABEL[sentiment]}
    </span>
  );
}

export function PriorityChip({ priority }: { priority: MessageAnalysis["priority"] }) {
  return <span className={cn(CHIP, TONE_CLASS[PRIORITY_TONE[priority]])}>{PRIORITY_LABEL[priority]} priority</span>;
}

/**
 * FR-AI-02 in the thread: intent, sentiment and priority of the analysed inbound message, with
 * Correct (FR-AI-04).
 */
export function AnalysisChips({ analysis, conversationId }: { analysis: MessageAnalysis; conversationId: string }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1" aria-label="AI analysis" role="group">
      <IntentChip intent={analysis.intent} />
      <SentimentChip sentiment={analysis.sentiment} />
      <PriorityChip priority={analysis.priority} />
      <CorrectAnalysis analysis={analysis} conversationId={conversationId} />
    </div>
  );
}

/** FR-AI-04: change the intent or sentiment; corrections feed the evaluation set. */
export function CorrectAnalysis({
  analysis,
  conversationId,
  variant = "icon",
}: {
  analysis: MessageAnalysis;
  conversationId: string;
  variant?: "icon" | "text";
}) {
  const workspace = useCurrentWorkspace();
  const correct = useCorrectAnalysis(workspace.id, conversationId);
  const [open, setOpen] = useState(false);
  const [intent, setIntent] = useState<Intent>(analysis.intent);
  const [sentiment, setSentiment] = useState<Sentiment>(analysis.sentiment);

  const openChange = (next: boolean) => {
    if (next) {
      setIntent(analysis.intent);
      setSentiment(analysis.sentiment);
    }
    setOpen(next);
  };

  const changes: AnalysisCorrection = {};
  if (intent !== analysis.intent) changes.intent = intent;
  if (sentiment !== analysis.sentiment) changes.sentiment = sentiment;
  const changed = Object.keys(changes).length > 0;

  const save = () =>
    correct.mutate(
      { id: analysis.id, correction: changes },
      {
        onSuccess: () => {
          toast.success("Correction saved");
          setOpen(false);
        },
        onError: (error) => toastError(error),
      },
    );

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        {variant === "icon" ? (
          // 24 px among 20 px chips: the visual stays small and a pseudo-element makes the hit area
          // 40 px on coarse pointers (DESIGN_SYSTEM §8.4), so the chip row doesn't grow or wrap.
          <button type="button" aria-label="Correct the analysis" className={INLINE_ICON_BUTTON}>
            <Pencil className="size-3" aria-hidden />
          </button>
        ) : (
          <Button variant="ghost" size="xs" className="text-brand-fg">
            Correct the AI
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-3">
        <div className="space-y-3" aria-label="Correct the analysis" role="group">
          <p className="text-sm font-semibold">Correct the AI</p>
          <div className="space-y-1.5">
            <p id={`intent-${analysis.id}`} className={EYEBROW}>
              Intent
            </p>
            {/* Thirteen intents: chips that wrap (DESIGN_SYSTEM §8.2), one of them chosen. */}
            <ToggleGroup
              variant="chips"
              value={intent}
              onValueChange={(value) => setIntent(value as Intent)}
              aria-labelledby={`intent-${analysis.id}`}
            >
              {INTENTS.map((value) => (
                <ToggleGroupItem key={value} value={value}>
                  {INTENT_LABEL[value]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="space-y-1.5">
            <p id={`sentiment-${analysis.id}`} className={EYEBROW}>
              Sentiment
            </p>
            <ToggleGroup
              size="sm"
              value={sentiment}
              onValueChange={(value) => setSentiment(value as Sentiment)}
              aria-labelledby={`sentiment-${analysis.id}`}
            >
              {SENTIMENTS.map((value) => (
                <ToggleGroupItem key={value} value={value}>
                  {SENTIMENT_LABEL[value]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" disabled={!changed || correct.isPending} onClick={save}>
              {correct.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * UX-INB-09 "Latest message" (C-063): intent, sentiment, priority and the analysis's topics, with
 * "Correct the AI". The lead score is on the customer card.
 */
export function AnalysisDetails({ analysis, conversationId }: { analysis: MessageAnalysis | null | undefined; conversationId: string }) {
  if (!analysis) {
    return <p className="text-sm text-fg-secondary">Not analysed yet. New customer messages are analysed as they arrive.</p>;
  }
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
        <dt className="text-fg-secondary">Intent</dt>
        <dd className="justify-self-end">
          <IntentChip intent={analysis.intent} />
        </dd>
        <dt className="text-fg-secondary">Sentiment</dt>
        <dd className="justify-self-end">
          <SentimentChip sentiment={analysis.sentiment} />
        </dd>
        <dt className="text-fg-secondary">Priority</dt>
        <dd className="justify-self-end">
          <PriorityChip priority={analysis.priority} />
        </dd>
      </dl>
      {analysis.topics.length > 0 ? (
        <ul aria-label="Topics" className="flex flex-wrap gap-1">
          {analysis.topics.map((topic) => (
            <li key={topic} className={cn(CHIP, "border border-line", TONE_CLASS.neutral)}>
              {topic}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex items-center justify-between gap-2 border-t border-line pt-2">
        <p className="text-xs text-fg-secondary">{analysis.corrected ? "Corrected by your team" : "Wrong? Correct it to teach the AI."}</p>
        <CorrectAnalysis analysis={analysis} conversationId={conversationId} variant="text" />
      </div>
    </div>
  );
}
