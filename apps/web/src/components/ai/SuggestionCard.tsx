"use client";

import { AlertTriangle, CornerDownLeft, RefreshCw, SendHorizontal, Sparkles, X } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DisabledReason } from "@/components/ui/disabled-reason";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Suggestion } from "@/lib/api/types";
import { sourceChips } from "@/lib/ai/format";
import { aiCopy } from "@/lib/copy";
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

/** The bar rises 8 px over `duration-slow` (DESIGN_SYSTEM §7.2: the suggestion bar). */
const BAR =
  "mx-4 mb-2 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2 motion-safe:duration-slow motion-safe:ease-enter";
/** The source and confidence chips are Badges; a long source title truncates inside the chip. */
const META = "max-w-40";

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
      <section aria-label="Suggested reply" className={cn(BAR, "rounded-lg border border-brand-line bg-panel px-3 py-2")} data-state="generating">
        <div className="flex items-center gap-2">
          <Sparkles className="size-3.5 shrink-0 text-brand-fg" aria-hidden />
          <span className="shrink-0 text-xs font-medium text-brand-fg">AI draft:</span>
          <Skeleton className="h-3 flex-1" aria-hidden />
        </div>
        <p role="status" className="mt-1 pl-5.5 text-xs text-fg-secondary">
          {aiCopy.drafting}
        </p>
      </section>
    );
  }
  if (!suggestion.can_answer) {
    return (
      <section aria-label={aiCopy.notInKnowledge} className={BAR} data-state="not_in_knowledge">
        <Alert
          tone="warning"
          variant="outline"
          icon={<AlertTriangle />}
          onDismiss={actions.onDismiss}
          dismissLabel="Dismiss suggestion"
          action={
            <>
              <Button variant="ghost" size="sm" onClick={actions.onWriteReply}>
                Write reply
              </Button>
              {actions.onAddToKnowledge ? (
                <Button size="sm" loading={addingToKnowledge} onClick={actions.onAddToKnowledge}>
                  Add to knowledge
                </Button>
              ) : null}
            </>
          }
        >
          <p>
            <span className="font-medium text-warning">{aiCopy.notInKnowledge}: </span>
            <span>
              {customerName} asked about {suggestion.missing_info?.trim() || "something your knowledge doesn't cover"}.
            </span>
          </p>
        </Alert>
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
    <section aria-label="Suggested reply" className={cn(BAR, "rounded-lg border border-brand-line bg-panel px-3 py-2")} data-state="ready">
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
          <Badge key={source.id} className={META}>
            <span className="truncate">From: {source.title}</span>
          </Badge>
        ))}
        {more > 0 ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge className={META} tabIndex={0}>
                +{more}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>{suggestion.sources.slice(2).map((s) => s.title).join(", ")}</TooltipContent>
          </Tooltip>
        ) : null}
        {suggestion.low_confidence ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge tone="warning" className={META} tabIndex={0}>
                Check this
              </Badge>
            </TooltipTrigger>
            <TooltipContent>The AI isn&apos;t sure about this one</TooltipContent>
          </Tooltip>
        ) : null}
        <span className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          <span className="text-2xs text-fg-secondary tabular-nums">
            {left > 0 ? `${left} ${left === 1 ? "draft" : "drafts"} left` : "No drafts left"}
          </span>
          <DisabledReason reason={left <= 0 ? "No more drafts for this message" : null}>
            <Button variant="ghost" size="sm" disabled={left <= 0} loading={busy} onClick={actions.onRegenerate}>
              <RefreshCw aria-hidden /> Draft again
            </Button>
          </DisabledReason>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="secondary" size="sm" onClick={actions.onEdit}>
                <CornerDownLeft aria-hidden /> Insert
              </Button>
            </TooltipTrigger>
            <TooltipContent>Put the draft in the reply box to edit</TooltipContent>
          </Tooltip>
          <Button size="sm" disabled={!canSend || !text} onClick={actions.onSend}>
            <SendHorizontal aria-hidden /> Send
          </Button>
        </span>
      </div>
    </section>
  );
}

function DismissButton({ onDismiss, disabled }: { onDismiss: () => void; disabled: boolean }) {
  return (
    // 28 px, 40 px on coarse pointers (Button `icon-sm`).
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Dismiss suggestion"
      disabled={disabled}
      onClick={onDismiss}
      className="-my-1 text-fg-secondary"
    >
      <X aria-hidden />
    </Button>
  );
}

/** F-08 Insert: the bar collapses to one line while its text is in the composer. */
export function EditingSuggestionChip({ onStop }: { onStop: () => void }) {
  return (
    <div className="mx-4 mb-2 flex items-center gap-2">
      <Badge tone="brand" size="md" className="pr-1">
        <Sparkles aria-hidden /> Editing suggestion
        <button
          type="button"
          aria-label="Stop editing the suggestion"
          onClick={onStop}
          // The chip's ×: 16 px, with a 40 px hit area on coarse pointers (DESIGN_SYSTEM §8.4).
          className="relative grid size-4 place-items-center rounded-full after:absolute after:-inset-1 hover:bg-pressed pointer-coarse:after:-inset-3"
        >
          <X aria-hidden />
        </button>
      </Badge>
    </div>
  );
}

/** Escalated in Auto (F-09): above the bar, "AI didn't reply: {reason}". */
export function EscalationBanner({ message }: { message: string }) {
  return (
    <Alert tone="warning" icon={<AlertTriangle />} className="mx-4 mb-2 w-auto">
      <p>{message}</p>
    </Alert>
  );
}
