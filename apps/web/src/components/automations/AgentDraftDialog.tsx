"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { draftAccount } from "@/lib/agent/draft";
import type { AutomationDraftHandoff } from "@/lib/agent/handoff";
import { useStartAutomationDraft } from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { TRIGGER_LABEL } from "@/lib/automations/format";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { editorHref } from "./TemplateGallery";

const ACTION_LABEL = { send_message: "Send a message", ai_reply: "Reply with AI" } as const;
const SCOPE_LABEL = { all: "All posts", selected: "Chosen posts", next_post: "The next post I publish" } as const;

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs text-fg-secondary sm:pt-0.5">{label}</dt>
      <dd className="min-w-0 text-sm break-words whitespace-pre-wrap">{children}</dd>
    </div>
  );
}

/**
 * FR-AGT-03 "Open the automation draft": what Ask Social Hood prepared, to check before it
 * becomes a draft in the editor (like choosing a template, F-11). Nothing runs until the member
 * activates it there. It stays mounted and keeps the last draft while it closes, so its exit plays
 * and focus goes back to what had it when it opened, if that is still on the page (UX-A11Y-02).
 */
export function AgentDraftDialog({
  open,
  draft,
  accounts,
  onClose,
}: {
  open: boolean;
  draft: AutomationDraftHandoff | null;
  /** Connected Instagram accounts. */
  accounts: SocialAccount[];
  onClose: () => void;
}) {
  const returnFocus = useReturnFocus();
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? null : onClose())}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto border-line bg-panel sm:max-w-lg" {...returnFocus}>
        {draft ? <AgentDraftBody key={draft.nonce} draft={draft} accounts={accounts} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}

/** Inside the dialog's content and keyed by the hand-off, so each hand-off starts fresh. */
function AgentDraftBody({
  draft,
  accounts,
  onClose,
}: {
  draft: AutomationDraftHandoff;
  accounts: SocialAccount[];
  onClose: () => void;
}) {
  const workspace = useCurrentWorkspace();
  const router = useRouter();
  const start = useStartAutomationDraft(workspace.id);
  // The draft's account (or the only one) unless the member picks one; accounts may still be loading.
  const [picked, setAccountId] = useState<string | null>(null);
  const accountId = picked ?? draftAccount(draft, accounts);
  const chooseAccount = accounts.length > 1 && !draftAccount(draft, accounts);
  const chosen = accounts.find((account) => account.id === accountId);
  const message = draft.action === "ai_reply" ? draft.ai_instructions : draft.message_text;

  const open = () =>
    start.mutate(
      { draft, accountId },
      {
        onSuccess: ({ automation, applied }) => {
          if (!applied) toast.error("Some of the prepared settings didn't apply. Check each step before activating.");
          router.push(editorHref(workspace.slug, automation.id, true));
        },
        onError: (error) => toastError(error),
      },
    );

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-brand-fg" aria-hidden /> Automation from Ask Social Hood
        </DialogTitle>
        <DialogDescription className="text-fg-secondary">
          Check what it prepared. Opening it creates a draft you finish in the editor; nothing runs until you activate
          it.
        </DialogDescription>
      </DialogHeader>
      <dl className="space-y-2" data-testid="agent-draft">
        <Row label="Name">{draft.name}</Row>
        {!chooseAccount ? (
          <Row label="Account">{chosen ? accountLabel(chosen) : "Choose in the editor"}</Row>
        ) : null}
        <Row label="When">{draft.trigger ? TRIGGER_LABEL[draft.trigger] : "Choose in the editor"}</Row>
        {draft.keywords && draft.keywords.length > 0 ? <Row label="Keywords">{draft.keywords.join(", ")}</Row> : null}
        {draft.trigger === "comment_keyword" || draft.trigger === "comment_any" ? (
          <Row label="Posts">{SCOPE_LABEL[draft.post_scope]}</Row>
        ) : null}
        <Row label="Then">{draft.action ? ACTION_LABEL[draft.action] : "Choose in the editor"}</Row>
        {message ? <Row label={draft.action === "ai_reply" ? "Instructions" : "Message"}>{message}</Row> : null}
        {draft.public_reply_texts && draft.public_reply_texts.length > 0 ? (
          <Row label="Public replies">{draft.public_reply_texts.join("\n")}</Row>
        ) : null}
      </dl>
      {chooseAccount ? (
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">Which account should it run on?</legend>
          {accounts.map((account) => (
            <label
              key={account.id}
              className={cn(
                "flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border border-line px-3 text-sm",
                accountId === account.id && "border-brand-line bg-brand-soft",
              )}
            >
              <input
                type="radio"
                name="agent-draft-account"
                value={account.id}
                checked={accountId === account.id}
                onChange={() => setAccountId(account.id)}
                className="accent-brand"
              />
              {accountLabel(account)}
            </label>
          ))}
        </fieldset>
      ) : null}
      <DialogFooter>
        <Button variant="ghost" className="min-h-10 md:min-h-8" onClick={onClose}>
          Cancel
        </Button>
        <Button
          className="bg-brand-gradient min-h-10 text-white md:min-h-8"
          disabled={start.isPending || (chooseAccount && !accountId)}
          onClick={open}
        >
          {start.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Open in editor
        </Button>
      </DialogFooter>
    </>
  );
}
