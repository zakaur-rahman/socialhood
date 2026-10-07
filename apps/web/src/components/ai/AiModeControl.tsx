"use client";

import { ChevronDown, Sparkles } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { ProBadge } from "@/components/automations/TemplateGallery";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useUpgradeDialog } from "@/lib/api/provider";
import { autoAllowed, useBilling, useSocialAccounts, useUpdateConversation } from "@/lib/api/queries";
import type { AiMode, Conversation, ConversationPatch } from "@/lib/api/types";
import { AI_MODE_LABEL, AI_MODES } from "@/lib/ai/format";
import { TONE_CLASS } from "@/lib/inbox/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AutoConfirmDialog } from "./AiModeDialogs";

export type AiModeChoice = AiMode | "default";

/** Takeover pauses only matter in Auto (FR-SUG-05); a pause far ahead reads "until you resume". */
export function pausedUntil(conversation: Conversation, now: Date): Date | null {
  const until = conversation.ai.paused_until ? new Date(conversation.ai.paused_until) : null;
  if (!until || until <= now || conversation.ai.effective_mode !== "auto") return null;
  return until;
}

/** Auto on a plan without it: the upgrade dialog opens before any request (F-15, §4.7). */
export const AUTO_UPGRADE = { code: "entitlement_required", entitlement: "ai_modes" } as const;

/**
 * FR-SUG-01 per-conversation override: Default (the account's mode), Off, Suggest or Auto. Auto
 * asks for confirmation (F-09); a plan without Auto opens the upgrade dialog, and so does a 402
 * (lib/api/provider.tsx opens it for every 402, so it isn't a toast as well).
 */
export function useConversationAiMode(conversation: Conversation) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const update = useUpdateConversation(wid);
  const accounts = useSocialAccounts(wid);
  const billing = useBilling(wid);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const upgrade = useUpgradeDialog();

  const accountMode = accounts.data?.find((a) => a.id === conversation.social_account_id)?.ai_mode ?? null;
  const allowsAuto = autoAllowed(billing.data, workspace.plan);
  const choice: AiModeChoice = conversation.ai.override ?? "default";

  const apply = (patch: Partial<ConversationPatch>, done?: string) =>
    update.mutate(
      { id: conversation.id, patch },
      {
        onSuccess: () => (done ? toast.success(done) : undefined),
        onError: (error) => toastError(error),
      },
    );

  const choose = (next: AiModeChoice) => {
    if (next === choice) return;
    if (next === "default") return apply({ clear_ai_mode_override: true });
    if (next === "auto") return allowsAuto ? setConfirmOpen(true) : upgrade.open(AUTO_UPGRADE);
    apply({ ai_mode_override: next });
  };

  const dialogs = (
    <AutoConfirmDialog
      open={confirmOpen}
      onOpenChange={setConfirmOpen}
      target="this conversation"
      onConfirm={() => apply({ ai_mode_override: "auto" })}
    />
  );

  return {
    choice,
    accountMode,
    allowsAuto,
    pending: update.isPending,
    choose,
    resume: () => apply({ resume_ai: true }, "AI resumed"),
    dialogs,
  };
}

function defaultLabel(accountMode: AiMode | null): string {
  return accountMode ? `Account default · ${AI_MODE_LABEL[accountMode]}` : "Account default";
}

/**
 * UX-INB-05: the one AI mode control (C-063), a compact menu in the thread header: the account
 * default and each mode; "AI paused" with Resume during a takeover. In a thread header narrower
 * than 576 px (its `header` container, UI-ISS-019) the menu shows as its icon and a pause as
 * Resume alone; the button's name, and Resume's description, still say the mode or the pause.
 */
export function AiModeMenu({ conversation, now }: { conversation: Conversation; now: Date }) {
  const control = useConversationAiMode(conversation);
  const paused = pausedUntil(conversation, now);
  const workspace = useCurrentWorkspace();
  const pausedId = useId();

  if (paused) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1">
        <span
          id={pausedId}
          className={cn("hidden rounded-full px-2 py-0.5 text-xs font-medium @xl/header:inline", TONE_CLASS.warning)}
          title={`Paused until ${formatDayTime(paused, workspace.timezone, now)} because you replied`}
        >
          AI paused
        </span>
        <Button
          variant="ghost"
          size="xs"
          className="text-brand-fg"
          aria-describedby={pausedId}
          disabled={control.pending}
          onClick={control.resume}
        >
          Resume
        </Button>
        {control.dialogs}
      </span>
    );
  }

  const label = AI_MODE_LABEL[conversation.ai.effective_mode];
  return (
    <>
      {/* Menus aren't modal (ui/dropdown-menu), so the Auto confirmation can open from this one. */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {/* The AI pill: the soft Button (brand-soft, DESIGN_SYSTEM §1.4), 28 px, 40 px on coarse pointers. */}
          <Button
            variant="soft"
            size="sm"
            aria-label={`AI mode: ${label}. Change`}
            title={
              control.choice === "default"
                ? `${defaultLabel(control.accountMode)}. Change it for this conversation`
                : "Set for this conversation. Change"
            }
          >
            <Sparkles aria-hidden />
            <span className="hidden @xl/header:inline">AI: {label}</span>
            <ChevronDown className="hidden size-3 @xl/header:block" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel>AI in this conversation</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={control.choice}
            onValueChange={(value) => control.choose(value as AiModeChoice)}
          >
            <DropdownMenuRadioItem value="default">{defaultLabel(control.accountMode)}</DropdownMenuRadioItem>
            {AI_MODES.map((mode) => (
              <DropdownMenuRadioItem key={mode} value={mode}>
                {AI_MODE_LABEL[mode]}
                {mode === "auto" && !control.allowsAuto ? <>{" "}<ProBadge /></> : null}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {control.dialogs}
    </>
  );
}
