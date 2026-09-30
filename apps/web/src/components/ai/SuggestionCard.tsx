"use client";

import { AlertTriangle, CornerDownLeft, Loader2, RefreshCw, SendHorizontal, Sparkles, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Suggestion } from "@/lib/api/types";
import { sourceChips } from "@/lib/ai/format";
import { aiCopy } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/** Longer drafts start clamped to two lines with "More" (UX-INB-08). */
const LONG_REPLY = 160;

export type SuggestionActions = {
  onSend: () => void;
  /** Insert: the draft goes into the composer to edit (F-08 Edit). */
  onEdit: () => void;
  /** Draft again (F-08 Regenerate). */
  onRegenerate: () => void;
  onDismiss: () => void;
  onWriteReply: () => void;
  /** Admins only: add the missing answer to knowledge (F-08, F-14). */
  onAddToKnowledge?: () => void;
};

const BAR =
  "mx-4 mb-2 rounded-lg border px-3 py-2 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2 motion-safe:duration-[180ms]";
const ACTION = "h-9 rounded-md px-2.5 text-xs font-medium md:h-7";
const META = "max-w-40 truncate rounded px-1.5 text-[11px] leading-[18px]";

/**
 * UX-INB-08 as a slim bar right above the composer (C-063): the one AI draft ("AI draft: …")
 * with Insert, Send, Draft again and Dismiss; while drafting, a shimmer; when the answer isn't in
 * the knowledge, "Not in your knowledge: …" with Add to knowledge. One draft, never a set of
 * quick replies.
 */
export function SuggestionCard({
  suggestion,
  generating,
  customerName,
  canSend,
  busy = false,
  addingToKnowledge = false,
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
  /** Add to knowledge is looking up the question's knowledge gap. */
  addingToKnowledge?: boolean;
  actions: SuggestionActions;
}) {
  if (generating || !suggestion) {
    return (
      <section aria-label="Suggested reply" className={cn(BAR, "border-brand-line bg-panel")} data-state="generating">
        <div className="flex items-center gap-2">
          <Sparkles className="size-3.5 shrink-0 text-brand-fg" aria-hidden />
          <span className="shrink-0 text-xs font-medium text-brand-fg">AI draft:</span>
          <Skeleton className="h-3 flex-1 bg-raised" aria-hidden />
        </div>
        <p role="status" className="mt-1 pl-5.5 text-xs text-fg-secondary">
          {aiCopy.drafting}
        </p>
      </section>
    );
  }
  if (!suggestion.can_answer) {
    return (
      <section aria-label={aiCopy.notInKnowledge} className={cn(BAR, "border-warning/40 bg-panel")} data-state="not_in_knowledge">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
          <p className="min-w-0 flex-1 text-sm">
            <span className="font-medium text-warning">{aiCopy.notInKnowledge}: </span>
            <span>
              {customerName} asked about {suggestion.missing_info?.trim() || "something your knowledge doesn't cover"}.
            </span>
          </p>
          <DismissButton onDismiss={actions.onDismiss} disabled={busy} />
        </div>
        <div className="mt-1.5 flex flex-wrap justify-end gap-1.5">
          <Button variant="ghost" className={ACTION} onClick={actions.onWriteReply}>
            Write reply
          </Button>
          {actions.onAddToKnowledge ? (
            <Button
              className={cn(ACTION, "bg-brand-gradient text-white")}
              disabled={addingToKnowledge}
              onClick={actions.onAddToKnowledge}
            >
              {addingToKnowledge ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Add to knowledge
            </Button>
          ) : null}
        </div>
      </section>
    );
  }
  return <ReadyBar suggestion={suggestion} canSend={canSend} busy={busy} actions={actions} />;
}

function ReadyBar({
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
  const long = text.length > LONG_REPLY || text.includes("\n");
  const { shown, more } = sourceChips(suggestion.sources);
  const left = suggestion.regenerations_left;

  return (
    <section aria-label="Suggested reply" className={cn(BAR, "border-brand-line bg-panel")} data-state="ready">
      <div className="flex items-start gap-2">
        <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-fg" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className={cn("text-sm whitespace-pre-wrap break-words text-fg", long && !expanded && "line-clamp-2")}>
            <span className="font-medium text-brand-fg">AI draft: </span>
            {text}
          </p>
          {long ? (
            <button
              type="button"
              className="text-xs font-medium text-brand-fg hover:underline"
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Less" : "More"}
            </button>
          ) : null}
        </div>
        <DismissButton onDismiss={actions.onDismiss} disabled={busy} />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 pl-5.5">
        {shown.map((source) => (
          <span key={source.id} className={cn(META, TONE_CLASS.neutral)}>
            From: {source.title}
          </span>
        ))}
        {more > 0 ? (
          <span className={cn(META, TONE_CLASS.neutral)} title={suggestion.sources.slice(2).map((s) => s.title).join(", ")}>
            +{more}
          </span>
        ) : null}
        {suggestion.low_confidence ? (
          <span className={cn(META, "font-medium", TONE_CLASS.warning)} title="The AI isn't sure about this one">
            Check this
          </span>
        ) : null}
        <span className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          <span className="text-[11px] text-fg-secondary tabular-nums">
            {left > 0 ? `${left} ${left === 1 ? "draft" : "drafts"} left` : "No drafts left"}
          </span>
          <Button
            variant="ghost"
            className={ACTION}
            disabled={left <= 0 || busy}
            title={left <= 0 ? "No more drafts for this message" : "Write a different draft"}
            onClick={actions.onRegenerate}
          >
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <RefreshCw aria-hidden />} Draft again
          </Button>
          <Button variant="secondary" className={ACTION} title="Put the draft in the reply box to edit" onClick={actions.onEdit}>
            <CornerDownLeft aria-hidden /> Insert
          </Button>
          <Button className={cn(ACTION, "bg-brand-gradient text-white")} disabled={!canSend || !text} onClick={actions.onSend}>
            <SendHorizontal aria-hidden /> Send
          </Button>
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
      className="-my-1 grid size-9 shrink-0 place-items-center rounded-full text-fg-secondary hover:bg-white/5 hover:text-fg disabled:opacity-50 md:size-7"
    >
      <X className="size-4" aria-hidden />
    </button>
  );
}

/** F-08 Insert: the bar collapses to one line while its text is in the composer. */
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

/** Escalated in Auto (F-09): above the bar, "AI didn't reply: {reason}". */
export function EscalationBanner({ message }: { message: string }) {
  return (
    <div role="status" className="mx-4 mb-2 flex items-center gap-2 rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning">
      <AlertTriangle className="size-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}
