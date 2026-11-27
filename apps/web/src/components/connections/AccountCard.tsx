"use client";

import { EllipsisVertical, SlidersHorizontal, Sparkles, Trash2, TriangleAlert, Unplug } from "lucide-react";
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
import { billingDate } from "@/lib/billing/plan";
import { accountStatusLabel } from "@/lib/copy";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import type { Tone } from "@/lib/ui/tone";
import { timeAgo } from "@/lib/time";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

import { DELETE_ACCOUNT_LABEL, DeleteAccountDialog, type DeleteMode } from "./DeleteAccountDialog";
import { DisconnectDialog } from "./DisconnectDialog";
import { PLATFORM_LOGO_BG, PlatformGlyph } from "./PlatformGlyph";

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

/** The API the account is connected through, for the card's handle line. */
const API_NAME = {
  instagram: "Instagram API",
  whatsapp: "WhatsApp Cloud API",
  facebook: "Facebook Pages API",
  web: "Website chat widget",
  youtube: "YouTube Data API",
} as const;

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

/** "synced 3h ago", or on a date once it's a week old; the card's tooltip has the full date. */
export function lastSyncedText(iso: string, now: Date): string {
  return `synced ${timeAgo(iso, now)}`;
}

/**
 * UX-SCR-07: one compact card per account (C-066). Avatar with the platform's badge, the name, and
 * one line with the handle, the API it uses and when it last synced; the status; an error in one
 * small line. While connected: the AI replies mode inline and an "AI settings" disclosure holding
 * the two switches. Reconnect or Retry only when needed, for owners and admins; Disconnect and
 * D-09's "Delete account and data" sit in the ⋯ menu, each opening its confirm dialog, so a healthy
 * card shows no red. C-214: a deleted account waits 15 days, showing the date and Reconnect (which
 * keeps its data); "Deleting…" with no actions once the purge is under way.
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
  // C-214: the day its data goes, while a reconnect can still keep it.
  const dueAt = deleting && account.deletion_due_at && new Date(account.deletion_due_at) > now ? account.deletion_due_at : null;
  const deletesOn = dueAt ? billingDate(dueAt, Intl.DateTimeFormat().resolvedOptions().timeZone, now) : null;
  const restorable = deletesOn !== null && canManage && !account.sandbox;
  const live = account.status !== "disconnected" && !deleting;
  const manage = canManage && !deleting;
  const autoLocked = plan === "free";
  const tone = deleting ? DELETING_TONE : STATUS_TONE[account.status];
  const reconnectable = !deleting && (account.status === "needs_reconnect" || account.status === "disconnected");
  // C-067's two modes: a live, real account is disconnected and its data deleted; a disconnected or
  // sandbox one is removed. D-09: one menu item opens either.
  const deleteMode: DeleteMode = live && !account.sandbox ? "disconnect" : "remove";
  // YouTube is publish-only: no DMs, comments or AI replies, so no AI settings (C-195).
  const aiOn = live && account.platform !== "youtube";
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const settingsId = `ai-settings-${account.id}`;
  // A dialog opened from the menu hands focus back to the menu's trigger.
  const refocusMenu = (event: Event) => {
    event.preventDefault();
    menuTrigger.current?.focus();
  };

  return (
    <Card asChild className={cn("flex flex-col gap-2", !live && "bg-field")}>
      <article aria-label={name} data-status={deleting ? "deleting" : account.status}>
      <header className="flex items-start gap-3">
        <Avatar>
          {account.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
          <AvatarFallback className="bg-raised text-fg">{name.slice(0, 1).toUpperCase()}</AvatarFallback>
          <AvatarBadge role="img" aria-label={platformName} className={PLATFORM_LOGO_BG[account.platform]}>
            <PlatformGlyph platform={account.platform} />
          </AvatarBadge>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-semibold" title={name}>
              {name}
            </span>
            {account.sandbox ? (
              <Badge tone="neutral" shape="tag">
                Sandbox
              </Badge>
            ) : null}
          </p>
          <p className="truncate text-xs text-fg-secondary" title={subtitle}>
            {subtitle}
          </p>
          <p className="flex min-w-0 items-center gap-1.5 text-xs text-fg-secondary">
            <span className="truncate">{API_NAME[account.platform]}</span>
            {account.last_synced_at ? (
              <>
                <span aria-hidden>·</span>
                <time
                  className="shrink-0"
                  dateTime={account.last_synced_at}
                  title={`Last synced ${new Date(account.last_synced_at).toLocaleString()}`}
                >
                  {lastSyncedText(account.last_synced_at, now)}
                </time>
              </>
            ) : null}
          </p>
        </div>
        {!deleting && account.status === "active" ? (
          // Connected is the normal state: a quiet dot, so a problem's pill stands out.
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-fg-secondary">
            <span className={cn("size-1.5 rounded-full", tone.dot)} aria-hidden />
            {accountStatusLabel[account.status]}
          </span>
        ) : (
          <Badge tone={tone.tone} size="md">
            <span className={cn("size-1.5 rounded-full", tone.dot)} aria-hidden />
            {deletesOn ? `Deletes on ${deletesOn}` : deleting ? "Deleting…" : accountStatusLabel[account.status]}
          </Badge>
        )}
      </header>

      {deletesOn ? (
        <p role="status" className="text-xs text-fg-secondary">
          Everything stored for it is deleted on {deletesOn}. Reconnect before then to keep it.
        </p>
      ) : deleting ? (
        <p role="status" className="text-xs text-fg-secondary">
          Deleting this account and everything stored for it. It disappears from this list when done.
        </p>
      ) : account.last_error && account.status !== "active" ? (
        <p
          role="status"
          className={cn(
            "flex min-w-0 items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs",
            account.status === "error" ? "border-danger-line bg-danger-soft text-danger-fg" : "border-warning-line bg-warning-soft text-warning",
          )}
        >
          <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate" title={account.last_error}>
            {account.last_error}
          </span>
        </p>
      ) : null}

      {restorable ? (
        <div className="mt-1 flex justify-end border-t border-line pt-3">
          <Button variant="secondary" size="sm" disabled={busy.reconnecting} onClick={actions.onReconnect}>
            {busy.reconnecting ? `Opening ${platformName}…` : "Reconnect"}
          </Button>
        </div>
      ) : null}

      {live || manage ? (
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-2 border-t border-line pt-3">
          {aiOn ? (
            <>
              <div className="flex items-center gap-2">
                <Label htmlFor={`ai-mode-${account.id}`} className="text-xs font-medium text-fg">
                  <Sparkles className="size-3.5 text-brand-fg" aria-hidden />
                  AI replies
                </Label>
                <Select
                  value={account.ai_mode}
                  disabled={!canManage || busy.saving}
                  onValueChange={(value) => actions.onChange({ ai_mode: value as AiMode })}
                >
                  <SelectTrigger id={`ai-mode-${account.id}`} size="sm" className="text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {AI_MODES.map((mode) => (
                      <SelectItem key={mode.value} value={mode.value}>
                        {mode.label}
                        {mode.value === "auto" && autoLocked ? " · Creator" : ""}
                        <span className="sr-only">: {mode.hint}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant={settingsOpen ? "secondary" : "ghost"}
                size="icon-sm"
                aria-label="AI settings"
                title="AI settings"
                aria-expanded={settingsOpen}
                aria-controls={settingsId}
                onClick={() => setSettingsOpen((open) => !open)}
              >
                <SlidersHorizontal aria-hidden />
              </Button>
            </>
          ) : null}
          {manage ? (
            <div className="ml-auto flex items-center gap-1.5">
              {reconnectable ? (
                <Button variant="secondary" size="sm" disabled={busy.reconnecting} onClick={actions.onReconnect}>
                  {busy.reconnecting ? `Opening ${platformName}…` : "Reconnect"}
                </Button>
              ) : null}
              {account.status === "error" ? (
                <Button variant="secondary" size="sm" disabled={busy.retrying} onClick={actions.onRetrySubscribe}>
                  {busy.retrying ? "Retrying…" : "Retry"}
                </Button>
              ) : null}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button ref={menuTrigger} variant="ghost" size="icon-sm" aria-label={`More actions for ${name}`}>
                    <EllipsisVertical aria-hidden />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {live ? (
                    <DropdownMenuItem onSelect={() => setDisconnectOpen(true)}>
                      <Unplug aria-hidden /> Disconnect
                    </DropdownMenuItem>
                  ) : null}
                  <DropdownMenuItem variant="destructive" onSelect={() => setDeleteOpen(true)}>
                    <Trash2 aria-hidden /> {DELETE_ACCOUNT_LABEL}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              {live ? (
                <DisconnectDialog
                  handle={handle}
                  pending={busy.disconnecting}
                  open={disconnectOpen}
                  onOpenChange={setDisconnectOpen}
                  onCloseAutoFocus={refocusMenu}
                  onConfirm={actions.onDisconnect}
                />
              ) : null}
              <DeleteAccountDialog
                account={account}
                handle={handle}
                mode={deleteMode}
                pending={busy.deleting}
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                onCloseAutoFocus={refocusMenu}
                onConfirm={(confirm) => actions.onDelete(confirm, deleteMode)}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {aiOn ? (
        <CardInset id={settingsId} hidden={!settingsOpen} padding="compact" className="space-y-2">
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

      {live && account.platform === "youtube" && account.status === "active" && !account.capabilities.includes("account_insights") ? (
        <p className="text-xs text-fg-secondary" data-testid="reconnect-insights">
          Reconnect to add watch time and subscriber changes
          {canManage ? (
            <>
              {" "}
              <Button variant="link" size="xs" className="px-0" disabled={busy.reconnecting} onClick={actions.onReconnect}>
                Reconnect
              </Button>
            </>
          ) : null}
        </p>
      ) : null}
      </article>
    </Card>
  );
}

function Setting({ id, label, hint, children }: { id: string; label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-8 items-center justify-between gap-4">
      <div className="min-w-0">
        <Label htmlFor={id} className="text-xs">
          {label}
        </Label>
        <p className="text-xs text-fg-secondary">{hint}</p>
      </div>
      {children}
    </div>
  );
}
