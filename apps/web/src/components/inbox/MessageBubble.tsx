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

  const bubbleClass = cn(
    "relative max-w-full rounded-2xl px-3 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap",
    !outbound && "rounded-bl-md border border-line-subtle bg-field text-fg shadow-sm",
    outbound && "rounded-br-md",
    outbound && !failed && !pending && !nativeApp && "bg-brand-gradient text-white",
    outbound && nativeApp && !failed && !pending && "bg-raised text-fg",
    pending && "bg-brand/60 text-white opacity-80",
    failed && "bg-danger-fill text-white",
  );
  const metaClass = outbound && !nativeApp ? "text-white/75" : "text-fg-secondary";

  let label: { icon?: LucideIcon; text: string } | null = null;
  if (outbound && message.source === "ai_auto") label = { icon: Sparkles, text: "Sent by AI" };
  else if (outbound && message.source === "automation") {
    label = { icon: Zap, text: message.automation ? `Automation · ${message.automation.name}` : "Automation" };
  } else if (nativeApp) label = { text: `Sent from ${platformName}` };

  const statusInfo = outbound && status ? STATUS[status] : undefined;
  const reactions = message.reactions ?? [];

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
          {label ? (
            <p className={cn("mb-1 flex items-center gap-1 text-xs font-medium", nativeApp ? "text-fg-secondary" : "text-white/90")}>
              {label.icon ? <label.icon className="size-3" aria-hidden /> : null}
              {label.text}
            </p>
          ) : null}
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
          ) : message.kind === "unsupported" ? (
            <p>
              Unsupported message.{" "}
              <a
                href={platform === "instagram" ? "https://www.instagram.com/direct/inbox/" : "https://web.whatsapp.com/"}
                target="_blank"
                rel="noreferrer"
                className={cn("inline-flex items-center gap-1 underline-offset-4 hover:underline", outbound ? "" : "text-brand-fg")}
              >
                View in {platformName} <ExternalLink className="size-3" aria-hidden />
              </a>
            </p>
          ) : message.kind === "location" && !message.text ? (
            <p>Shared a location</p>
          ) : message.text ? (
            <p>{message.text}</p>
          ) : null}
          <p className={cn("mt-1 flex items-center justify-end gap-1 text-xs tabular-nums", metaClass)}>
            {message.edited_at && !unsent ? <span>Edited ·</span> : null}
            <time dateTime={message.occurred_at}>{formatTime(message.occurred_at, timeZone)}</time>
            {statusInfo ? (
              <span role="img" aria-label={statusInfo.label} title={statusInfo.label} className="inline-flex">
                <statusInfo.icon className={cn("size-3.5", statusInfo.className)} aria-hidden />
              </span>
            ) : null}
          </p>
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
