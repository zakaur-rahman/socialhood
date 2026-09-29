"use client";

import { ArrowUp, LoaderCircle, Square } from "lucide-react";
import { useCallback, useLayoutEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import { REQUEST_MAX_CHARS } from "@/lib/agent/format";
import { cn } from "@/lib/utils";

/** One line of text (24 px) and its padding; the box grows with the text up to MAX_HEIGHT. */
const MIN_HEIGHT = 36;
const MAX_HEIGHT = 160;
/** The counter shows from here, so the limit never comes as a surprise. */
const COUNT_FROM = REQUEST_MAX_CHARS - 200;

const count = new Intl.NumberFormat("en-US");

/**
 * The textarea's height for its text: scrollHeight measures the content and padding only, so
 * the border (offsetHeight − clientHeight) is added back; without it the text is always a
 * couple of pixels short and the box shows scroll arrows. It scrolls only past MAX_HEIGHT.
 */
export function fitTextarea(el: HTMLTextAreaElement): void {
  el.style.height = "auto";
  el.style.overflowY = "hidden";
  const needed = el.scrollHeight + (el.offsetHeight - el.clientHeight);
  el.style.height = `${Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, needed))}px`;
  el.style.overflowY = needed > MAX_HEIGHT ? "auto" : "hidden";
}

/**
 * The question box (FR-AGT-01): one rounded field with the send button inside. Enter asks,
 * Shift+Enter adds a line; up to 2,000 characters in English, Hindi or Hinglish. While a run
 * works the member can keep typing, and the button stops the run instead.
 */
export function AskComposer({
  id,
  value,
  onChange,
  onSubmit,
  sending,
  working = false,
  onStop,
  stopping = false,
  blockedReason,
  className,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string) => void;
  sending: boolean;
  /** A run in this thread is working: the button is Stop. */
  working?: boolean;
  onStop?: () => void;
  stopping?: boolean;
  /** Why asking is paused (the credits are used up), shown under the box. */
  blockedReason?: string | null;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const text = value.trim();
  const canSend = text.length > 0 && text.length <= REQUEST_MAX_CHARS && !sending && !working && !blockedReason;

  const resize = useCallback(() => {
    if (ref.current) fitTextarea(ref.current);
  }, []);

  useLayoutEffect(() => {
    resize();
  }, [value, resize]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (canSend) onSubmit(text);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  };

  const buttonClass = "grid size-10 shrink-0 place-items-center rounded-full md:size-8";

  return (
    <form onSubmit={submit} className={cn("shrink-0", className)}>
      <div className="flex items-end gap-2 rounded-2xl border border-line bg-field py-1.5 pr-1.5 pl-4 focus-within:border-brand-line focus-within:ring-3 focus-within:ring-ring/40 motion-safe:transition-shadow">
        <label htmlFor={id} className="sr-only">
          Ask Social Hood a question
        </label>
        <textarea
          ref={ref}
          id={id}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about your posts, comments or messages…"
          maxLength={REQUEST_MAX_CHARS}
          aria-describedby={blockedReason ? `${id}-blocked` : undefined}
          className="block max-h-40 min-h-9 flex-1 resize-none overflow-y-hidden bg-transparent py-1.5 text-[15px] leading-6 outline-none"
        />
        {working ? (
          <button
            type="button"
            onClick={onStop}
            disabled={stopping || !onStop}
            aria-label="Stop"
            title="Stop this answer"
            className={cn(buttonClass, "bg-fg text-canvas hover:bg-fg/90 disabled:opacity-60")}
          >
            <Square className="size-3 fill-current" aria-hidden />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Ask"
            className={cn(buttonClass, canSend ? "bg-brand-gradient text-white" : "bg-raised text-fg-disabled")}
          >
            {sending ? (
              <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden />
            ) : (
              <ArrowUp className="size-4" aria-hidden />
            )}
          </button>
        )}
      </div>
      {blockedReason ? (
        <p id={`${id}-blocked`} className="mt-1.5 px-1 text-xs text-warning">
          {blockedReason}
        </p>
      ) : value.length >= COUNT_FROM ? (
        <p className="mt-1.5 px-1 text-right text-xs text-fg-secondary tabular-nums">
          {count.format(value.length)} / {count.format(REQUEST_MAX_CHARS)}
        </p>
      ) : (
        <p className="mt-1.5 hidden text-center text-[11px] text-fg-secondary pointer-fine:block">
          Enter to ask · Shift+Enter for a new line
        </p>
      )}
    </form>
  );
}
