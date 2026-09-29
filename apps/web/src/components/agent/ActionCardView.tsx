"use client";

import { CalendarClock, MessageSquareReply, Zap, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";

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

/**
 * FR-AGT-03: a prepared action. Its button opens the existing screen with the values filled in
 * (the schedule popover, the comment's reply box, the automation editor); the member completes
 * it there, so every existing check applies.
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

  const open = () => {
    handOff(card);
    onOpen?.();
    router.push(workspaceHref(slug, actionPath(card)));
  };

  return (
    <section
      aria-label={kind.title}
      className="space-y-2 rounded-xl border border-brand-line bg-field p-3"
      data-testid={`action-${card.kind}`}
    >
      <p className="flex items-center gap-2 text-xs font-medium text-brand-fg">
        <Icon className="size-4" aria-hidden /> {kind.title}
      </p>
      <ActionDetails card={card} timeZone={timeZone} now={now} />
      {card.note ? <p className="text-xs text-fg-secondary">{card.note}</p> : null}
      <p className="text-xs text-fg-secondary">{kind.hint}</p>
      <Button className="bg-brand-gradient min-h-10 w-full text-white md:min-h-8" onClick={open}>
        {card.label}
      </Button>
    </section>
  );
}

function Quote({ children }: { children: string }) {
  return (
    <p className="line-clamp-4 border-l-2 border-brand-line pl-2 text-sm break-words whitespace-pre-wrap">{children}</p>
  );
}

function ActionDetails({ card, timeZone, now }: { card: ActionCard; timeZone: string; now: Date }) {
  switch (card.kind) {
    case "schedule_message": {
      const { text, send_at: sendAt, window_closes_at: closesAt } = card.prefill;
      return (
        <div className="space-y-1">
          <Quote>{text}</Quote>
          <p className="text-xs text-fg-secondary">
            {sendAt ? `Send ${formatDayTime(sendAt, timeZone, now)}` : "You pick the time"}
            {closesAt ? ` · Window closes ${formatDayTime(closesAt, timeZone, now)}` : ""}
          </p>
        </div>
      );
    }
    case "reply_to_comment":
      return (
        <div className="space-y-1">
          <p className="text-xs text-fg-secondary">{card.prefill.private ? "Private reply (a DM)" : "Public reply"}</p>
          <Quote>{card.prefill.text}</Quote>
        </div>
      );
    case "automation_draft": {
      const draft = card.prefill;
      const message = draft.action === "ai_reply" ? draft.ai_instructions : draft.message_text;
      return (
        <div className="space-y-1 text-sm">
          <p className="font-medium break-words">{draft.name}</p>
          <p className="text-xs text-fg-secondary">
            {[
              draft.trigger ? TRIGGER_LABEL[draft.trigger] : null,
              draft.action ? ACTION_LABEL[draft.action] : null,
            ]
              .filter(Boolean)
              .join(" · ") || "Trigger and action to choose"}
          </p>
          {draft.keywords && draft.keywords.length > 0 ? (
            <ul className="flex flex-wrap gap-1" aria-label="Keywords">
              {draft.keywords.map((keyword) => (
                <li key={keyword} className="rounded-full bg-raised px-2 py-0.5 text-xs">
                  {keyword}
                </li>
              ))}
            </ul>
          ) : null}
          {message ? <Quote>{message}</Quote> : null}
        </div>
      );
    }
  }
}
