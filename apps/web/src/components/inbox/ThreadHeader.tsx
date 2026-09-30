"use client";

import { ArrowLeft, Clock, EllipsisVertical, PanelRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Conversation } from "@/lib/api/types";
import { contactName, ESCALATION_LABEL, PLATFORM_LABEL, platformContactUrl, TONE_CLASS } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

import { ContactAvatar } from "./ContactAvatar";
import { ReplyWindowChip } from "./ReplyWindowChip";

const AI_LABEL = { off: "AI: Off", suggest: "AI: Suggest", auto: "AI: Auto" } as const;

const PLATFORM_TEXT = { instagram: "text-instagram", whatsapp: "text-whatsapp" } as const;

type Props = {
  conversation: Conversation;
  now: Date;
  /** Phones: the back button to the list. */
  backHref?: Route;
  /** The context panel is showing (inline or as a sheet). */
  detailsOpen: boolean;
  onToggleDetails: () => void;
  canSchedule: boolean;
  onSchedule: () => void;
  onArchive: (archived: boolean) => void;
  onMarkUnread: () => void;
  /** The one AI mode control (a compact menu); without it the header shows a read-only chip. */
  aiControl?: ReactNode;
};

/**
 * UX-INB-05, re-arranged (C-063): who (avatar, name, handle, platform and our linked account),
 * the reply-window chip beside the name, then the AI mode menu, scheduling, the context panel
 * toggle and the conversation's other actions.
 */
export function ThreadHeader({
  conversation,
  now,
  backHref,
  detailsOpen,
  onToggleDetails,
  canSchedule,
  onSchedule,
  onArchive,
  onMarkUnread,
  aiControl,
}: Props) {
  const name = contactName(conversation.contact, conversation.platform);
  const platform = PLATFORM_LABEL[conversation.platform];
  const account = conversation.social_account.username
    ? `@${conversation.social_account.username}`
    : conversation.social_account.display_name;
  const paused = conversation.ai.paused_until && new Date(conversation.ai.paused_until) > now;
  const archived = conversation.status === "archived";
  const needsYou = conversation.needs_human ? (
    <span className={cn("hidden shrink-0 rounded-full px-2 py-0.5 text-xs font-medium md:inline-flex", TONE_CLASS.danger)}>
      Needs you{conversation.needs_human_reason ? `: ${ESCALATION_LABEL[conversation.needs_human_reason]}` : ""}
    </span>
  ) : null;

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-panel px-4">
      {backHref ? (
        <Link
          href={backHref}
          aria-label="Back to conversations"
          className="-ml-2 grid size-10 shrink-0 place-items-center rounded-lg text-fg-secondary hover:bg-white/5 hover:text-fg"
        >
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
      ) : null}
      <ContactAvatar
        id={conversation.contact.id}
        name={name}
        pictureUrl={conversation.contact.profile_picture_url}
        platform={conversation.platform}
        size={40}
      />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-sm font-semibold">{name}</h2>
          <ReplyWindowChip window={conversation.reply_window} now={now} />
          {needsYou}
        </div>
        <p className="truncate text-xs text-fg-secondary" data-testid="thread-identity">
          {conversation.contact.username ? `@${conversation.contact.username} · ` : ""}
          <span className={PLATFORM_TEXT[conversation.platform]}>{platform}</span>
          {account ? ` · ${account}` : ""}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {aiControl ?? (
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
              paused ? TONE_CLASS.warning : TONE_CLASS.brand,
            )}
          >
            {paused ? "AI paused" : AI_LABEL[conversation.ai.effective_mode]}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon-lg"
          className="hidden size-9 md:inline-flex"
          aria-label="Schedule a message"
          title={canSchedule ? "Schedule a message" : "Scheduling needs an open reply window"}
          disabled={!canSchedule}
          onClick={onSchedule}
        >
          <Clock aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon-lg"
          aria-label="Details"
          title={detailsOpen ? "Hide the customer panel" : "Show the customer panel"}
          aria-pressed={detailsOpen}
          onClick={onToggleDetails}
          className={cn("size-10 md:size-9", detailsOpen && "bg-brand-soft text-brand-fg")}
        >
          <PanelRight aria-hidden />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-lg" className="size-10 md:size-9" aria-label="More actions">
              <EllipsisVertical aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 border-line bg-panel shadow-xl">
            <DropdownMenuItem onSelect={() => onArchive(!archived)}>{archived ? "Unarchive" : "Archive"}</DropdownMenuItem>
            <DropdownMenuItem onSelect={onMarkUnread}>Mark unread</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a href={platformContactUrl(conversation.platform, conversation.contact)} target="_blank" rel="noreferrer">
                Open in {platform}
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => {
                void navigator.clipboard
                  ?.writeText(window.location.href)
                  .then(() => toast.success("Link copied"), () => toast.error("Couldn't copy the link"));
              }}
            >
              Copy link
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
