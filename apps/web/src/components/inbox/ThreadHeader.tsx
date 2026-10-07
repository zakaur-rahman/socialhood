"use client";

import { ArrowLeft, Clock, EllipsisVertical, PanelRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Button } from "@/components/ui/button";
import { DisabledReason } from "@/components/ui/disabled-reason";
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

/** Platform colours are for glyphs and fills, never text (DESIGN_SYSTEM §1.6). */
const PLATFORM_GLYPH = { instagram: "text-instagram", whatsapp: "text-whatsapp" } as const;

const NEEDS_YOU_CHIP = cn("shrink-0 rounded-full py-0.5 text-xs font-medium", TONE_CLASS.danger);

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
 *
 * The header follows the thread pane's width, not the viewport's (a container query: the pane is
 * 370 px on a tablet and 395 px at 1280 px with the panel open). The name keeps at least 80 px and
 * the other items move first (UI-ISS-019): below 672 px "Needs you" goes to the handle line
 * (without its reason, which screen readers still hear); below 576 px the window chip joins it,
 * without "Window:", and the AI menu shows as its icon; below 352 px the panel toggle moves into
 * More. From 672 px it is C-063's layout.
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
  const reason = conversation.needs_human_reason ? `: ${ESCALATION_LABEL[conversation.needs_human_reason]}` : "";
  // The panel toggle is hidden on the narrowest phones (CSS); More offers it then.
  const detailsRef = useRef<HTMLButtonElement>(null);
  const [detailsInMenu, setDetailsInMenu] = useState(false);

  return (
    <header className="@container/header shrink-0 border-b border-line bg-panel">
      <div className="@container/row flex h-16 items-center gap-2 px-4 @md/header:gap-3">
        {backHref ? (
          <Button asChild variant="ghost" size="icon-lg" className="-ml-2 text-fg-secondary">
            <Link href={backHref} aria-label="Back to conversations">
              <ArrowLeft className="size-5" aria-hidden />
            </Link>
          </Button>
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
            <h2 className="min-w-20 truncate text-sm font-semibold @xl/header:min-w-0">{name}</h2>
            <ReplyWindowChip window={conversation.reply_window} now={now} className="hidden @xl/header:inline-flex" />
            {conversation.needs_human ? (
              <span className={cn(NEEDS_YOU_CHIP, "hidden px-2 @2xl/header:inline-flex")}>Needs you{reason}</span>
            ) : null}
          </div>
          <div className="flex min-w-0 items-center gap-1">
            {conversation.needs_human ? (
              <span className={cn(NEEDS_YOU_CHIP, "px-1.5 @2xl/header:hidden")}>
                Needs you<span className="sr-only">{reason}</span>
              </span>
            ) : null}
            <ReplyWindowChip
              window={conversation.reply_window}
              now={now}
              compact
              className="min-w-0 shrink truncate @xl/header:hidden"
            />
            <p className="min-w-0 flex-1 truncate text-xs text-fg-secondary" data-testid="thread-identity">
              {conversation.contact.username ? `@${conversation.contact.username} · ` : ""}
              <span>
                <PlatformGlyph
                  platform={conversation.platform}
                  className={cn("mr-1 inline-block size-3 align-text-bottom", PLATFORM_GLYPH[conversation.platform])}
                />
                {platform}
              </span>
              {account ? ` · ${account}` : ""}
            </p>
          </div>
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
          {/* Disabled, it says why (DisabledReason): to keyboard, touch and screen reader users too. */}
          <DisabledReason
            reason={canSchedule ? null : "Scheduling needs an open reply window"}
            side="bottom"
            className="hidden md:inline-flex"
          >
            <Button
              variant="ghost"
              size="icon-lg"
              aria-label="Schedule a message"
              title={canSchedule ? "Schedule a message" : undefined}
              disabled={!canSchedule}
              onClick={onSchedule}
            >
              <Clock aria-hidden />
            </Button>
          </DisabledReason>
          <Button
            ref={detailsRef}
            variant="ghost"
            size="icon-lg"
            aria-label="Details"
            title={detailsOpen ? "Hide the customer panel" : "Show the customer panel"}
            aria-pressed={detailsOpen}
            onClick={onToggleDetails}
            className={cn("hidden @xs/row:inline-flex", detailsOpen && "bg-brand-soft text-brand-fg")}
          >
            <PanelRight aria-hidden />
          </Button>
          <DropdownMenu
            onOpenChange={(open) => {
              const toggle = detailsRef.current;
              if (open) setDetailsInMenu(!toggle || getComputedStyle(toggle).display === "none");
            }}
          >
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-lg" aria-label="More actions">
                <EllipsisVertical aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {detailsInMenu ? (
                <>
                  <DropdownMenuItem onSelect={onToggleDetails}>Customer details</DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              ) : null}
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
      </div>
    </header>
  );
}
