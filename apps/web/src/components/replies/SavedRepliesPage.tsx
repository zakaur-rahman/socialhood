"use client";

import { MessageSquareText, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import { useCreateSavedReply, useDeleteSavedReply, useSavedReplies, useUpdateSavedReply } from "@/lib/api/queries";
import type { SavedReply } from "@/lib/api/types";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const VARIABLES = "{first_name}, {name}, {username}, {email}, {phone}";

/**
 * GR-21: Settings → Saved replies. Messages used again and again, each with a shortcut: typing
 * "/" in a reply lists them and Enter inserts one, filled in for the customer. Owners and admins
 * add, change and delete; agents see the list and use it in the inbox.
 */
export function SavedRepliesPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const canManage = workspace.role !== "agent";
  const replies = useSavedReplies(wid);
  const [editing, setEditing] = useState<SavedReply | "new" | null>(null);
  const [removing, setRemoving] = useState<SavedReply | null>(null);
  const remove = useDeleteSavedReply(wid);
  const full = replies.data ? replies.data.items.length >= replies.data.max_items : false;

  let content;
  if (replies.isPending) {
    content = (
      <Card>
        <ul aria-busy="true" aria-label="Loading saved replies" className="divide-y divide-line-subtle">
          {Array.from({ length: 3 }, (_, i) => (
            <li key={i} className="space-y-2 px-4 py-4">
              <Skeleton className="h-4 w-1/4" />
              <Skeleton className="h-3 w-2/3" />
            </li>
          ))}
        </ul>
      </Card>
    );
  } else if (replies.isError) {
    content = <ErrorState error={replies.error} onRetry={() => void replies.refetch()} />;
  } else if (replies.data.items.length === 0) {
    content = (
      <Card>
        <EmptyState
          size="compact"
          icon={<MessageSquareText />}
          title="No saved replies yet"
          body={
            canManage
              ? "Save the answers you give again and again. Type / in a reply to insert one."
              : "An owner or admin can add them. Type / in a reply to insert one."
          }
          action={
            canManage ? (
              <Button size="sm" onClick={() => setEditing("new")}>
                <Plus aria-hidden /> New saved reply
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  } else {
    content = (
      <Card className="overflow-hidden p-0">
        <ul aria-label="Saved replies" className="divide-y divide-line-subtle">
          {replies.data.items.map((reply) => (
            <li key={reply.id} className="space-y-1.5 px-4 py-4" data-testid="saved-reply-row">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-0.5">
                  <p className="flex min-w-0 items-baseline gap-2 text-sm">
                    <span className="shrink-0 font-semibold text-brand-fg">/{reply.shortcut}</span>
                    <span className="truncate font-medium">{reply.title}</span>
                  </p>
                  <p className="whitespace-pre-wrap break-words text-sm text-fg-secondary">{reply.body}</p>
                </div>
                {canManage ? (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(reply)} aria-label={`Edit /${reply.shortcut}`}>
                      <Pencil aria-hidden /> Edit
                    </Button>
                    <Button
                      variant="destructive-ghost"
                      size="sm"
                      onClick={() => setRemoving(reply)}
                      aria-label={`Delete /${reply.shortcut}`}
                    >
                      <Trash2 aria-hidden /> Delete
                    </Button>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </Card>
    );
  }

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Saved replies"
          description="Messages you send often. Type / in a reply to pick one; it is filled in with the customer's name and details."
          actions={
            canManage ? (
              <Button size="lg" onClick={() => setEditing("new")} disabled={full}>
                <Plus aria-hidden /> New <span className="max-[359px]:sr-only">saved reply</span>
              </Button>
            ) : null
          }
        />
      }
    >
      {content}
      {canManage ? (
        <ReplyDialog
          key={editing === null ? "closed" : editing === "new" ? "new" : editing.id}
          wid={wid}
          reply={editing === "new" ? null : editing}
          open={editing !== null}
          onOpenChange={(open) => !open && setEditing(null)}
        />
      ) : null}
      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this saved reply?</AlertDialogTitle>
            <AlertDialogDescription>
              Automations that send it stop at that step, and Activity says why. Messages already sent stay as they are.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!removing) return;
                remove.mutate(removing.id, {
                  onSuccess: () => toast.success("Saved reply deleted"),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Delete reply
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsFrame>
  );
}

/** Add or change a saved reply. The shortcut is typed without the slash. */
function ReplyDialog({
  wid,
  reply,
  open,
  onOpenChange,
}: {
  wid: string;
  reply: SavedReply | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateSavedReply(wid);
  const update = useUpdateSavedReply(wid);
  const [title, setTitle] = useState(reply?.title ?? "");
  const [shortcut, setShortcut] = useState(reply?.shortcut ?? "");
  const [body, setBody] = useState(reply?.body ?? "");
  const [problems, setProblems] = useState<Record<string, string>>({});
  const pending = create.isPending || update.isPending;

  function failed(error: Error) {
    if (error instanceof ApiError && error.errors.length > 0) {
      setProblems(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
    } else if (error instanceof ApiError && error.code === "conflict") {
      setProblems({ shortcut: error.message });
    } else {
      toastError(error);
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setProblems({});
    const values = { title, shortcut: shortcut.replace(/^\//, ""), body };
    const done = {
      onSuccess: () => {
        onOpenChange(false);
        toast.success(reply ? "Saved reply updated" : "Saved reply added");
      },
      onError: failed,
    };
    if (reply) update.mutate({ id: reply.id, body: values }, done);
    else create.mutate(values, done);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>{reply ? "Edit saved reply" : "New saved reply"}</DialogTitle>
            <DialogDescription>
              Use {VARIABLES} or the key of a contact field, like {"{city}"}. {"{first_name|there}"} sets what to write when the
              name is unknown.
            </DialogDescription>
          </DialogHeader>
          <Field invalid={Boolean(problems.title)}>
            <FieldLabel htmlFor="saved-reply-title">Title</FieldLabel>
            <Input
              id="saved-reply-title"
              required
              maxLength={60}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            {problems.title ? <p className="text-sm text-danger-fg">{problems.title}</p> : null}
          </Field>
          <Field invalid={Boolean(problems.shortcut)}>
            <FieldLabel htmlFor="saved-reply-shortcut">Shortcut</FieldLabel>
            <div className="flex items-center gap-2">
              <span aria-hidden className="text-fg-secondary">
                /
              </span>
              <Input
                id="saved-reply-shortcut"
                required
                maxLength={31}
                value={shortcut}
                onChange={(event) => setShortcut(event.target.value)}
                aria-describedby="saved-reply-shortcut-hint"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />
            </div>
            <p id="saved-reply-shortcut-hint" className="text-xs text-fg-secondary">
              Lower case letters, numbers, - and _. Type /{shortcut.replace(/^\//, "") || "price"} in a reply to use it.
            </p>
            {problems.shortcut ? <p className="text-sm text-danger-fg">{problems.shortcut}</p> : null}
          </Field>
          <Field invalid={Boolean(problems.body)}>
            <FieldLabel htmlFor="saved-reply-body">Message</FieldLabel>
            <Textarea
              id="saved-reply-body"
              required
              maxLength={1000}
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
            {problems.body ? <p className="text-sm text-danger-fg">{problems.body}</p> : null}
          </Field>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={pending} disabled={!title.trim() || !shortcut.trim() || !body.trim()}>
              {reply ? "Save changes" : "Add saved reply"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
