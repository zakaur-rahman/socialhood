"use client";

import { Cable, Sparkles } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { AccountStatus, AiMode, Plan, SocialAccount, SocialAccountPatch } from "@/lib/api/types";
import { accountStatusLabel } from "@/lib/copy";
import { relativeTime } from "@/lib/time";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

import { DeleteAccountDialog, type DeleteMode } from "./DeleteAccountDialog";
import { DisconnectDialog } from "./DisconnectDialog";
import { PLATFORM_BG, PlatformGlyph } from "./PlatformGlyph";

const STATUS_TONE: Record<AccountStatus, { pill: string; dot: string }> = {
  active: { pill: "bg-success-soft text-success", dot: "bg-success" },
  needs_reconnect: { pill: "bg-warning-soft text-warning", dot: "bg-warning" },
  error: { pill: "bg-danger-soft text-danger-fg", dot: "bg-danger" },
  disconnected: { pill: "bg-hover text-fg-secondary", dot: "bg-fg-secondary" },
};
/** C-067: while its data is being deleted, whatever its status (the dot pulses only with motion). */
const DELETING_TONE = { pill: "bg-danger-soft text-danger-fg", dot: "bg-danger motion-safe:animate-pulse" };

const AI_MODES: { value: AiMode; label: string; hint: string }[] = [
  { value: "off", label: "Off", hint: "No AI replies" },
  { value: "suggest", label: "Suggest", hint: "AI drafts, you send" },
  { value: "auto", label: "Auto", hint: "AI sends when it's confident" },
];

/** The API the account is connected through, for the card's footer. */
const API_NAME = { instagram: "Instagram API", whatsapp: "WhatsApp Cloud API" } as const;

export type AccountActions = {
  onChange: (patch: SocialAccountPatch) => void;
  onReconnect: () => void;
  onRetrySubscribe: () => void;
  onDisconnect: () => void;
  /** C-067: Disconnect and delete data, or Remove; resolves once the API accepted it. */
  onDelete: (confirm: string, mode: DeleteMode) => Promise<void>;
};

export type AccountBusy = {
  saving: boolean;
  reconnecting: boolean;
  retrying: boolean;
  disconnecting: boolean;
  deleting: boolean;
};

/** "Last synced 3h ago", or on a date once it's a week old. */
export function lastSyncedText(iso: string, now: Date): string {
  const when = relativeTime(iso, now);
  if (when === "now") return "Last synced just now";
  return /^\d+[mhd]$/.test(when) ? `Last synced ${when} ago` : `Last synced on ${when}`;
}

/**
 * UX-SCR-07: one card per account (C-066). Avatar with the platform's badge, name and handle,
 * the status; while connected, its AI settings in an inner panel; the API it uses and when it
 * last synced; Reconnect, Retry or Disconnect for owners and admins. C-067: Disconnect and delete
 * data on a connected account, Remove on a disconnected or sandbox one, and "Deleting…" with no
 * actions until the purge has removed it.
 */
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
  busy: AccountBusy;
  actions: AccountActions;
}) {
  const now = useNow();
  const whatsapp = account.platform === "whatsapp";
  const platformName = whatsapp ? "WhatsApp" : "Instagram";
  const handle = account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "this account");
  const name = account.display_name ?? account.username ?? `${platformName} account`;
  const subtitle = account.username ? `@${account.username}` : (account.phone_number ?? platformName);
  const deleting = account.deleting;
  const live = account.status !== "disconnected" && !deleting;
  const autoLocked = plan === "free";
  const tone = deleting ? DELETING_TONE : STATUS_TONE[account.status];
  const reconnectable = !deleting && (account.status === "needs_reconnect" || account.status === "disconnected");
  const removable = !deleting && (!live || account.sandbox);
  const onDelete = (mode: DeleteMode) => (confirm: string) => actions.onDelete(confirm, mode);

  return (
    <article
      aria-label={name}
      className={cn("flex min-w-0 flex-col gap-4 rounded-2xl border border-line bg-panel p-5", !live && "bg-panel/60")}
      data-status={deleting ? "deleting" : account.status}
    >
      <header className="flex items-start gap-3">
        <div className="relative shrink-0">
          <Avatar className="size-12">
            {account.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
            <AvatarFallback className="bg-brand-soft text-brand-fg">{name.slice(0, 1).toUpperCase()}</AvatarFallback>
          </Avatar>
          <span
            role="img"
            aria-label={platformName}
            className={cn(
              "absolute -right-1 -bottom-1 grid size-5 place-items-center rounded-full text-on-brand ring-2 ring-panel",
              PLATFORM_BG[account.platform],
            )}
          >
            <PlatformGlyph platform={account.platform} className="size-3" />
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 items-center gap-2">
            <span className="truncate font-semibold">{name}</span>
            {account.sandbox ? (
              <span className="shrink-0 rounded bg-brand-soft px-1.5 text-xs font-medium text-brand-fg">Sandbox</span>
            ) : null}
          </p>
          <p className="truncate text-sm text-fg-secondary">{subtitle}</p>
        </div>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
            tone.pill,
          )}
        >
          <span className={cn("size-1.5 rounded-full", tone.dot)} aria-hidden />
          {deleting ? "Deleting…" : accountStatusLabel[account.status]}
        </span>
      </header>

      {deleting ? (
        <p role="status" className="text-sm text-fg-secondary">
          Deleting this account and everything stored for it. It disappears from this list when done.
        </p>
      ) : account.last_error && account.status !== "active" ? (
        <p role="status" className={cn("text-sm", account.status === "error" ? "text-danger-fg" : "text-warning")}>
          {account.last_error}
        </p>
      ) : null}

      {live ? (
        <div className="space-y-4 rounded-lg border border-line p-4">
          <Setting
            id={`ai-mode-${account.id}`}
            label="AI replies"
            icon={<Sparkles className="size-4 text-brand-fg" aria-hidden />}
          >
            <Select
              value={account.ai_mode}
              disabled={!canManage || busy.saving}
              onValueChange={(value) => actions.onChange({ ai_mode: value as AiMode })}
            >
              <SelectTrigger id={`ai-mode-${account.id}`} size="xl" className="w-36">
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

      <footer className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-line-subtle pt-4">
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-fg-secondary">
          <Cable className="size-3.5 shrink-0" aria-hidden />
          <span>{API_NAME[account.platform]}</span>
          {account.last_synced_at ? (
            <>
              <span aria-hidden>·</span>
              <time dateTime={account.last_synced_at}>{lastSyncedText(account.last_synced_at, now)}</time>
            </>
          ) : null}
        </p>
        {canManage && !deleting ? (
          <div className="flex flex-wrap items-center gap-2">
            {reconnectable ? (
              <Button size="lg" disabled={busy.reconnecting}
                onClick={actions.onReconnect}
              >
                {busy.reconnecting ? `Opening ${platformName}…` : "Reconnect"}
              </Button>
            ) : null}
            {account.status === "error" ? (
              <Button variant="secondary" size="lg" disabled={busy.retrying} onClick={actions.onRetrySubscribe}>
                {busy.retrying ? "Retrying…" : "Retry"}
              </Button>
            ) : null}
            {live ? <DisconnectDialog handle={handle} pending={busy.disconnecting} onConfirm={actions.onDisconnect} /> : null}
            {live && !account.sandbox ? (
              <DeleteAccountDialog
                account={account}
                handle={handle}
                mode="disconnect"
                pending={busy.deleting}
                onConfirm={onDelete("disconnect")}
              />
            ) : null}
            {removable ? (
              <DeleteAccountDialog
                account={account}
                handle={handle}
                mode="remove"
                pending={busy.deleting}
                onConfirm={onDelete("remove")}
              />
            ) : null}
          </div>
        ) : null}
      </footer>
    </article>
  );
}

function Setting({
  id,
  label,
  hint,
  icon,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-10 items-center justify-between gap-4">
      <div className="min-w-0">
        <Label htmlFor={id} className="flex items-center gap-2">
          {icon}
          {label}
        </Label>
        {hint ? <p className="text-xs text-fg-secondary">{hint}</p> : null}
      </div>
      {children}
    </div>
  );
}
