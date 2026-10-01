"use client";

import {
  AlertCircle,
  Check,
  CheckCheck,
  Clock,
  ExternalLink,
  Loader2,
  Sparkles,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { Message, MessageStatus, Platform } from "@/lib/api/types";
import type { SendFailure } from "@/lib/copy";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { formatTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { AttachmentView } from "./AttachmentView";
import { ContactAvatar } from "./ContactAvatar";
import { SystemNote } from "./DateSeparator";

const STATUS: Partial<Record<MessageStatus, { icon: LucideIcon; label: string; className?: string }>> = {
  queued: { icon: Clock, label: "Queued" },
  sending: { icon: Loader2, label: "Sending", className: "animate-spin" },
  sent: { icon: Check, label: "Sent" },
  delivered: { icon: CheckCheck, label: "Delivered" },
  read: { icon: CheckCheck, label: "Read", className: "text-brand-fg" },
  failed: { icon: AlertCircle, label: "Failed" },
};

export type BubbleContact = { id: string; name: string; pictureUrl?: string | null };

type Props = {
  message: Message;
  platform: Platform;
  timeZone: string;
  contact: BubbleContact;
  /** Last bubble of a same-side group within 5 minutes: shows the customer's avatar. */
  groupEnd: boolean;
  /** Arrived live (not history): fades in and rises 4 px (§4.2 motion). */
  live?: boolean;
  /** For a failed outbound bubble: the reason and what the user can do. */
  failure?: SendFailure | null;
  onRetry?: () => void;
  onDiscard?: () => void;
  onChooseTemplate?: () => void;
  reconnectHref?: Route;
  /** An AI auto reply's "why" button, in the "Sent by AI" label row (F-09). */
  aiInfo?: ReactNode;
  /** Under the bubble: the analysis chips of an analysed customer message (FR-AI-02). */
  below?: ReactNode;
};

/** UX-INB-06: one message, in the variant its direction, source and status call for. */
export function MessageBubble({
  message,
  platform,
  timeZone,
  contact,
  groupEnd,
  live = false,
  failure,
  onRetry,
  onDiscard,
  onChooseTemplate,
  reconnectHref,
  aiInfo,
  below,
}: Props) {
  if (message.direction === "system" || message.kind === "system") {
    return <SystemNote>{message.text ?? "Conversation updated"}</SystemNote>;
  }
  const unsent = Boolean(message.deleted_at);
  const outbound = message.direction === "outbound";
  const status = message.status ?? null;
  const failed = outbound && status === "failed";
  const pending = outbound && (status === "queued" || status === "sending");
  const nativeApp = outbound && message.source === "native_app";
  const platformName = PLATFORM_LABEL[platform];
  // Stickers stand on their own, without a bubble; Instagram's heart is stored as its emoji.
  const sticker = message.kind === "sticker" && !failed && !unsent;
  const heart = sticker && message.attachments.length === 0 && Boolean(message.text);

  const bubbleClass = cn(
    "relative max-w-full rounded-2xl px-3 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap",
    sticker && "px-0 py-0",
    !outbound && !sticker && "rounded-bl-md border border-line-subtle bg-field text-fg shadow-sm",
    outbound && "rounded-br-md",
    outbound && !failed && !pending && !nativeApp && !sticker && "bg-brand-gradient text-white",
    outbound && nativeApp && !failed && !pending && !sticker && "bg-raised text-fg",
    pending && !sticker && "bg-brand/60 text-white",
    pending && "opacity-80",
    failed && "bg-danger-fill text-white",
  );
  // On a coloured bubble, labels are on-brand at full strength: white/75 was 3.46:1 at the gradient's light end.
  const metaClass = outbound && !nativeApp && !sticker ? "text-on-brand" : "text-fg-secondary";

  // Written by the AI (an auto reply) or an automation: "AI Assisted" under the bubble (C-063).
  const assisted =
    outbound && message.source === "ai_auto"
      ? "Sent by AI: an auto reply"
      : outbound && message.source === "automation"
        ? message.automation
          ? `Sent by an automation: ${message.automation.name}`
          : "Sent by an automation"
        : null;
  const label = nativeApp ? `Sent from ${platformName}` : null;

  const statusInfo = outbound && status ? STATUS[status] : undefined;
  const reactions = message.reactions ?? [];
  const quickReplies = outbound && !unsent ? (message.quick_replies ?? []) : [];
  // White chips on the gradient, failed and sending fills; neutral ones on a native-app bubble.
  const tinted = !nativeApp || failed || pending;

  return (
    <div
      className={cn(
        "flex items-end gap-2",
        outbound ? "justify-end" : "justify-start",
        live && "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-150",
      )}
      data-direction={message.direction}
      data-status={status ?? undefined}
      data-message-id={message.id}
    >
      {!outbound ? (
        <span className="w-6 shrink-0">
          {groupEnd ? <ContactAvatar id={contact.id} name={contact.name} pictureUrl={contact.pictureUrl} size={24} /> : null}
        </span>
      ) : null}
      <div className={cn("flex max-w-[85%] flex-col md:max-w-[70%]", outbound ? "items-end" : "items-start")}>
        <div className={cn(bubbleClass, reactions.length > 0 && "mb-3")} data-variant={variantName(message)}>
          {label ? <p className="mb-1 text-[11px] font-medium text-fg-secondary">{label}</p> : null}
          {message.kind === "template" && message.template ? (
            <p className={cn("mb-1 text-xs font-medium", metaClass)}>Template · {message.template.name}</p>
          ) : null}
          {message.attachments.length > 0 ? (
            <div className="mb-1 flex flex-col gap-1.5">
              {message.attachments.map((attachment) => (
                <AttachmentView key={attachment.id} attachment={attachment} kind={message.kind} outbound={outbound && !nativeApp} />
              ))}
            </div>
          ) : null}
          {unsent ? (
            <p className="italic text-fg-secondary">Message unsent</p>
          ) : heart ? (
            <p className="text-5xl leading-none" role="img" aria-label="Heart sticker">
              {message.text}
            </p>
          ) : message.kind === "unsupported" ? (
            <div
              className={cn(
                "flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-lg border px-3 py-2 text-xs",
                outbound && !nativeApp ? "border-white/30" : "border-line bg-canvas/40",
              )}
              data-testid="unsupported-card"
            >
              <span className={outbound && !nativeApp ? "text-on-brand" : "text-fg-secondary"}>Unsupported message format</span>
              <a
                href={platform === "instagram" ? "https://www.instagram.com/direct/inbox/" : "https://web.whatsapp.com/"}
                target="_blank"
                rel="noreferrer"
                className={cn(
                  "inline-flex items-center gap-1 font-medium underline-offset-4 hover:underline",
                  outbound && !nativeApp ? "" : "text-brand-fg",
                )}
              >
                View in {platformName} <ExternalLink className="size-3" aria-hidden />
              </a>
            </div>
          ) : message.kind === "location" && !message.text ? (
            <p>Shared a location</p>
          ) : message.text ? (
            <p>{message.text}</p>
          ) : null}
          {quickReplies.length > 0 ? (
            // Tap first's button (FR-AUT-21): shown as it was offered; the customer taps it in Instagram.
            <ul aria-label="Quick replies" className="mt-2 flex flex-wrap gap-1.5 whitespace-normal">
              {quickReplies.map((reply, index) => (
                <li
                  key={`${reply.title}-${index}`}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 text-xs font-medium",
                    tinted ? "border-white/60 text-white" : "border-line-strong text-fg",
                  )}
                >
                  {reply.title}
                </li>
              ))}
            </ul>
          ) : null}
          {reactions.length > 0 ? (
            <span
              className={cn(
                "absolute -bottom-3 flex gap-0.5 rounded-full border border-line bg-raised px-1.5 py-0.5 text-xs",
                outbound ? "right-2" : "left-2",
              )}
              aria-label={`Reactions: ${reactions.map((r) => r.emoji).join(" ")}`}
            >
              {reactions.map((reaction, i) => (
                <span key={`${reaction.emoji}-${i}`} aria-hidden>
                  {reaction.emoji}
                </span>
              ))}
            </span>
          ) : null}
        </div>
        {/* Under the bubble (C-063): time, delivery ticks, and who wrote an AI or automation message. */}
        <p className="mt-1 flex items-center gap-1 px-1 text-[11px] text-fg-secondary tabular-nums" data-testid="message-meta">
          {message.edited_at && !unsent ? <span>Edited ·</span> : null}
          <time dateTime={message.occurred_at}>{formatTime(message.occurred_at, timeZone)}</time>
          {statusInfo ? (
            <span role="img" aria-label={statusInfo.label} title={statusInfo.label} className="inline-flex">
              <statusInfo.icon className={cn("size-3.5", statusInfo.className)} aria-hidden />
            </span>
          ) : null}
          {assisted ? (
            <span className="ml-1 inline-flex items-center gap-0.5 font-medium text-brand-fg" title={assisted}>
              {message.source === "automation" ? (
                <Zap className="size-3" aria-hidden />
              ) : (
                <Sparkles className="size-3" aria-hidden />
              )}
              <span>AI Assisted</span>
              <span className="sr-only"> ({assisted})</span>
            </span>
          ) : null}
          {message.source === "ai_auto" && aiInfo ? aiInfo : null}
        </p>
        {failed && failure ? (
          <div className="mt-1 flex max-w-full flex-col items-end gap-1" role="alert">
            <p className="text-right text-xs text-danger-fg">{failure.message}</p>
            <div className="flex flex-wrap justify-end gap-1">
              {failure.retry && onRetry ? (
                <Button variant="ghost" size="xs" onClick={onRetry}>
                  Retry
                </Button>
              ) : null}
              {failure.chooseTemplate && onChooseTemplate ? (
                <Button variant="ghost" size="xs" onClick={onChooseTemplate}>
                  Choose template
                </Button>
              ) : null}
              {failure.reconnect && reconnectHref ? (
                <Button variant="ghost" size="xs" asChild>
                  <Link href={reconnectHref}>Reconnect</Link>
                </Button>
              ) : null}
              {message.text ? (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() =>
                    void navigator.clipboard
                      ?.writeText(message.text ?? "")
                      .then(() => toast.success("Text copied"), () => toast.error("Couldn't copy the text"))
                  }
                >
                  Copy text
                </Button>
              ) : null}
              {onDiscard ? (
                <Button variant="ghost" size="xs" onClick={onDiscard}>
                  Discard
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
        {below}
      </div>
    </div>
  );
}

function variantName(message: Message): string {
  if (message.direction === "inbound") return "customer";
  if (message.status === "failed") return "failed";
  if (message.status === "queued" || message.status === "sending") return "sending";
  if (message.source === "native_app") return "native_app";
  if (message.source === "ai_auto") return "ai_auto";
  if (message.source === "automation") return "automation";
  return "human";
}
