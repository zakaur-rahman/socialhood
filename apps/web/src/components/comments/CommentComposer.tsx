"use client";

import { Send } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import {
  authorName,
  byteLength,
  formatCount,
  PRIVATE_REPLY_MAX_BYTES,
  REPLY_MAX_CHARS,
} from "@/lib/comments/format";
import type { Platform, PostComment } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";
import { uuid } from "@/lib/uuid";

/** Messenger's text limit for a private reply on a Page (unverified, GR-29). */
const FACEBOOK_PRIVATE_REPLY_MAX = 2000;

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
  platform = "instagram",
}: {
  kind: ComposerKind;
  comment: PostComment;
  pending: boolean;
  error: string | null;
  onSend: (text: string, idempotencyKey: string) => void;
  onCancel: () => void;
  /** A reply prepared by Ask Amplychat (FR-AGT-03); the member edits and sends it. */
  initialText?: string;
  /** GR-29: the post's platform. A Page counts a private reply in characters (2,000), Instagram in bytes. */
  platform?: Platform;
}) {
  const id = useId();
  const [text, setText] = useState(initialText);
  const last = useRef<{ text: string; key: string } | null>(null);
  const name = authorName(comment);
  const trimmed = text.trim();
  const inBytes = kind === "dm" && platform !== "facebook";
  const size = inBytes ? byteLength(trimmed) : trimmed.length;
  const limit = kind === "dm" ? (platform === "facebook" ? FACEBOOK_PRIVATE_REPLY_MAX : PRIVATE_REPLY_MAX_BYTES) : REPLY_MAX_CHARS;
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
    <CardInset padding="compact" className="mt-2" data-testid={`composer-${kind}`}>
      <Field id={id} invalid={over || undefined} className="gap-2">
        <FieldLabel className="sr-only">{label}</FieldLabel>
        {kind === "dm" ? (
          <FieldDescription className="px-1">
            Sent as a DM to {name}. {PLATFORM_LABEL[platform]} allows one private reply per comment, within 7 days of it.
          </FieldDescription>
        ) : null}
        <Textarea
          autoFocus
          rows={2}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={kind === "dm" ? "Write a DM…" : "Reply publicly…"}
          // The field recipe (DESIGN_SYSTEM §8.2); two lines tall, as with rows={2}, growing to 160 px.
          className="max-h-40 min-h-16 resize-none"
        />
        <FieldError className="px-1">{error}</FieldError>
        <div className="flex items-center justify-between gap-2">
          <FieldDescription className={cn("px-1 tabular-nums", over && "text-danger-fg")}>
            {formatCount(size)} / {formatCount(limit)}
            {inBytes ? " bytes" : ""}
          </FieldDescription>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
            <Button size="sm" disabled={!canSend && !pending} loading={pending} onClick={send}>
              <Send aria-hidden />
              {kind === "dm" ? "Send DM" : "Send reply"}
            </Button>
          </div>
        </div>
      </Field>
    </CardInset>
  );
}
