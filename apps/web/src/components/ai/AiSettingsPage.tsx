"use client";

import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { ProBadge } from "@/components/automations/TemplateGallery";
import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  autoAllowed,
  toSettingsUpdate,
  useAiSettings,
  useBilling,
  useSocialAccounts,
  useUpdateAccount,
  useUpdateAiSettings,
} from "@/lib/api/queries";
import type { AiMode, AiSettings, SocialAccount, TakeoverMinutes } from "@/lib/api/types";
import { AI_MODE_HINT, AI_MODE_LABEL, AI_MODES, BUILT_IN_ESCALATIONS, TAKEOVER_OPTIONS } from "@/lib/ai/format";
import { errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

import { isEntitlementError } from "./AiModeControl";
import { AutoConfirmDialog, UpgradeDialog } from "./AiModeDialogs";
import { ChipListInput } from "./ChipListInput";

function handleOf(account: SocialAccount): string {
  return account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "Account");
}

/**
 * UX-SCR-07 AI: each connected account's AI mode (FR-SUG-01; Auto needs a paid plan and a
 * confirmation, F-09), the human takeover period (FR-SUG-05) and escalation phrases next to the
 * built-in rules (FR-SUG-06).
 */
export function AiSettingsPage() {
  const workspace = useCurrentWorkspace();
  const canManage = workspace.role !== "agent";
  const accounts = useSocialAccounts(workspace.id);
  const settings = useAiSettings(workspace.id, canManage);

  if (accounts.isPending || (canManage && settings.isPending)) return <PageSkeleton rows={3} />;
  if (accounts.isError) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />;
  if (canManage && settings.isError) return <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />;

  return (
    <PageFrame title="AI">
      <div className="max-w-2xl space-y-6">
        <AccountModes accounts={accounts.data.filter((a) => a.status !== "disconnected")} canManage={canManage} />
        {canManage && settings.data ? (
          <EscalationForm settings={settings.data} />
        ) : (
          <p className="text-sm text-fg-secondary">Only owners and admins can change AI settings.</p>
        )}
      </div>
    </PageFrame>
  );
}

function AccountModes({ accounts, canManage }: { accounts: SocialAccount[]; canManage: boolean }) {
  const workspace = useCurrentWorkspace();
  const update = useUpdateAccount(workspace.id);
  const billing = useBilling(workspace.id);
  const allowsAuto = autoAllowed(billing.data, workspace.plan);
  const [confirming, setConfirming] = useState<SocialAccount | null>(null);
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  const save = (account: SocialAccount, mode: AiMode) =>
    update.mutate(
      { id: account.id, patch: { ai_mode: mode } },
      {
        onSuccess: () => toast.success(`${handleOf(account)}: AI ${AI_MODE_LABEL[mode]}`),
        onError: (error) => (isEntitlementError(error) ? setUpgradeOpen(true) : toast.error(errorMessage(error))),
      },
    );

  const choose = (account: SocialAccount, mode: AiMode) => {
    if (mode === account.ai_mode) return;
    if (mode === "auto") return allowsAuto ? setConfirming(account) : setUpgradeOpen(true);
    save(account, mode);
  };

  return (
    <section aria-labelledby="ai-accounts-title" className="rounded-xl border border-line bg-panel p-5">
      <h2 id="ai-accounts-title" className="text-base font-semibold">
        AI replies by account
      </h2>
      <p className="text-xs text-fg-secondary">
        Off: no AI replies. Suggest: the AI drafts, you send. Auto: the AI sends when it&apos;s confident.
        {allowsAuto ? "" : " Auto is part of Pro."}
      </p>
      {accounts.length === 0 ? (
        <EmptyState title="No connected accounts" body="Connect Instagram or WhatsApp to choose how the AI replies." />
      ) : (
        <ul className="mt-4 divide-y divide-line-subtle">
          {accounts.map((account) => (
            <li key={account.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <PlatformGlyph platform={account.platform} className="size-4 shrink-0" />
                <span id={`ai-mode-label-${account.id}`} className="truncate text-sm font-medium">
                  {handleOf(account)}
                </span>
              </div>
              <ToggleGroup
                value={account.ai_mode}
                onValueChange={(value) => choose(account, value as AiMode)}
                aria-labelledby={`ai-mode-label-${account.id}`}
                disabled={!canManage || (update.isPending && update.variables?.id === account.id)}
                className="sm:w-72"
              >
                {AI_MODES.map((mode) => (
                  <ToggleGroupItem key={mode} value={mode} className="text-xs" title={AI_MODE_HINT[mode]}>
                    {AI_MODE_LABEL[mode]}
                    {mode === "auto" && !allowsAuto ? <>{" "}<ProBadge /></> : null}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </li>
          ))}
        </ul>
      )}
      <AutoConfirmDialog
        open={Boolean(confirming)}
        onOpenChange={(open) => (open ? undefined : setConfirming(null))}
        target={confirming ? handleOf(confirming) : "this account"}
        onConfirm={() => {
          if (confirming) save(confirming, "auto");
          setConfirming(null);
        }}
      />
      <UpgradeDialog open={upgradeOpen} onOpenChange={setUpgradeOpen} />
    </section>
  );
}

type EscalationValues = { takeover_minutes: TakeoverMinutes; escalation_phrases: string[] };

function EscalationForm({ settings }: { settings: AiSettings }) {
  const workspace = useCurrentWorkspace();
  const update = useUpdateAiSettings(workspace.id);
  const form = useForm<EscalationValues>({
    defaultValues: { takeover_minutes: settings.takeover_minutes, escalation_phrases: settings.escalation_phrases },
  });

  const onSubmit = form.handleSubmit((values) =>
    update.mutate(
      { ...toSettingsUpdate(settings), ...values },
      {
        onSuccess: (saved) => {
          form.reset({ takeover_minutes: saved.takeover_minutes, escalation_phrases: saved.escalation_phrases });
          toast.success("AI settings saved");
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    ),
  );

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6" aria-label="Takeover and escalation">
      <section aria-labelledby="takeover-title" className="space-y-3 rounded-xl border border-line bg-panel p-5">
        <div>
          <h2 id="takeover-title" className="text-base font-semibold">
            Human takeover
          </h2>
          <p className="text-xs text-fg-secondary">When you reply in a conversation, Auto pauses there for this long.</p>
        </div>
        <Controller
          control={form.control}
          name="takeover_minutes"
          render={({ field }) => (
            <ToggleGroup
              value={String(field.value)}
              onValueChange={(value) => field.onChange(Number(value) as TakeoverMinutes)}
              aria-labelledby="takeover-title"
            >
              {TAKEOVER_OPTIONS.map((option) => (
                <ToggleGroupItem key={option.value} value={String(option.value)} className="text-xs">
                  {option.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          )}
        />
      </section>

      <section aria-labelledby="escalation-title" className="space-y-4 rounded-xl border border-line bg-panel p-5">
        <div>
          <h2 id="escalation-title" className="text-base font-semibold">
            Escalation
          </h2>
          <p className="text-xs text-fg-secondary">In Auto, these always come to you instead of an AI reply.</p>
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Always built in</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-secondary" aria-label="Built-in escalation rules">
            {BUILT_IN_ESCALATIONS.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Your escalation phrases</p>
          <Controller
            control={form.control}
            name="escalation_phrases"
            render={({ field }) => (
              <ChipListInput
                id="escalation-phrases"
                label="Escalation phrases"
                items={field.value}
                onChange={field.onChange}
                placeholder="e.g. cancel my order"
                hint="A message with any of these words or phrases comes to you. Press Enter to add."
              />
            )}
          />
        </div>
      </section>

      <div className="flex justify-end">
        <Button type="submit" className="bg-brand-gradient text-white" disabled={!form.formState.isDirty || update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
