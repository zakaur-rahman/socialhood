"use client";

import { Send } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  authorName,
  byteLength,
  formatCount,
  PRIVATE_REPLY_MAX_BYTES,
  REPLY_MAX_CHARS,
} from "@/lib/comments/format";
import type { PostComment } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { uuid } from "@/lib/uuid";

export type ComposerKind = "reply" | "dm";

/**
 * The inline composer under a comment (UX-SCR-05): a public reply, or the one private reply (a DM).
 * Enter sends, Shift+Enter adds a line, Esc cancels. A retry of the same text reuses its
 * Idempotency-Key, so a dropped answer never posts twice (TR-API-05).
 */
export function CommentComposer({
  kind,
  comment,
  pending,
  error,
  onSend,
  onCancel,
  initialText = "",
}: {
  kind: ComposerKind;
  comment: PostComment;
  pending: boolean;
  error: string | null;
  onSend: (text: string, idempotencyKey: string) => void;
  onCancel: () => void;
  /** A reply prepared by Ask Social Hood (FR-AGT-03); the member edits and sends it. */
  initialText?: string;
}) {
  const id = useId();
  const [text, setText] = useState(initialText);
  const last = useRef<{ text: string; key: string } | null>(null);
  const name = authorName(comment);
  const trimmed = text.trim();
  const size = kind === "dm" ? byteLength(trimmed) : trimmed.length;
  const limit = kind === "dm" ? PRIVATE_REPLY_MAX_BYTES : REPLY_MAX_CHARS;
  const over = size > limit;
  const canSend = trimmed.length > 0 && !over && !pending;

  const send = () => {
    if (!canSend) return;
    const key = last.current?.text === trimmed ? last.current.key : uuid();
    last.current = { text: trimmed, key };
    onSend(trimmed, key);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    } else if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  };

  const label = kind === "dm" ? `Private reply to ${name}` : `Public reply to ${name}`;
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-line bg-field p-2" data-testid={`composer-${kind}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      {kind === "dm" ? (
        <p id={`${id}-hint`} className="px-1 text-xs text-fg-secondary">
          Sent as a DM to {name}. Instagram allows one private reply per comment, within 7 days of it.
        </p>
      ) : null}
      <Textarea
        id={id}
        autoFocus
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={kind === "dm" ? "Write a DM…" : "Reply publicly…"}
        aria-describedby={kind === "dm" ? `${id}-hint ${id}-count` : `${id}-count`}
        aria-invalid={over || undefined}
        // The field recipe (DESIGN_SYSTEM §8.2); two lines tall, as with rows={2}, growing to 160 px.
        className="max-h-40 min-h-16 resize-none"
      />
      {error ? (
        <p role="alert" className="px-1 text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-2">
        <span id={`${id}-count`} className={cn("px-1 text-xs tabular-nums", over ? "text-danger-fg" : "text-fg-secondary")}>
          {formatCount(size)} / {formatCount(limit)}
          {kind === "dm" ? " bytes" : ""}
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" disabled={!canSend} onClick={send}>
            {pending ? <Spinner size="sm" /> : <Send aria-hidden />}
            {kind === "dm" ? "Send DM" : "Send reply"}
          </Button>
        </div>
      </div>
    </div>
  );
}
