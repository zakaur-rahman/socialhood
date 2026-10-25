"use client";

import { Bookmark, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import { useContactSegments, useCreateSegment, useDeleteSegment } from "@/lib/api/queries";
import type { ContactSegment } from "@/lib/api/types";
import { filtersToSpec, hasAnyFilter, sameFilters, specToFilters, type ContactFilters } from "@/lib/contacts/filters";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

/**
 * Saved segments (GR-17): a row of named filters above the list. Choosing one applies its filters;
 * the one that matches the current filters shows as pressed. Owners and admins save the current
 * filters under a name and delete segments (the API refuses agents).
 */
export function SegmentBar({ filters, onApply }: { filters: ContactFilters; onApply: (next: ContactFilters, segment: ContactSegment | null) => void }) {
  const { id: wid, role } = useCurrentWorkspace();
  const admin = role !== "agent";
  const segments = useContactSegments(wid).data ?? [];
  const remove = useDeleteSegment(wid);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<ContactSegment | null>(null);
  const current = segments.find((segment) => sameFilters(filters, specToFilters(segment.filter)));
  const canSave = admin && hasAnyFilter(filters) && !current;

  if (segments.length === 0 && !canSave) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Segments">
      {segments.map((segment) => {
        const active = current?.id === segment.id;
        return (
          <span
            key={segment.id}
            className={cn(
              "inline-flex items-center rounded-full border text-sm",
              active ? "border-brand-line bg-brand-soft text-brand-fg" : "border-line bg-hover text-fg",
            )}
          >
            <button
              type="button"
              aria-pressed={active}
              className={cn("min-h-8 rounded-full py-1 pl-3 text-left pointer-coarse:min-h-10", admin ? "pr-1.5" : "pr-3")}
              onClick={() => onApply(active ? specToFilters({}) : specToFilters(segment.filter), active ? null : segment)}
            >
              {segment.name}
            </button>
            {admin ? (
              <button
                type="button"
                aria-label={`Delete the ${segment.name} segment`}
                className="mr-1 inline-flex size-6 items-center justify-center rounded-full text-fg-secondary hover:bg-hover hover:text-fg pointer-coarse:size-8"
                onClick={() => setRemoving(segment)}
              >
                <X className="size-3" aria-hidden />
              </button>
            ) : null}
          </span>
        );
      })}
      {canSave ? (
        <Button variant="secondary" size="sm" onClick={() => setSaving(true)}>
          <Bookmark aria-hidden /> Save as segment
        </Button>
      ) : null}
      <SaveDialog wid={wid} filters={filters} open={saving} onOpenChange={setSaving} />
      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this segment?</AlertDialogTitle>
            <AlertDialogDescription>
              {removing ? `The ${removing.name} segment goes. No contacts are changed.` : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!removing) return;
                remove.mutate(removing.id, {
                  onSuccess: () => toast.success("Segment deleted"),
                  onError: (error) => toastError(error),
                });
                setRemoving(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SaveDialog({
  wid,
  filters,
  open,
  onOpenChange,
}: {
  wid: string;
  filters: ContactFilters;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateSegment(wid);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    create.mutate(
      { name: name.trim(), filter: filtersToSpec(filters) },
      {
        onSuccess: () => {
          setName("");
          onOpenChange(false);
          toast.success("Segment saved");
        },
        onError: (failure) => {
          if (failure instanceof ApiError && (failure.status === 409 || failure.errors.length > 0)) {
            setError(failure.errors[0]?.message ?? "A segment with that name already exists.");
          } else {
            toastError(failure);
          }
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Save as segment</DialogTitle>
            <DialogDescription>
              A segment keeps these filters under a name. It is always whoever matches them now.
            </DialogDescription>
          </DialogHeader>
          <Field invalid={Boolean(error)}>
            <FieldLabel>Name</FieldLabel>
            <Input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} placeholder="Lead magnet with email" />
            {error ? <FieldError>{error}</FieldError> : null}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={!name.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
