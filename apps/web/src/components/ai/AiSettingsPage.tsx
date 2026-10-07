"use client";

import { CheckCircle2, Lock, MessagesSquare, ShieldAlert, Timer } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { ProBadge } from "@/components/automations/TemplateGallery";
import { PLATFORM_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { PhraseChips } from "@/components/settings/PhraseChips";
import { SaveBar } from "@/components/settings/SaveBar";
import { SectionLabel, SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useUpgradeDialog } from "@/lib/api/provider";
import {
  autoAllowed,
  toSettingsUpdate,
  useAiSettings,
  useBilling,
  useSocialAccounts,
  useUpdateAccount,
  useUpdateAiSettings,
} from "@/lib/api/queries";
import type { AccountStatus, AiMode, AiSettings, SocialAccount, TakeoverMinutes } from "@/lib/api/types";
import { AI_MODE_HINT, AI_MODE_LABEL, AI_MODES, BUILT_IN_ESCALATIONS, TAKEOVER_OPTIONS } from "@/lib/ai/format";
import { errorMessage } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AUTO_UPGRADE } from "./AiModeControl";
import { AutoConfirmDialog } from "./AiModeDialogs";

/** AiSettingsUpdate.escalation_phrases (apps/api schemas/ai.py): up to 20, each up to 120 characters. */
export const ESCALATION_PHRASES_MAX = 20;
const PHRASE_MAX_CHARS = 120;

const API_NAME = { instagram: "Instagram API", whatsapp: "WhatsApp Cloud API" } as const;

const STATUS_DOT: Record<AccountStatus, string> = {
  active: "bg-success",
  needs_reconnect: "bg-warning",
  error: "bg-danger",
  disconnected: "bg-fg-secondary",
};

function handleOf(account: SocialAccount): string {
  return account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "Account");
}

/**
 * UX-SCR-07 AI Rules & Takeover (C-066): on the left each connected account's AI mode
 * (FR-SUG-01; Auto needs a paid plan and a confirmation, F-09) and the human takeover period
 * (FR-SUG-05); on the right the built-in escalation rules and the workspace's escalation phrases
 * (FR-SUG-06). Modes save as they change; takeover and phrases save from the save bar.
 */
export function AiSettingsPage() {
  const workspace = useCurrentWorkspace();
  const canManage = workspace.role !== "agent";
  const accounts = useSocialAccounts(workspace.id);
  const settings = useAiSettings(workspace.id, canManage);

  if (accounts.isPending || (canManage && settings.isPending)) return <PageSkeleton rows={3} />;
  if (accounts.isError) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />;
  if (canManage && settings.isError) return <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />;

  const live = accounts.data.filter((a) => a.status !== "disconnected");
  const header = (
    <SettingsPageHeader
      label="Autonomy & safety"
      title="AI Rules & Takeover"
      description="How the AI replies on each account, how long it steps back when you reply, and what always comes to you."
    />
  );

  if (!canManage || !settings.data) {
    return (
      <SettingsFrame header={header}>
        <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
          <AccountModes accounts={live} canManage={false} />
          <SettingsCard
            id="ai-readonly"
            icon={<Lock />}
            title="Takeover and escalation"
            description="Only owners and admins can change AI settings."
          />
        </div>
      </SettingsFrame>
    );
  }
  return (
    <SettingsFrame header={header}>
      <RulesForm settings={settings.data} modes={<AccountModes accounts={live} canManage />} />
    </SettingsFrame>
  );
}

function AccountModes({ accounts, canManage }: { accounts: SocialAccount[]; canManage: boolean }) {
  const workspace = useCurrentWorkspace();
  const update = useUpdateAccount(workspace.id);
  const billing = useBilling(workspace.id);
  const allowsAuto = autoAllowed(billing.data, workspace.plan);
  const [confirming, setConfirming] = useState<SocialAccount | null>(null);
  const upgrade = useUpgradeDialog();

  const save = (account: SocialAccount, mode: AiMode) =>
    update.mutate(
      { id: account.id, patch: { ai_mode: mode } },
      {
        onSuccess: () => toast.success(`${handleOf(account)}: AI ${AI_MODE_LABEL[mode]}`),
        // A 402 opens the upgrade dialog by itself (lib/api/provider.tsx).
        onError: (error) => toastError(error),
      },
    );

  const choose = (account: SocialAccount, mode: AiMode) => {
    if (mode === account.ai_mode) return;
    if (mode === "auto") return allowsAuto ? setConfirming(account) : upgrade.open(AUTO_UPGRADE);
    save(account, mode);
  };

  return (
    <SettingsCard
      id="ai-accounts"
      icon={<MessagesSquare />}
      title="AI replies by account"
      description={
        <>
          <span className="font-medium text-fg">Off:</span> no AI replies.{" "}
          <span className="font-medium text-fg">Suggest:</span> the AI drafts, you send.{" "}
          <span className="font-medium text-fg">Auto:</span> the AI sends when it&apos;s confident.
        </>
      }
      aside={
        accounts.length > 0 ? (
          <Badge size="md" className="tabular-nums">
            {accounts.length} connected
          </Badge>
        ) : null
      }
    >
      {accounts.length === 0 ? (
        <EmptyState title="No connected accounts" body="Connect Instagram or WhatsApp to choose how the AI replies." />
      ) : (
        <ul className="space-y-2" aria-label="AI mode per account">
          {accounts.map((account) => (
            <li
              key={account.id}
              className="flex flex-col gap-3 rounded-lg border border-line p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span
                  aria-hidden
                  className={cn("grid size-10 shrink-0 place-items-center rounded-xl text-on-brand", PLATFORM_BG[account.platform])}
                >
                  <PlatformGlyph platform={account.platform} className="size-5" />
                </span>
                <div className="min-w-0">
                  <p id={`ai-mode-label-${account.id}`} className="truncate text-sm font-medium">
                    {handleOf(account)}
                  </p>
                  <p className="flex items-center gap-1.5 text-xs text-fg-secondary">
                    <span className={cn("size-1.5 shrink-0 rounded-full", STATUS_DOT[account.status])} aria-hidden />
                    {API_NAME[account.platform]}
                  </p>
                </div>
              </div>
              <ToggleGroup
                value={account.ai_mode}
                onValueChange={(value) => choose(account, value as AiMode)}
                aria-labelledby={`ai-mode-label-${account.id}`}
                disabled={!canManage || (update.isPending && update.variables?.id === account.id)}
                size="xl"
                className="sm:w-64"
              >
                {AI_MODES.map((mode) => {
                  const locked = mode === "auto" && !allowsAuto;
                  return (
                    <Tooltip key={mode}>
                      <TooltipTrigger asChild>
                        <ToggleGroupItem value={mode} disabled={locked}>
                          {AI_MODE_LABEL[mode]}
                          {locked ? (
                            <>
                              {" "}
                              <ProBadge />
                            </>
                          ) : null}
                        </ToggleGroupItem>
                      </TooltipTrigger>
                      <TooltipContent>{locked ? "Auto is part of Pro" : AI_MODE_HINT[mode]}</TooltipContent>
                    </Tooltip>
                  );
                })}
              </ToggleGroup>
            </li>
          ))}
        </ul>
      )}
      {!allowsAuto && accounts.length > 0 ? (
        <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg-secondary">
          <Lock className="size-4 shrink-0" aria-hidden />
          Auto is part of Pro.
          {canManage ? (
            // An inline link in the sentence: the link Button's 32 px (40 px on coarse pointers), no padding.
            <Button type="button" variant="link" className="px-0" onClick={() => upgrade.open(AUTO_UPGRADE)}>
              Upgrade for Auto
            </Button>
          ) : null}
        </p>
      ) : null}
      <AutoConfirmDialog
        open={Boolean(confirming)}
        onOpenChange={(open) => (open ? undefined : setConfirming(null))}
        target={confirming ? handleOf(confirming) : "this account"}
        onConfirm={() => {
          if (confirming) save(confirming, "auto");
          setConfirming(null);
        }}
      />
    </SettingsCard>
  );
}

type RulesValues = { takeover_minutes: TakeoverMinutes; escalation_phrases: string[] };

function valuesOf(settings: AiSettings): RulesValues {
  return { takeover_minutes: settings.takeover_minutes, escalation_phrases: settings.escalation_phrases };
}

function RulesForm({ settings, modes }: { settings: AiSettings; modes: ReactNode }) {
  const workspace = useCurrentWorkspace();
  const update = useUpdateAiSettings(workspace.id);
  const [saveError, setSaveError] = useState<string | null>(null);
  const form = useForm<RulesValues>({ defaultValues: valuesOf(settings) });

  const onSubmit = form.handleSubmit((values) => {
    setSaveError(null);
    update.mutate(
      { ...toSettingsUpdate(settings), ...values },
      {
        onSuccess: (saved) => {
          form.reset(valuesOf(saved));
          toast.success("AI settings saved");
        },
        onError: (error) => setSaveError(errorMessage(error)),
      },
    );
  });

  return (
    <form onSubmit={onSubmit} noValidate aria-label="Takeover and escalation">
      <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
        <div className="min-w-0 space-y-6">
          {modes}
          <SettingsCard
            id="takeover"
            icon={<Timer />}
            title="Human takeover"
            description="When you reply in a conversation, Auto pauses there for this long."
          >
            <Controller
              control={form.control}
              name="takeover_minutes"
              render={({ field }) => (
                <ToggleGroup
                  value={String(field.value)}
                  onValueChange={(value) => field.onChange(Number(value) as TakeoverMinutes)}
                  aria-labelledby="takeover-title"
                  size="xl"
                  className="grid grid-cols-2 sm:grid-cols-4"
                >
                  {TAKEOVER_OPTIONS.map((option) => (
                    <ToggleGroupItem key={option.value} value={String(option.value)}>
                      {option.label}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              )}
            />
          </SettingsCard>
        </div>

        <SettingsCard
          id="escalation"
          icon={<ShieldAlert />}
          title="Escalation"
          description="In Auto, these conversations always come to you instead of an AI reply."
        >
          <div className="space-y-6">
            <div className="space-y-3">
              <SectionLabel id="built-in-label">Always built in</SectionLabel>
              <ul className="grid gap-2 sm:grid-cols-2" aria-label="Built-in escalation rules">
                {BUILT_IN_ESCALATIONS.map((rule) => (
                  <li key={rule} className="flex items-start gap-2 rounded-lg border border-line p-3 text-sm">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
            <Controller
              control={form.control}
              name="escalation_phrases"
              render={({ field }) => (
                <PhraseChips
                  id="escalation-phrases"
                  label="Your escalation phrases"
                  items={field.value}
                  onChange={field.onChange}
                  max={ESCALATION_PHRASES_MAX}
                  maxLength={PHRASE_MAX_CHARS}
                  placeholder="e.g. cancel my order"
                  hint="A message with any of these words or phrases comes to you."
                />
              )}
            />
          </div>
        </SettingsCard>
      </div>

      <SaveBar
        dirty={form.formState.isDirty}
        saving={update.isPending}
        error={saveError}
        onReset={() => {
          setSaveError(null);
          form.reset(valuesOf(settings));
        }}
        onSave={() => void onSubmit()}
      />
    </form>
  );
}
