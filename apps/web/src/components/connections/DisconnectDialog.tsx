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
        <Button variant="ghost" className="min-h-10 px-3 text-danger-fg hover:bg-danger/10 hover:text-danger-fg md:min-h-9">
          Disconnect
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="border-line bg-panel">
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {handle}?</AlertDialogTitle>
          <AlertDialogDescription className="text-fg-secondary">
            Social Hood deletes this account&apos;s access now and stops receiving its messages and
            comments. Its conversations, comments and posts stay here for reference; to delete them
            too, use Disconnect and delete data. You can connect it again later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            onClick={onConfirm}
            className="bg-danger-fill text-white hover:bg-danger-fill/90"
          >
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
