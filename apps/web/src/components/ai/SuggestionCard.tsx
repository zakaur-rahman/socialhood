"use client";

import { AlertTriangle, Loader2, Pencil, RefreshCw, Sparkles, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Suggestion } from "@/lib/api/types";
import { sourceChips } from "@/lib/ai/format";
import { aiCopy } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/** Longer replies start clamped to six lines with "More" (UX-INB-08). */
const LONG_REPLY = 280;

export type SuggestionActions = {
  onSend: () => void;
  onEdit: () => void;
  onRegenerate: () => void;
  onDismiss: () => void;
  onWriteReply: () => void;
  /** Admins only: add the missing answer to knowledge (F-08, F-14). */
  onAddToKnowledge?: () => void;
};

const CARD =
  "mx-4 mb-2 rounded-xl border border-brand-line bg-panel p-3 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2 motion-safe:duration-[180ms]";
const ACTION = "h-10 rounded-md px-3 text-xs font-medium md:h-8";

/**
 * UX-INB-08: the suggested reply between the messages and the composer. States: generating,
 * ready (with sources, "Check this" under 0.6 confidence, regenerations left), not in knowledge.
 */
export function SuggestionCard({
  suggestion,
  generating,
  customerName,
  canSend,
  busy = false,
  actions,
}: {
  suggestion: Suggestion | null;
  /** Drafting the first reply, or a regenerated one (until suggestion.created). */
  generating: boolean;
  /** First name, for "Priya asked about …". */
  customerName: string;
  /** The composer can send right now (window open, account connected). */
  canSend: boolean;
  /** A dismiss or regenerate request is in flight. */
  busy?: boolean;
  actions: SuggestionActions;
}) {
  if (generating || !suggestion) {
    return (
      <section aria-label="Suggested reply" className={CARD} data-state="generating">
        <p className="flex items-center gap-1.5 text-xs font-medium text-brand-fg">
          <Sparkles className="size-3.5" aria-hidden /> Suggested reply
        </p>
        <div className="mt-2 space-y-2" aria-hidden>
          <Skeleton className="h-3 w-11/12 bg-raised" />
          <Skeleton className="h-3 w-2/3 bg-raised" />
        </div>
        <p role="status" className="mt-2 text-xs text-fg-secondary">
          {aiCopy.drafting}
        </p>
      </section>
    );
  }
  if (!suggestion.can_answer) {
    return (
      <section aria-label={aiCopy.notInKnowledge} className={CARD} data-state="not_in_knowledge">
        <div className="flex items-center gap-2">
          <p className="flex flex-1 items-center gap-1.5 text-xs font-medium text-warning">
            <AlertTriangle className="size-3.5" aria-hidden /> {aiCopy.notInKnowledge}
          </p>
          <DismissButton onDismiss={actions.onDismiss} disabled={busy} />
        </div>
        <p className="mt-1.5 text-sm text-fg">
          {customerName} asked about {suggestion.missing_info?.trim() || "something your knowledge doesn't cover"}.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {actions.onAddToKnowledge ? (
            <Button className={cn(ACTION, "bg-brand-gradient text-white")} onClick={actions.onAddToKnowledge}>
              Add to knowledge
            </Button>
          ) : null}
          <Button variant="secondary" className={ACTION} onClick={actions.onWriteReply}>
            Write reply
          </Button>
        </div>
      </section>
    );
  }
  return <ReadyCard suggestion={suggestion} canSend={canSend} busy={busy} actions={actions} />;
}

function ReadyCard({
  suggestion,
  canSend,
  busy,
  actions,
}: {
  suggestion: Suggestion;
  canSend: boolean;
  busy: boolean;
  actions: SuggestionActions;
}) {
  const [expanded, setExpanded] = useState(false);
  const text = suggestion.reply_text ?? "";
  const long = text.length > LONG_REPLY || text.split("\n").length > 6;
  const { shown, more } = sourceChips(suggestion.sources);
  const left = suggestion.regenerations_left;

  return (
    <section aria-label="Suggested reply" className={CARD} data-state="ready">
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="flex flex-1 items-center gap-1.5 text-xs font-medium text-brand-fg">
          <Sparkles className="size-3.5" aria-hidden /> Suggested reply
        </p>
        {shown.map((source) => (
          <span key={source.id} className={cn("max-w-40 truncate rounded-full px-2 py-0.5 text-[11px]", TONE_CLASS.neutral)}>
            From: {source.title}
          </span>
        ))}
        {more > 0 ? (
          <span
            className={cn("rounded-full px-2 py-0.5 text-[11px]", TONE_CLASS.neutral)}
            title={suggestion.sources.slice(2).map((s) => s.title).join(", ")}
          >
            +{more}
          </span>
        ) : null}
        {suggestion.low_confidence ? (
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", TONE_CLASS.warning)} title="The AI isn't sure about this one">
            Check this
          </span>
        ) : null}
        <DismissButton onDismiss={actions.onDismiss} disabled={busy} />
      </div>
      <p className={cn("mt-1.5 text-sm whitespace-pre-wrap break-words text-fg", long && !expanded && "line-clamp-6")}>{text}</p>
      {long ? (
        <button
          type="button"
          className="mt-1 text-xs font-medium text-brand-fg hover:underline"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Less" : "More"}
        </button>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button className={cn(ACTION, "bg-brand-gradient text-white")} disabled={!canSend || !text} onClick={actions.onSend}>
          Send
        </Button>
        <Button variant="secondary" className={ACTION} onClick={actions.onEdit}>
          <Pencil aria-hidden /> Edit
        </Button>
        <Button
          variant="ghost"
          className={ACTION}
          disabled={left <= 0 || busy}
          title={left <= 0 ? "No more drafts for this message" : undefined}
          onClick={actions.onRegenerate}
        >
          {busy ? <Loader2 className="animate-spin" aria-hidden /> : <RefreshCw aria-hidden />} Regenerate
        </Button>
        <span className="text-xs text-fg-secondary tabular-nums">
          {left > 0 ? `${left} ${left === 1 ? "draft" : "drafts"} left` : "No drafts left"}
        </span>
      </div>
    </section>
  );
}

function DismissButton({ onDismiss, disabled }: { onDismiss: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      aria-label="Dismiss suggestion"
      disabled={disabled}
      onClick={onDismiss}
      className="grid size-10 place-items-center rounded-full text-fg-secondary hover:bg-white/5 hover:text-fg disabled:opacity-50 md:size-7"
    >
      <X className="size-4" aria-hidden />
    </button>
  );
}

/** F-08 Edit: the card collapses to one line while its text is in the composer. */
export function EditingSuggestionChip({ onStop }: { onStop: () => void }) {
  return (
    <div className="mx-4 mb-2 flex items-center gap-2">
      <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft py-1 pr-1 pl-3 text-xs font-medium text-brand-fg">
        <Sparkles className="size-3.5" aria-hidden /> Editing suggestion
        <button
          type="button"
          aria-label="Stop editing the suggestion"
          onClick={onStop}
          className="grid size-5 place-items-center rounded-full hover:bg-white/10"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </span>
    </div>
  );
}

/** Escalated in Auto (F-09): above the card, "AI didn't reply: {reason}". */
export function EscalationBanner({ message }: { message: string }) {
  return (
    <div role="status" className="mx-4 mb-2 flex items-center gap-2 rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning">
      <AlertTriangle className="size-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}
