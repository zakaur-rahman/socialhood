"use client";

import type { SavedReply } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const SAVED_REPLY_LIST_ID = "saved-reply-options";

export function savedReplyOptionId(reply: SavedReply): string {
  return `saved-reply-${reply.id}`;
}

/**
 * GR-21: the composer's "/" picker. A list of saved replies above the box, as a listbox the
 * composer drives with the arrow keys (the textarea keeps focus and points at the active option
 * with aria-activedescendant). Clicking an option picks it; mouse down is prevented so the box
 * keeps its caret.
 */
export function SavedReplyPicker({
  replies,
  activeIndex,
  busy,
  onPick,
}: {
  replies: readonly SavedReply[];
  activeIndex: number;
  /** A reply is being filled in. */
  busy: boolean;
  onPick: (reply: SavedReply) => void;
}) {
  return (
    <div
      id={SAVED_REPLY_LIST_ID}
      role="listbox"
      aria-label="Saved replies"
      aria-busy={busy}
      className="absolute inset-x-0 bottom-full z-20 mb-2 max-h-64 overflow-y-auto rounded-lg bg-popover p-1 text-popover-foreground shadow-floating ring-1 ring-line"
    >
      {replies.map((reply, index) => (
        <div
          key={reply.id}
          id={savedReplyOptionId(reply)}
          role="option"
          aria-selected={index === activeIndex}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onPick(reply)}
          className={cn(
            "flex cursor-default flex-col gap-0.5 rounded-md px-2.5 py-1.5 text-sm pointer-coarse:min-h-11",
            index === activeIndex ? "bg-hover" : "hover:bg-hover",
          )}
        >
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="shrink-0 font-medium text-brand-fg">/{reply.shortcut}</span>
            <span className="truncate font-medium">{reply.title}</span>
          </span>
          <span className="line-clamp-2 text-xs text-fg-secondary">{reply.body}</span>
        </div>
      ))}
    </div>
  );
}
