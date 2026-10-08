"use client";

import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { useCancelScheduled, useScheduledMessages, useUpdateScheduled } from "@/lib/api/queries";
import type { ScheduledMessage } from "@/lib/api/types";
import { emptyStates, errorMessage } from "@/lib/copy";
import { contactName, type Tone } from "@/lib/inbox/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime, toZonedInputs } from "@/lib/tz";
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
        <Badge size="md" className="tabular-nums">
          <time dateTime={item.send_at}>{formatDayTime(item.send_at, timeZone, now)}</time>
        </Badge>
        <Badge size="md" tone={status.tone}>
          {status.label}
        </Badge>
        {pending ? (
          <span className="ml-auto flex gap-1">
            <Button variant="ghost" size="sm" onClick={onEdit}>
              Edit
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive-ghost" size="sm" loading={canceling}>
                  Cancel
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Cancel this scheduled message?</AlertDialogTitle>
                  <AlertDialogDescription>It won&apos;t be sent.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Keep it</AlertDialogCancel>
                  <AlertDialogAction variant="destructive" onClick={onCancel}>
                    Cancel message
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </span>
        ) : null}
      </div>
      {item.error && (item.status === "failed" || item.status === "expired") ? (
        <Alert tone="danger" className="mt-2">
          {item.error.message}
        </Alert>
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
      <DialogContent size="md" {...returnFocus}>
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
        <DialogDescription>To {contactName(item.contact, item.platform)}</DialogDescription>
      </DialogHeader>
      <Field id="scheduled-text" density="compact">
        <FieldLabel>Message</FieldLabel>
        <Textarea
          value={text}
          maxLength={2000}
          onChange={(event) => setText(event.target.value)}
          className="max-h-60 resize-none"
        />
      </Field>
      <ScheduleFields idPrefix="edit-scheduled" value={when} onChange={setWhen} timeZone={timeZone} limits={limits} error={error} />
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Keep as is
        </Button>
        <Button loading={update.isPending} onClick={save}>
          Save
        </Button>
      </DialogFooter>
    </>
  );
}
