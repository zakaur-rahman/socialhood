"use client";

import { LoaderCircle, SendHorizontal } from "lucide-react";
import { useCallback, useLayoutEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import { REQUEST_MAX_CHARS } from "@/lib/agent/format";
import { cn } from "@/lib/utils";

const MIN_HEIGHT = 40;
const MAX_HEIGHT = 160;
/** The counter shows from here, so the limit never comes as a surprise. */
const COUNT_FROM = REQUEST_MAX_CHARS - 200;

const count = new Intl.NumberFormat("en-US");

/**
 * The question box (FR-AGT-01): Enter asks, Shift+Enter adds a line. Plain language in English,
 * Hindi or Hinglish; up to 2,000 characters.
 */
export function AskComposer({
  id,
  value,
  onChange,
  onSubmit,
  sending,
  blockedReason,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string) => void;
  sending: boolean;
  /** Why asking is paused (a run is still working, credits are used up), shown under the box. */
  blockedReason?: string | null;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const text = value.trim();
  const canSend = text.length > 0 && text.length <= REQUEST_MAX_CHARS && !sending && !blockedReason;

  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, el.scrollHeight))}px`;
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

  return (
    <form onSubmit={submit} className="shrink-0 border-t border-line bg-panel px-4 py-3">
      <div className="flex items-end gap-2">
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
          className="max-h-40 min-h-10 flex-1 resize-none rounded-[20px] border border-line bg-field px-4 py-2 text-sm leading-relaxed outline-none focus:bg-raised"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Ask"
          className={cn(
            "grid size-10 shrink-0 place-items-center rounded-full",
            canSend ? "bg-brand-gradient text-white" : "bg-raised text-fg-disabled",
          )}
        >
          {sending ? (
            <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden />
          ) : (
            <SendHorizontal className="size-4" aria-hidden />
          )}
        </button>
      </div>
      {blockedReason ? (
        <p id={`${id}-blocked`} className="mt-2 text-xs text-fg-secondary">
          {blockedReason}
        </p>
      ) : value.length >= COUNT_FROM ? (
        <p className="mt-2 text-right text-xs text-fg-secondary tabular-nums">
          {count.format(value.length)} / {count.format(REQUEST_MAX_CHARS)}
        </p>
      ) : null}
    </form>
  );
}
