"use client";

import { useState } from "react";

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
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

/**
 * FR-CON-06: disconnecting deletes the token at once; the user chooses whether the account's
 * conversations and comments go too.
 */
export function DisconnectDialog({
  handle,
  pending,
  onConfirm,
}: {
  handle: string;
  pending: boolean;
  onConfirm: (deleteData: boolean) => void;
}) {
  const [deleteData, setDeleteData] = useState(false);
  return (
    <AlertDialog onOpenChange={(open) => (open ? setDeleteData(false) : undefined)}>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" className="min-h-10 px-3 text-danger-fg hover:bg-danger/10 hover:text-danger-fg md:min-h-9">
          Disconnect
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="border-line bg-panel">
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {handle}?</AlertDialogTitle>
          <AlertDialogDescription className="text-fg-secondary">
            Social Hood deletes this account&apos;s access now and stops receiving its messages and
            comments. You can connect it again later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex items-start gap-3 rounded-lg border border-line p-3">
          <Checkbox
            id="delete-data"
            checked={deleteData}
            onCheckedChange={(value) => setDeleteData(value === true)}
            className="mt-0.5"
          />
          <Label htmlFor="delete-data" className="block font-normal leading-snug">
            Also delete this account&apos;s conversations and comments
            <span className="mt-0.5 block text-xs text-fg-secondary">
              Leave this off to keep them for reference.
            </span>
          </Label>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            onClick={() => onConfirm(deleteData)}
            className="bg-danger-fill text-white hover:bg-danger-fill/90"
          >
            {deleteData ? "Disconnect and delete" : "Disconnect"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
