"use client";

import { Cable, EllipsisVertical, Sparkles, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Avatar, AvatarBadge, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardInset } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { AccountStatus, AiMode, Plan, SocialAccount, SocialAccountPatch } from "@/lib/api/types";
import { accountStatusLabel } from "@/lib/copy";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import type { Tone } from "@/lib/ui/tone";
import { relativeTime } from "@/lib/time";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

import { DELETE_ACCOUNT_LABEL, DeleteAccountDialog, type DeleteMode } from "./DeleteAccountDialog";
import { DisconnectDialog } from "./DisconnectDialog";
import { PLATFORM_BG, PlatformGlyph } from "./PlatformGlyph";

const STATUS_TONE: Record<AccountStatus, { tone: Tone; dot: string }> = {
  active: { tone: "success", dot: "bg-success" },
  needs_reconnect: { tone: "warning", dot: "bg-warning" },
  error: { tone: "danger", dot: "bg-danger" },
  disconnected: { tone: "neutral", dot: "bg-fg-secondary" },
};
/** C-067: while its data is being deleted, whatever its status (the dot pulses only with motion). */
const DELETING_TONE: { tone: Tone; dot: string } = { tone: "danger", dot: "bg-danger motion-safe:animate-pulse" };

const AI_MODES: { value: AiMode; label: string; hint: string }[] = [
  { value: "off", label: "Off", hint: "No AI replies" },
  { value: "suggest", label: "Suggest", hint: "AI drafts, you send" },
  { value: "auto", label: "Auto", hint: "AI sends when it's confident" },
];

/** The API the account is connected through, for the card's footer. */
const API_NAME = { instagram: "Instagram API", whatsapp: "WhatsApp Cloud API", facebook: "Facebook Pages API" } as const;

export type AccountActions = {
  onChange: (patch: SocialAccountPatch) => void;
  onReconnect: () => void;
  onRetrySubscribe: () => void;
  onDisconnect: () => void;
  /** C-067: delete the account's data (D-09: the menu item); resolves once the API accepted it. */
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
 * last synced; Reconnect, Retry or Disconnect (a neutral ghost button) for owners and admins. D-09
 * (amends C-067): one "Delete account and data" item in the ⋯ menu for every account, which opens
 * the typed-confirm dialog; a healthy card shows no red. "Deleting…" with no actions until the
 * purge has removed it.
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
  const platformName = PLATFORM_LABEL[account.platform];
  const handle = account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "this account");
  const name = account.display_name ?? account.username ?? `${platformName} account`;
  const subtitle = account.username ? `@${account.username}` : (account.phone_number ?? platformName);
  const deleting = account.deleting;
  const live = account.status !== "disconnected" && !deleting;
  const autoLocked = plan === "free";
  const tone = deleting ? DELETING_TONE : STATUS_TONE[account.status];
  const reconnectable = !deleting && (account.status === "needs_reconnect" || account.status === "disconnected");
  // C-067's two modes: a live, real account is disconnected and its data deleted; a disconnected or
  // sandbox one is removed. D-09: one menu item opens either.
  const deleteMode: DeleteMode = live && !account.sandbox ? "disconnect" : "remove";
  const [deleteOpen, setDeleteOpen] = useState(false);
  const menuTrigger = useRef<HTMLButtonElement>(null);

  return (
    <Card asChild padding="roomy" className={cn("flex flex-col gap-4", !live && "bg-field")}>
      <article aria-label={name} data-status={deleting ? "deleting" : account.status}>
      <header className="flex items-start gap-3">
        <Avatar size="lg">
          {account.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
          <AvatarFallback className="bg-brand-soft text-brand-fg">{name.slice(0, 1).toUpperCase()}</AvatarFallback>
          <AvatarBadge role="img" aria-label={platformName} className={PLATFORM_BG[account.platform]}>
            <PlatformGlyph platform={account.platform} />
          </AvatarBadge>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 items-center gap-2">
            <span className="truncate font-semibold">{name}</span>
            {account.sandbox ? (
              <Badge tone="brand" shape="tag">
                Sandbox
              </Badge>
            ) : null}
          </p>
          <p className="truncate text-sm text-fg-secondary">{subtitle}</p>
        </div>
        <Badge tone={tone.tone} size="md">
          <span className={cn("size-1.5 rounded-full", tone.dot)} aria-hidden />
          {deleting ? "Deleting…" : accountStatusLabel[account.status]}
        </Badge>
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
        <CardInset className="space-y-4">
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
                  <SelectItem key={mode.value} value={mode.value}>
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
        </CardInset>
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
              <Button variant="secondary" size="lg" disabled={busy.reconnecting}
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button ref={menuTrigger} variant="ghost" size="icon-lg" aria-label={`More actions for ${name}`}>
                  <EllipsisVertical aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => setDeleteOpen(true)}>
                  <Trash2 aria-hidden /> {DELETE_ACCOUNT_LABEL}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <DeleteAccountDialog
              account={account}
              handle={handle}
              mode={deleteMode}
              pending={busy.deleting}
              open={deleteOpen}
              onOpenChange={setDeleteOpen}
              onCloseAutoFocus={(event) => {
                event.preventDefault();
                menuTrigger.current?.focus();
              }}
              onConfirm={(confirm) => actions.onDelete(confirm, deleteMode)}
            />
          </div>
        ) : null}
      </footer>
      </article>
    </Card>
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
