"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import {
  useCreateHashtagGroup,
  useDeleteHashtagGroup,
  useHashtagGroups,
  useUpdateHashtagGroup,
} from "@/lib/api/queries/calendar";
import type { HashtagGroup } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { HASHTAG_GROUP_NAME_MAX, MAX_HASHTAGS, parseHashtags } from "@/lib/schedule/format";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

const PREVIEW = 4;

/**
 * UX-SCR-14 hashtag groups (FR-PUB-12): the list (name, count, first hashtags) with create, edit
 * and delete. The editor counts hashtags against the limit of 30. The composer inserts groups.
 */
export function HashtagGroupsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [editing, setEditing] = useState<HashtagGroup | "new" | null>(null);
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        onOpenChange(value);
        if (!value) setEditing(null);
      }}
    >
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{editing === "new" ? "New hashtag group" : editing ? `Edit ${editing.name}` : "Hashtag groups"}</DialogTitle>
          <DialogDescription>Save sets of hashtags to add to a caption or first comment in one click.</DialogDescription>
        </DialogHeader>
        {open ? (
          editing ? (
            <GroupEditor
              key={editing === "new" ? "new" : editing.id}
              group={editing === "new" ? null : editing}
              onDone={() => setEditing(null)}
            />
          ) : (
            <GroupList onNew={() => setEditing("new")} onEdit={setEditing} />
          )
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function GroupList({ onNew, onEdit }: { onNew: () => void; onEdit: (group: HashtagGroup) => void }) {
  const wid = useCurrentWorkspace().id;
  const groups = useHashtagGroups(wid);
  const remove = useDeleteHashtagGroup(wid);
  const [confirming, setConfirming] = useState<string | null>(null);

  if (groups.isPending) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading hashtag groups">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  }
  if (groups.isError) return <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />;

  return (
    <div className="space-y-3">
      {groups.data.length === 0 ? (
        <EmptyState
          className="rounded-xl border border-line bg-field py-6"
          title="No hashtag groups yet"
          body="Group the hashtags you use often, like #handmade #linen #summerstyle."
        />
      ) : (
        <ul className="divide-y divide-line-subtle rounded-xl border border-line bg-field" aria-label="Hashtag groups">
          {groups.data.map((group) => (
            <li key={group.id} className="flex items-center gap-2 px-3 py-2.5">
              {confirming === group.id ? (
                <div className="flex w-full flex-wrap items-center gap-2" role="group" aria-label={`Delete ${group.name}?`}>
                  <span className="min-w-0 flex-1 text-sm">
                    Delete {group.name}? Captions that used it keep their hashtags.
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                    Keep
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={remove.isPending}
                    onClick={() =>
                      remove.mutate(group, {
                        onSuccess: () => {
                          setConfirming(null);
                          toast.success(`${group.name} deleted`);
                        },
                        onError: (error) => toastError(error),
                      })
                    }
                  >
                    Delete group
                  </Button>
                </div>
              ) : (
                <>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-baseline gap-2 text-sm font-medium">
                      <span className="truncate">{group.name}</span>
                      <span className="shrink-0 text-xs font-normal text-fg-secondary tabular-nums">
                        {group.hashtags.length} {group.hashtags.length === 1 ? "hashtag" : "hashtags"}
                      </span>
                    </p>
                    <p className="truncate text-xs text-fg-secondary">
                      {group.hashtags
                        .slice(0, PREVIEW)
                        .map((tag) => `#${tag}`)
                        .join(" ")}
                      {group.hashtags.length > PREVIEW ? " …" : ""}
                    </p>
                  </div>
                  <Button variant="ghost" size="icon-sm" aria-label={`Edit ${group.name}`} onClick={() => onEdit(group)}>
                    <Pencil aria-hidden />
                  </Button>
                  <Button
                    variant="destructive-ghost"
                    size="icon-sm"
                    aria-label={`Delete ${group.name}`}
                    onClick={() => setConfirming(group.id)}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <Button onClick={onNew}>
        <Plus aria-hidden /> New group
      </Button>
    </div>
  );
}

function GroupEditor({ group, onDone }: { group: HashtagGroup | null; onDone: () => void }) {
  const wid = useCurrentWorkspace().id;
  const create = useCreateHashtagGroup(wid);
  const update = useUpdateHashtagGroup(wid);
  const [name, setName] = useState(group?.name ?? "");
  const [text, setText] = useState(group ? group.hashtags.map((tag) => `#${tag}`).join(" ") : "");
  const [errors, setErrors] = useState<{ name?: string; hashtags?: string; form?: string }>({});
  const { tags, invalid } = parseHashtags(text);
  const over = tags.length > MAX_HASHTAGS;
  const pending = create.isPending || update.isPending;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Name the group.";
    if (tags.length === 0) next.hashtags = "Add at least one hashtag.";
    else if (invalid.length > 0) next.hashtags = `Use letters, numbers and underscores only: ${invalid.join(" ")}`;
    else if (over) next.hashtags = `Use at most ${MAX_HASHTAGS} hashtags.`;
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    const onError = (error: Error) => {
      if (error instanceof ApiError && error.errors.length > 0) {
        setErrors({
          name: error.errors.find((e) => e.field === "name")?.message,
          hashtags: error.errors.find((e) => e.field.startsWith("hashtags"))?.message,
          form: error.errors.every((e) => e.field !== "name" && !e.field.startsWith("hashtags")) ? errorMessage(error) : undefined,
        });
      } else setErrors({ form: errorMessage(error) });
    };
    const onSuccess = (saved: HashtagGroup) => {
      toast.success(group ? `${saved.name} saved` : `${saved.name} created`);
      onDone();
    };
    const body = { name: name.trim(), hashtags: tags };
    if (group) update.mutate({ id: group.id, patch: body }, { onSuccess, onError });
    else create.mutate(body, { onSuccess, onError });
  };

  return (
    <form onSubmit={submit} className="grid gap-4" noValidate>
      <div className="space-y-1">
        <Label htmlFor="hashtag-group-name" className="text-xs text-fg-secondary">
          Name
        </Label>
        <Input
          id="hashtag-group-name"
          size="lg"
          value={name}
          maxLength={HASHTAG_GROUP_NAME_MAX}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? "hashtag-group-name-error" : undefined}
          onChange={(event) => setName(event.target.value)}
        />
        {errors.name ? (
          <p id="hashtag-group-name-error" className="text-xs text-danger-fg">
            {errors.name}
          </p>
        ) : null}
      </div>
      <div className="space-y-1">
        <div className="flex items-baseline justify-between">
          <Label htmlFor="hashtag-group-tags" className="text-xs text-fg-secondary">
            Hashtags
          </Label>
          <span
            data-testid="hashtag-count"
            aria-live="polite"
            className={cn("text-xs tabular-nums", over ? "text-danger-fg" : "text-fg-secondary")}
          >
            {tags.length} of {MAX_HASHTAGS} hashtags
          </span>
        </div>
        <Textarea
          id="hashtag-group-tags"
          value={text}
          rows={5}
          aria-invalid={Boolean(errors.hashtags) || over}
          aria-describedby="hashtag-group-tags-help"
          onChange={(event) => setText(event.target.value)}
          className="max-h-60 min-h-32 resize-none"
        />
        <p id="hashtag-group-tags-help" className="text-xs text-fg-secondary">
          Separate them with spaces, commas or new lines. The # is optional.
        </p>
        {errors.hashtags ? <p className="text-xs text-danger-fg">{errors.hashtags}</p> : null}
      </div>
      {errors.form ? (
        <p role="alert" className="text-xs text-danger-fg">
          {errors.form}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          {group ? "Save group" : "Create group"}
        </Button>
      </div>
    </form>
  );
}
