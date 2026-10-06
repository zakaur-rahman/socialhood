"use client";

import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useCancelScheduled, useScheduledMessages, useUpdateScheduled } from "@/lib/api/queries";
import type { ScheduledMessage } from "@/lib/api/types";
import { emptyStates, errorMessage } from "@/lib/copy";
import { contactName, TONE_CLASS, type Tone } from "@/lib/inbox/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime, toZonedInputs } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ContactAvatar } from "./ContactAvatar";
import { RowSkeletons } from "./ConversationList";
import { checkSchedule, ScheduleFields, scheduleLimits, type ScheduleValue } from "./ScheduleFields";

const STATUS: Record<ScheduledMessage["status"], { label: string; tone: Tone }> = {
  scheduled: { label: "Scheduled", tone: "brand" },
  sending: { label: "Sending", tone: "brand" },
  sent: { label: "Sent", tone: "neutral" },
  failed: { label: "Failed", tone: "danger" },
  canceled: { label: "Canceled", tone: "neutral" },
  expired: { label: "Expired", tone: "warning" },
};

/** UX-INB-10, FR-SMS-02: scheduled messages across conversations. */
export function ScheduledList({ onOpen, now }: { onOpen: (conversationId: string) => void; now: Date }) {
  const workspace = useCurrentWorkspace();
  const scheduled = useScheduledMessages(workspace.id);
  const cancel = useCancelScheduled(workspace.id);
  // The edit dialog stays mounted and keeps the last message while it closes, so its exit plays.
  const [editing, setEditing] = useState<ScheduledMessage | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  if (scheduled.isPending) return <RowSkeletons count={4} />;
  if (scheduled.isError) return <ErrorState error={scheduled.error} onRetry={() => void scheduled.refetch()} />;
  const items = scheduled.data.pages.flatMap((page) => page.items).filter((s) => s.status !== "canceled");
  if (items.length === 0) return <EmptyState {...emptyStates.scheduled} />;

  return (
    <div
      className="min-h-0 flex-1 overflow-y-auto p-3"
      onScroll={(event) => {
        const el = event.currentTarget;
        if (scheduled.hasNextPage && !scheduled.isFetchingNextPage && el.scrollTop + el.clientHeight >= el.scrollHeight - 300) {
          void scheduled.fetchNextPage();
        }
      }}
    >
      <ul aria-label="Scheduled messages" className="space-y-2">
        {items.map((item) => (
          <li key={item.id}>
            <ScheduledCard
              item={item}
              slug={workspace.slug}
              timeZone={workspace.timezone}
              now={now}
              onOpen={() => onOpen(item.conversation_id)}
              onEdit={() => {
                setEditing(item);
                setEditOpen(true);
              }}
              canceling={cancel.isPending && cancel.variables?.id === item.id}
              onCancel={() =>
                cancel.mutate(item, {
                  onSuccess: () => toast.success("Scheduled message canceled"),
                  onError: (error) => toastError(error),
                })
              }
            />
          </li>
        ))}
      </ul>
      <EditScheduledDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        item={editing}
        timeZone={workspace.timezone}
        now={now}
      />
    </div>
  );
}

export function ScheduledCard({
  item,
  slug,
  timeZone,
  now,
  onOpen,
  onEdit,
  onCancel,
  canceling = false,
}: {
  item: ScheduledMessage;
  slug: string;
  timeZone: string;
  now: Date;
  onOpen?: () => void;
  onEdit: () => void;
  onCancel: () => void;
  canceling?: boolean;
}) {
  const name = contactName(item.contact, item.platform);
  const status = STATUS[item.status];
  const pending = item.status === "scheduled";
  return (
    <article aria-label={`Scheduled message to ${name}`} className="rounded-lg border border-line-subtle bg-field p-3">
      <Link
        href={`/w/${slug}/inbox/${item.conversation_id}` as Route}
        onClick={onOpen ? (event) => { event.preventDefault(); onOpen(); } : undefined}
        className="flex gap-3 rounded-md"
      >
        <ContactAvatar id={item.conversation_id} name={name} pictureUrl={item.contact.profile_picture_url} size={32} />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-sm font-semibold">
            <span className="truncate">{name}</span>
            <PlatformGlyph platform={item.platform} className="size-3.5 shrink-0 text-fg-secondary" />
          </span>
          <span className="mt-0.5 line-clamp-2 text-sm text-fg-secondary">{item.text}</span>
        </span>
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-fg tabular-nums">
          <time dateTime={item.send_at}>{formatDayTime(item.send_at, timeZone, now)}</time>
        </span>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASS[status.tone])}>{status.label}</span>
        {pending ? (
          <span className="ml-auto flex gap-1">
            <Button variant="ghost" size="sm" onClick={onEdit}>
              Edit
            </Button>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="text-danger-fg hover:text-danger-fg" disabled={canceling}>
                  Cancel
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-60 border-line bg-panel shadow-xl">
                <p className="text-sm">Cancel this scheduled message?</p>
                <p className="text-xs text-fg-secondary">It won&apos;t be sent.</p>
                <Button size="sm" className="bg-danger-fill text-white hover:bg-danger-fill/90" onClick={onCancel}>
                  Cancel message
                </Button>
              </PopoverContent>
            </Popover>
          </span>
        ) : null}
      </div>
      {item.error && (item.status === "failed" || item.status === "expired") ? (
        <p className="mt-2 text-xs text-danger-fg">{item.error.message}</p>
      ) : null}
    </article>
  );
}

/**
 * FR-SMS-02: change the text or the time of a pending scheduled message. Opened from a card's
 * Edit, so focus goes back there when it closes (UX-A11Y-02).
 */
function EditScheduledDialog({
  open,
  onOpenChange,
  item,
  timeZone,
  now,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: ScheduledMessage | null;
  timeZone: string;
  now: Date;
}) {
  const returnFocus = useReturnFocus();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-line bg-panel sm:max-w-md" {...returnFocus}>
        {item ? (
          <EditScheduledForm key={item.id} item={item} timeZone={timeZone} now={now} onClose={() => onOpenChange(false)} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/** Inside the dialog's content, so each opening starts from the message as it is. */
function EditScheduledForm({
  item,
  timeZone,
  now,
  onClose,
}: {
  item: ScheduledMessage;
  timeZone: string;
  now: Date;
  onClose: () => void;
}) {
  const workspace = useCurrentWorkspace();
  const update = useUpdateScheduled(workspace.id);
  const [text, setText] = useState(item.text);
  const [when, setWhen] = useState<ScheduleValue>(() => toZonedInputs(new Date(item.send_at), timeZone));
  const [error, setError] = useState<string | null>(null);
  const limits = scheduleLimits(now, null);

  const save = () => {
    const trimmed = text.trim();
    if (!trimmed) return setError("Write a message.");
    const checked = checkSchedule(when, timeZone, limits, now);
    if ("error" in checked) return setError(checked.error);
    setError(null);
    update.mutate(
      { id: item.id, patch: { text: trimmed, send_at: checked.at.toISOString() } },
      {
        onSuccess: () => {
          toast.success("Scheduled message updated");
          onClose();
        },
        onError: (e) => setError(errorMessage(e)),
      },
    );
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit scheduled message</DialogTitle>
        <DialogDescription className="text-fg-secondary">
          To {contactName(item.contact, item.platform)}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-1">
        <Label htmlFor="scheduled-text" className="text-xs text-fg-secondary">
          Message
        </Label>
        <textarea
          id="scheduled-text"
          value={text}
          maxLength={2000}
          rows={4}
          onChange={(event) => setText(event.target.value)}
          className="w-full resize-none rounded-lg border border-line bg-field px-3 py-2 text-sm leading-relaxed focus:bg-raised"
        />
      </div>
      <ScheduleFields idPrefix="edit-scheduled" value={when} onChange={setWhen} timeZone={timeZone} limits={limits} error={error} />
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Keep as is
        </Button>
        <Button className="bg-brand-gradient text-white" disabled={update.isPending} onClick={save}>
          Save
        </Button>
      </DialogFooter>
    </>
  );
}
