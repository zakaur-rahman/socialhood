"use client";

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

/**
 * FR-CON-06: disconnecting deletes the token at once and keeps what was stored for the account.
 * Deleting that too is its own action with a typed confirmation (C-067, DeleteAccountDialog).
 */
export function DisconnectDialog({
  handle,
  pending,
  onConfirm,
}: {
  handle: string;
  pending: boolean;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive-ghost" size="lg">
          Disconnect
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {handle}?</AlertDialogTitle>
          <AlertDialogDescription>
            Social Hood deletes this account&apos;s access now and stops receiving its messages and
            comments. Its conversations, comments and posts stay here for reference; to delete them
            too, use Disconnect and delete data. You can connect it again later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={pending} onClick={onConfirm}>
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
