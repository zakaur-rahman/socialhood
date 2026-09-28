"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { AccountStatus, AiMode, Plan, SocialAccount, SocialAccountPatch } from "@/lib/api/types";
import { accountStatusLabel } from "@/lib/copy";
import { cn } from "@/lib/utils";

import { DisconnectDialog } from "./DisconnectDialog";
import { PlatformGlyph } from "./PlatformGlyph";

const STATUS_TONE: Record<AccountStatus, string> = {
  active: "bg-success/15 text-success",
  needs_reconnect: "bg-warning/15 text-warning",
  error: "bg-danger/15 text-danger-fg",
  disconnected: "bg-white/5 text-fg-secondary",
};

const AI_MODES: { value: AiMode; label: string; hint: string }[] = [
  { value: "off", label: "Off", hint: "No AI replies" },
  { value: "suggest", label: "Suggest", hint: "AI drafts, you send" },
  { value: "auto", label: "Auto", hint: "AI sends when it's confident" },
];

export type AccountActions = {
  onChange: (patch: SocialAccountPatch) => void;
  onReconnect: () => void;
  onRetrySubscribe: () => void;
  onDisconnect: (deleteData: boolean) => void;
};

/** UX-SCR-07: one card per connected account. */
export function AccountCard({
  account,
  plan,
  canManage,
  busy,
  actions,
}: {
  account: SocialAccount;
  plan: Plan;
  canManage: boolean;
  busy: { saving: boolean; reconnecting: boolean; retrying: boolean; disconnecting: boolean };
  actions: AccountActions;
}) {
  const whatsapp = account.platform === "whatsapp";
  const platformName = whatsapp ? "WhatsApp" : "Instagram";
  const handle = account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "this account");
  const name = account.display_name ?? account.username ?? `${platformName} account`;
  const subtitle = account.username ? `@${account.username}` : (account.phone_number ?? platformName);
  const live = account.status !== "disconnected";
  const autoLocked = plan === "free";

  return (
    <article
      aria-label={name}
      className="flex flex-col gap-4 rounded-xl border border-line bg-panel p-5"
      data-status={account.status}
    >
      <header className="flex items-start gap-3">
        <Avatar className="size-11">
          {account.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
          <AvatarFallback className="bg-brand-soft text-brand-fg">{name.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{name}</p>
          <p className="flex items-center gap-1.5 text-sm text-fg-secondary">
            <PlatformGlyph platform={account.platform} className="size-3.5" />
            <span className="truncate">{subtitle}</span>
            {account.sandbox ? (
              <span className="rounded bg-brand-soft px-1.5 text-xs font-medium text-brand-fg">Sandbox</span>
            ) : null}
          </p>
        </div>
        <span className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium", STATUS_TONE[account.status])}>
          {accountStatusLabel[account.status]}
        </span>
      </header>

      {account.last_error && account.status !== "active" ? (
        <p role="status" className={cn("text-sm", account.status === "error" ? "text-danger-fg" : "text-warning")}>
          {account.last_error}
        </p>
      ) : null}

      {live ? (
        <div className="space-y-3 border-t border-line pt-4">
          <Setting id={`ai-mode-${account.id}`} label="AI replies">
            <Select
              value={account.ai_mode}
              disabled={!canManage || busy.saving}
              onValueChange={(value) => actions.onChange({ ai_mode: value as AiMode })}
            >
              <SelectTrigger id={`ai-mode-${account.id}`} className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AI_MODES.map((mode) => (
                  <SelectItem key={mode.value} value={mode.value} disabled={mode.value === "auto" && autoLocked}>
                    {mode.label}
                    {mode.value === "auto" && autoLocked ? " · Pro" : ""}
                    <span className="sr-only">: {mode.hint}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Setting>
          <Setting id={`analysis-${account.id}`} label="AI analysis" hint="Tags intent, sentiment and leads on new messages">
            <Switch
              id={`analysis-${account.id}`}
              checked={account.ai_analysis_enabled}
              disabled={!canManage || busy.saving}
              onCheckedChange={(checked) => actions.onChange({ ai_analysis_enabled: checked })}
            />
          </Setting>
          {whatsapp ? null : (
            <Setting id={`spam-${account.id}`} label="Hide spam comments" hint="Hides comments the AI marks as spam">
              <Switch
                id={`spam-${account.id}`}
                checked={account.auto_hide_spam}
                disabled={!canManage || busy.saving}
                onCheckedChange={(checked) => actions.onChange({ auto_hide_spam: checked })}
              />
            </Setting>
          )}
        </div>
      ) : null}

      {canManage ? (
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
          <div className="flex gap-2">
            {account.status === "needs_reconnect" || account.status === "disconnected" ? (
              <Button size="sm" className="bg-brand-gradient text-white" disabled={busy.reconnecting} onClick={actions.onReconnect}>
                {busy.reconnecting ? `Opening ${platformName}…` : "Reconnect"}
              </Button>
            ) : null}
            {account.status === "error" ? (
              <Button size="sm" variant="secondary" disabled={busy.retrying} onClick={actions.onRetrySubscribe}>
                {busy.retrying ? "Retrying…" : "Retry"}
              </Button>
            ) : null}
          </div>
          {live ? <DisconnectDialog handle={handle} pending={busy.disconnecting} onConfirm={actions.onDisconnect} /> : null}
        </footer>
      ) : null}
    </article>
  );
}

function Setting({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0">
        <Label htmlFor={id}>{label}</Label>
        {hint ? <p className="text-xs text-fg-secondary">{hint}</p> : null}
      </div>
      {children}
    </div>
  );
}
