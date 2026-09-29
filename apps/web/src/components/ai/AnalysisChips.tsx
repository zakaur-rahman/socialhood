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
import { errorMessage } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

const CHIP = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium";

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
        onError: (error) => toast.error(errorMessage(error)),
      },
    );

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        {variant === "icon" ? (
          <button
            type="button"
            aria-label="Correct the analysis"
            className="grid size-6 place-items-center rounded-full text-fg-secondary hover:bg-white/5 hover:text-fg"
          >
            <Pencil className="size-3" aria-hidden />
          </button>
        ) : (
          <Button variant="ghost" size="xs" className="text-brand-fg">
            Correct
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 border-line bg-panel p-3 shadow-xl">
        <div className="space-y-3" aria-label="Correct the analysis" role="group">
          <p className="text-sm font-semibold">Correct the AI</p>
          <div className="space-y-1.5">
            <p id={`intent-${analysis.id}`} className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">
              Intent
            </p>
            <ToggleGroup
              value={intent}
              onValueChange={(value) => setIntent(value as Intent)}
              aria-labelledby={`intent-${analysis.id}`}
              className="flex-wrap bg-transparent p-0"
            >
              {INTENTS.map((value) => (
                <ToggleGroupItem
                  key={value}
                  value={value}
                  className="min-h-7 flex-none rounded-full bg-field px-2.5 py-1 text-xs data-[state=on]:bg-brand-soft"
                >
                  {INTENT_LABEL[value]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="space-y-1.5">
            <p id={`sentiment-${analysis.id}`} className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">
              Sentiment
            </p>
            <ToggleGroup
              value={sentiment}
              onValueChange={(value) => setSentiment(value as Sentiment)}
              aria-labelledby={`sentiment-${analysis.id}`}
            >
              {SENTIMENTS.map((value) => (
                <ToggleGroupItem key={value} value={value} className="text-xs">
                  {SENTIMENT_LABEL[value]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" className="bg-brand-gradient text-white" disabled={!changed || correct.isPending} onClick={save}>
              {correct.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** UX-INB-09 "Latest message": chips, lead score bar, topics and Correct. */
export function AnalysisDetails({ analysis, conversationId }: { analysis: MessageAnalysis | null | undefined; conversationId: string }) {
  if (!analysis) {
    return <p className="text-sm text-fg-secondary">Not analysed yet. New customer messages are analysed as they arrive.</p>;
  }
  const lead = Math.max(0, Math.min(100, analysis.lead_score));
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
        <dt className="text-fg-secondary">Intent</dt>
        <dd>
          <IntentChip intent={analysis.intent} />
        </dd>
        <dt className="text-fg-secondary">Sentiment</dt>
        <dd>
          <SentimentChip sentiment={analysis.sentiment} />
        </dd>
        <dt className="text-fg-secondary">Priority</dt>
        <dd>
          <PriorityChip priority={analysis.priority} />
        </dd>
        <dt className="text-fg-secondary">Lead</dt>
        <dd className="flex items-center gap-2">
          <span
            role="meter"
            aria-label="Lead score"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={lead}
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-raised"
          >
            <span className="bg-brand-gradient-decor block h-full rounded-full" style={{ width: `${lead}%` }} />
          </span>
          <span className="text-xs tabular-nums text-fg-secondary">{lead} / 100</span>
        </dd>
      </dl>
      {analysis.topics.length > 0 ? (
        <ul aria-label="Topics" className="flex flex-wrap gap-1">
          {analysis.topics.map((topic) => (
            <li key={topic} className={cn(CHIP, TONE_CLASS.neutral)}>
              {topic}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-fg-secondary">{analysis.corrected ? "Corrected by your team" : "Wrong? Correct it to teach the AI."}</p>
        <CorrectAnalysis analysis={analysis} conversationId={conversationId} variant="text" />
      </div>
    </div>
  );
}
