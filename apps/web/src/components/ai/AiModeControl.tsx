"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
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
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { isPlanLimitError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import { autoAllowed, useBilling, useSocialAccounts, useUpdateConversation } from "@/lib/api/queries";
import type { AiMode, Conversation, ConversationPatch } from "@/lib/api/types";
import { AI_MODE_LABEL, AI_MODES } from "@/lib/ai/format";
import { errorMessage } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
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
        onError: (error) => (isPlanLimitError(error) ? undefined : toast.error(errorMessage(error))),
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

/** UX-INB-05: the AI chip in the thread header, a menu of modes; "AI paused" with Resume. */
export function AiModeMenu({ conversation, now }: { conversation: Conversation; now: Date }) {
  const control = useConversationAiMode(conversation);
  const paused = pausedUntil(conversation, now);
  const workspace = useCurrentWorkspace();

  if (paused) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1">
        <span
          className={cn("rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASS.warning)}
          title={`Paused until ${formatDayTime(paused, workspace.timezone, now)} because you replied`}
        >
          AI paused
        </span>
        <Button
          variant="ghost"
          size="xs"
          className="text-brand-fg"
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
      {/* Not modal: the Auto confirmation opens from it (a modal menu would keep the page inert). */}
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`AI mode: ${label}. Change`}
            className={cn(
              "inline-flex shrink-0 items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium hover:bg-brand/25",
              TONE_CLASS.brand,
            )}
          >
            AI: {label}
            <ChevronDown className="size-3" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60 border-line bg-panel shadow-xl">
          <DropdownMenuLabel className="text-xs text-fg-secondary">AI in this conversation</DropdownMenuLabel>
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

/** UX-INB-09: the segmented Default · Off · Suggest · Auto in the details panel. */
export function AiModeSegments({ conversation, now }: { conversation: Conversation; now: Date }) {
  const control = useConversationAiMode(conversation);
  const workspace = useCurrentWorkspace();
  const paused = pausedUntil(conversation, now);
  const far = paused && paused.getTime() - now.getTime() > 7 * 24 * 3_600_000;

  return (
    <div className="space-y-2">
      <ToggleGroup
        value={control.choice}
        onValueChange={(value) => control.choose(value as AiModeChoice)}
        aria-label="AI in this conversation"
        disabled={control.pending}
      >
        <ToggleGroupItem value="default" className="px-1.5 text-xs">
          Default
        </ToggleGroupItem>
        {AI_MODES.map((mode) => (
          <ToggleGroupItem key={mode} value={mode} className="px-1.5 text-xs">
            {AI_MODE_LABEL[mode]}
            {mode === "auto" && !control.allowsAuto ? <span className="sr-only"> (Pro)</span> : null}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <p className="text-xs text-fg-secondary">
        {control.choice === "default"
          ? control.accountMode
            ? `Uses the account's mode: ${AI_MODE_LABEL[control.accountMode]}.`
            : "Uses the account's mode."
          : `Set for this conversation: ${AI_MODE_LABEL[control.choice]}.`}
        {!control.allowsAuto ? " Auto is part of Pro." : null}
      </p>
      {paused ? (
        <div className="flex items-center justify-between gap-2 rounded-lg bg-warning/15 px-3 py-2 text-xs text-warning" role="status">
          <span>
            {far ? "AI paused until you resume it" : `AI paused until ${formatDayTime(paused, workspace.timezone, now)}`}
          </span>
          <Button variant="ghost" size="xs" className="text-fg" disabled={control.pending} onClick={control.resume}>
            Resume
          </Button>
        </div>
      ) : null}
      {control.dialogs}
    </div>
  );
}
