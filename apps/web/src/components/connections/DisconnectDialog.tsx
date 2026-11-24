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
} from "@/components/ui/alert-dialog";

/**
 * FR-CON-06: disconnecting deletes the token at once and keeps what was stored for the account.
 * Deleting that too is its own action with a typed confirmation (C-067, DeleteAccountDialog).
 * The card's ⋯ menu opens it, so the caller owns `open` (like DeleteAccountDialog).
 */
export function DisconnectDialog({
  handle,
  pending,
  open,
  onOpenChange,
  onCloseAutoFocus,
  onConfirm,
}: {
  handle: string;
  pending: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCloseAutoFocus?: (event: Event) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {handle}?</AlertDialogTitle>
          <AlertDialogDescription>
            Amplychat deletes this account&apos;s access now and stops receiving its messages and
            comments. Its conversations, comments and posts stay here for reference; to delete them
            too, use Delete account and data. You can connect it again later.
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
