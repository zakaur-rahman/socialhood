"use client";

import { CalendarClock, MessageSquareReply, Zap, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { handOff } from "@/lib/agent/handoff";
import { actionPath, workspaceHref } from "@/lib/agent/routes";
import type { ActionCard, ActionKind } from "@/lib/api/types";
import { TRIGGER_LABEL } from "@/lib/automations/format";
import { formatDayTime } from "@/lib/tz";

const KIND: Record<ActionKind, { icon: LucideIcon; title: string; hint: string }> = {
  schedule_message: {
    icon: CalendarClock,
    title: "Scheduled message",
    hint: "Opens the conversation with this message ready to schedule. Nothing is sent until you do.",
  },
  reply_to_comment: {
    icon: MessageSquareReply,
    title: "Comment reply",
    hint: "Opens the comment with this reply ready. Nothing is posted until you send it.",
  },
  automation_draft: {
    icon: Zap,
    title: "Automation draft",
    hint: "Opens these settings for you to check, then edit and activate in the automation editor.",
  },
};

const ACTION_LABEL = { send_message: "Send a message", ai_reply: "Reply with AI" } as const;

function quote(text: string | null | undefined): string | null {
  const trimmed = text?.replace(/\s+/g, " ").trim();
  return trimmed ? `“${trimmed}”` : null;
}

/** The one-line summary of what the card prepared, in plain words. */
export function actionSummary(card: ActionCard, timeZone: string, now: Date): string {
  switch (card.kind) {
    case "schedule_message": {
      const { text, send_at: sendAt, window_closes_at: closesAt } = card.prefill;
      return [
        quote(text),
        sendAt ? `Send ${formatDayTime(sendAt, timeZone, now)}` : "You pick the time",
        closesAt ? `Window closes ${formatDayTime(closesAt, timeZone, now)}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    }
    case "reply_to_comment":
      return [card.prefill.private ? "Private reply (a DM)" : "Public reply", quote(card.prefill.text)]
        .filter(Boolean)
        .join(" · ");
    case "automation_draft": {
      const draft = card.prefill;
      return [
        draft.name,
        draft.trigger ? TRIGGER_LABEL[draft.trigger] : null,
        draft.keywords && draft.keywords.length > 0 ? draft.keywords.join(", ") : null,
        draft.action ? ACTION_LABEL[draft.action] : null,
      ]
        .filter(Boolean)
        .join(" · ");
    }
  }
}

/**
 * FR-AGT-03: a prepared action, one light row: what it is, what it holds, and Open. Open takes
 * the values to the existing screen (the schedule popover, the comment's reply box, the
 * automation editor); the member completes it there, so every existing check applies.
 */
export function ActionCardView({
  card,
  slug,
  timeZone,
  now,
  onOpen,
}: {
  card: ActionCard;
  slug: string;
  timeZone: string;
  now: Date;
  /** Leaving the panel: the caller closes it. */
  onOpen?: () => void;
}) {
  const router = useRouter();
  const kind = KIND[card.kind];
  const Icon = kind.icon;
  const hintId = useId();
  const summary = actionSummary(card, timeZone, now);

  const open = () => {
    handOff(card);
    onOpen?.();
    router.push(workspaceHref(slug, actionPath(card)));
  };

  return (
    <section
      aria-label={kind.title}
      className="flex items-center gap-3 rounded-xl border border-line-subtle bg-hover px-3 py-2.5"
      data-testid={`action-${card.kind}`}
    >
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand-fg" aria-hidden>
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{card.label}</p>
        <p className="line-clamp-2 text-xs break-words text-fg-secondary" data-testid="action-summary">
          {summary}
          {card.note ? ` · ${card.note}` : ""}
        </p>
        <p id={hintId} className="sr-only">
          {kind.hint}
        </p>
      </div>
      <Button
        variant="secondary"
        className="shrink-0 px-3"
        // The visible "Open" starts the name (WCAG 2.5.3), then what it opens.
        aria-label={/^open\b/i.test(card.label) ? card.label : `Open: ${card.label}`}
        aria-describedby={hintId}
        title={kind.hint}
        onClick={open}
      >
        Open
      </Button>
    </section>
  );
}
