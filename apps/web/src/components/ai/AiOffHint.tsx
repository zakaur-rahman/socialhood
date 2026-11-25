"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { keys, useSocialAccounts, useUpdateAccount } from "@/lib/api/queries";
import type { Conversation } from "@/lib/api/types";
import { accountName } from "@/lib/inbox/format";
import { toastError } from "@/lib/toast-error";
import { useStoredFlag } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * C-204: accounts start with AI replies off. Above the composer of a conversation whose account is
 * off (and has no per-conversation mode), one quiet line offers Suggest. Only for members who can
 * change it (not agents); dismissed per account, per browser.
 */
export function AiOffHint({ conversation }: { conversation: Conversation }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const queryClient = useQueryClient();
  const accounts = useSocialAccounts(wid);
  const update = useUpdateAccount(wid);
  const account = accounts.data?.find((item) => item.id === conversation.social_account_id);
  const [dismissed, setDismissed] = useStoredFlag(`socialhood:ai-off-hint:${conversation.social_account_id}`);

  const show =
    workspace.role !== "agent" &&
    !dismissed &&
    account !== undefined &&
    account.ai_mode === "off" &&
    conversation.ai.override == null;
  if (!show) return null;

  const name = accountName(account);
  const turnOn = () =>
    update.mutate(
      { id: account.id, patch: { ai_mode: "suggest" } },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: keys.conversationDetails(wid) });
          void queryClient.invalidateQueries({ queryKey: keys.conversationLists(wid) });
          toast.success(`AI drafts are on for ${name}. New messages get a draft.`);
        },
        onError: (error) => toastError(error),
      },
    );

  return (
    <div
      className="mx-4 mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-secondary"
      data-testid="ai-off-hint"
    >
      <Sparkles aria-hidden className="size-4 shrink-0" />
      <p className="min-w-0 flex-1">AI drafts are off for {name}.</p>
      <Button size="sm" variant="secondary" loading={update.isPending} onClick={turnOn}>
        Turn on Suggest
      </Button>
      <Button size="icon-sm" variant="ghost" aria-label="Hide this" onClick={() => setDismissed(true)}>
        <X aria-hidden />
      </Button>
    </div>
  );
}
