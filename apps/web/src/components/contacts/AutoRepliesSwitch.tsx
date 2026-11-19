"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useId } from "react";

import { Switch } from "@/components/ui/switch";
import { useUpdateContact } from "@/lib/api/queries";
import { keys } from "@/lib/api/queries/keys";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * GR-44: "Automatic replies" for one contact, in the contact drawer and the inbox's details panel.
 * Off means only people reply to them: no keyword, welcome, flow, comment, away-message, sequence
 * or AI Auto reply. The AI still drafts suggestions, and order notices and broadcasts go as usual.
 */
export function AutoRepliesSwitch({ contactId, off }: { contactId: string; off: boolean }) {
  const { id: wid } = useCurrentWorkspace();
  const queryClient = useQueryClient();
  const update = useUpdateContact(wid);
  const labelId = useId();
  const hintId = useId();
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0 text-sm">
        <p id={labelId} className="font-medium">
          Automatic replies
        </p>
        <p id={hintId} className="text-xs text-fg-secondary">
          {off
            ? "Off: only your team replies to this person. The AI still drafts suggestions."
            : "On: automations, the away message and AI Auto can reply to this person."}
        </p>
      </div>
      <Switch
        checked={!off}
        disabled={update.isPending}
        aria-labelledby={labelId}
        aria-describedby={hintId}
        onCheckedChange={(on) =>
          update.mutate(
            { id: contactId, body: { auto_replies_off: !on } },
            {
              onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.conversationDetails(wid) }),
              onError: (error) => toastError(error),
            },
          )
        }
      />
    </div>
  );
}
