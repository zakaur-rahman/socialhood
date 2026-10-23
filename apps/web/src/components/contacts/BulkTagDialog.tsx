"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import { useBulkTag, useTags } from "@/lib/api/queries";
import { filtersToSpec, type ContactFilters } from "@/lib/contacts/filters";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/** What a bulk tag applies to: the rows ticked, or everyone the filters match. */
export type BulkTarget = { kind: "ids"; ids: string[] } | { kind: "filter"; filters: ContactFilters; count: number };

/**
 * Add or remove one tag on many contacts (GR-17). The API caps a filter-wide change; when the
 * match is too big it says how many matched, and that message shows here so the member can narrow
 * the filter.
 */
export function BulkTagDialog({
  open,
  onOpenChange,
  target,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  target: BulkTarget;
  onDone: () => void;
}) {
  const { id: wid } = useCurrentWorkspace();
  const tags = useTags(wid).data ?? [];
  const bulk = useBulkTag(wid);
  const [tagId, setTagId] = useState("");
  const count = target.kind === "ids" ? target.ids.length : target.count;
  const who = `${count.toLocaleString()} ${count === 1 ? "contact" : "contacts"}`;

  function apply(mode: "add" | "remove") {
    if (!tagId) return;
    const change = mode === "add" ? { add: [tagId], remove: [] } : { add: [], remove: [tagId] };
    const body = target.kind === "ids" ? { contact_ids: target.ids, ...change } : { filter: filtersToSpec(target.filters), ...change };
    bulk.mutate(body, {
      onSuccess: (result) => {
        toast.success(`${mode === "add" ? "Tagged" : "Untagged"} ${result.updated.toLocaleString()} ${result.updated === 1 ? "contact" : "contacts"}`);
        onOpenChange(false);
        onDone();
      },
      onError: (error) => {
        if (error instanceof ApiError && error.errors[0]) toast.error(error.errors[0].message);
        else toastError(error);
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tag {who}</DialogTitle>
          <DialogDescription>Choose a tag to add to them, or to take off them.</DialogDescription>
        </DialogHeader>
        <Field>
          <FieldLabel>Tag</FieldLabel>
          {tags.length === 0 ? (
            <p className="text-sm text-fg-secondary">There are no tags yet. Open a contact to make the first one.</p>
          ) : (
            <Select value={tagId} onValueChange={setTagId}>
              <SelectTrigger aria-label="Tag" className="w-full">
                <SelectValue placeholder="Choose a tag" />
              </SelectTrigger>
              <SelectContent>
                {tags.map((tag) => (
                  <SelectItem key={tag.id} value={tag.id}>
                    {tag.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </Field>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="secondary" disabled={!tagId} loading={bulk.isPending && bulk.variables?.remove?.length === 1} onClick={() => apply("remove")}>
            Remove tag
          </Button>
          <Button disabled={!tagId} loading={bulk.isPending && bulk.variables?.add?.length === 1} onClick={() => apply("add")}>
            Add tag
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
