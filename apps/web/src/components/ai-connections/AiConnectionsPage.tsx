"use client";

import { Activity, Bot, ExternalLink, Plug, ShieldAlert, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BILLING_HREF } from "@/components/shell/nav";
import {
  useAiConnectionActivity,
  useAiConnections,
  useAiConnectionsSettings,
  useRevokeAiConnection,
  useRevokeAllAiConnections,
  useUpdateAiConnectionsMode,
} from "@/lib/api/queries";
import type { AiConnection, AiConnectionCall, AiConnectionsMode } from "@/lib/api/types";
import { siteHref } from "@/lib/marketing/site";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

export const SETUP_GUIDE_PATH = "/developers/mcp";

/** The four modes, least first, with what each allows in plain words (01-design.md §6.7). */
export const MODES: readonly { mode: AiConnectionsMode; label: string; body: string }[] = [
  { mode: "off", label: "Off", body: "AI apps can't do anything here. They can only say that connections are off." },
  {
    mode: "read_only",
    label: "Read only",
    body: "AI apps can read posts, the inbox, comments, analytics, knowledge and automations. They can't change anything.",
  },
  {
    mode: "read_drafts",
    label: "Read and drafts",
    body: "Reading, plus drafts: draft posts and reply drafts that a person finishes in Amplychat. Nothing is scheduled.",
  },
  {
    mode: "full",
    label: "Full",
    body: "Reading and drafts, plus scheduling, changing and cancelling posts, uploading media, adding knowledge and pausing or resuming automations. Replies are never sent by an AI app.",
  },
];

/** A scope in plain words, as on the consent page. */
export const SCOPE_WORDS: Record<string, string> = {
  "workspace:read": "Workspace and accounts",
  "posts:read": "See posts and media",
  "posts:write": "Schedule and change posts",
  "media:write": "Upload media",
  "conversations:read": "Read the inbox",
  "replies:draft": "Draft replies",
  "comments:read": "Read comments",
  "analytics:read": "Read analytics",
  "knowledge:read": "Search knowledge",
  "knowledge:write": "Add knowledge",
  "automations:read": "See automations",
  "automations:write": "Pause and resume automations",
  ask: "Ask Amplychat",
};

const OUTCOME: Record<AiConnectionCall["outcome"], { label: string; tone: "success" | "warning" | "danger" }> = {
  ok: { label: "Done", tone: "success" },
  refused: { label: "Refused", tone: "warning" },
  error: { label: "Failed", tone: "danger" },
};

/**
 * Settings › Connected AI apps (C-165 phase C): what AI apps (Claude, ChatGPT, Codex over MCP)
 * may do in this workspace, and every app connected to it, each with its member, what it may do,
 * when it was last used, its recent tool calls and Disconnect. Owners and admins set the mode and
 * see everyone's connections; other members see their own.
 */
export function AiConnectionsPage() {
  const workspace = useCurrentWorkspace();
  const admin = workspace.role === "owner" || workspace.role === "admin";
  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Connected AI apps"
          description={
            <>
              Claude, ChatGPT and Codex can work in this workspace as one of its members.{" "}
              <Link
                className="inline-flex items-center gap-1 font-medium text-brand-fg underline underline-offset-4"
                href={siteHref(SETUP_GUIDE_PATH) as Route}
              >
                How to connect an AI app <ExternalLink className="size-3.5" aria-hidden />
              </Link>
            </>
          }
        />
      }
    >
      {admin ? <ModeCard /> : null}
      <ConnectionsCard />
    </SettingsFrame>
  );
}

function ModeCard() {
  const workspace = useCurrentWorkspace();
  const settings = useAiConnectionsSettings(workspace.id);
  const update = useUpdateAiConnectionsMode(workspace.id);
  const current = settings.data?.mode;
  const allowed = new Set(settings.data?.plan_allows ?? []);
  const capped = settings.data && settings.data.effective_mode !== settings.data.mode;

  return (
    <SettingsCard
      id="ai-mode"
      icon={<ShieldAlert />}
      title="What AI apps may do"
      description="Applies to every connected app and API key, from their next request."
    >
      {settings.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : settings.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load this setting. Try again in a moment.</p>
      ) : (
        <fieldset className="space-y-2" disabled={update.isPending}>
          <legend className="sr-only">What AI apps may do</legend>
          {MODES.map((option) => {
            const inPlan = allowed.has(option.mode);
            const id = `ai-mode-${option.mode}`;
            return (
              <label
                key={option.mode}
                htmlFor={id}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-lg border border-line p-3",
                  current === option.mode && "border-brand-line bg-brand-soft",
                  !inPlan && "cursor-not-allowed opacity-70",
                )}
              >
                <input
                  id={id}
                  type="radio"
                  name="ai-connections-mode"
                  value={option.mode}
                  checked={current === option.mode}
                  disabled={!inPlan}
                  aria-describedby={`${id}-body`}
                  onChange={() =>
                    update.mutate(option.mode, {
                      onSuccess: () => toast.success(`AI apps: ${option.label.toLowerCase()}`),
                      onError: (error) => toastError(error),
                    })
                  }
                  className="mt-1 accent-brand"
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {option.label}
                    {!inPlan ? <Badge tone="neutral">Pro and Max</Badge> : null}
                  </span>
                  <span id={`${id}-body`} className="block text-sm text-fg-secondary">
                    {option.body}
                  </span>
                </span>
              </label>
            );
          })}
        </fieldset>
      )}
      {capped ? (
        <p className="text-sm text-fg-secondary">
          Your plan allows up to &ldquo;Read and drafts&rdquo;, so that&rsquo;s what applies now.{" "}
          <Link className="font-medium text-brand-fg underline underline-offset-4" href={BILLING_HREF(workspace.slug)}>
            See plans
          </Link>
        </p>
      ) : null}
    </SettingsCard>
  );
}

function ConnectionsCard() {
  const workspace = useCurrentWorkspace();
  const list = useAiConnections(workspace.id);
  const revokeAll = useRevokeAllAiConnections(workspace.id);
  const [confirmAll, setConfirmAll] = useState(false);
  const items = list.data?.items ?? [];
  const manages = list.data?.can_manage_all ?? false;

  return (
    <SettingsCard
      id="ai-apps"
      icon={<Plug />}
      title={manages ? "Connected apps" : "Your connected apps"}
      description={
        manages
          ? "Every AI app a member has connected to this workspace. Disconnect stops it at once."
          : "The AI apps you've connected to this workspace. Owners and admins can see these too."
      }
      aside={
        manages && items.length > 0 ? (
          <Button variant="destructive-ghost" onClick={() => setConfirmAll(true)}>
            <Trash2 aria-hidden /> Disconnect all
          </Button>
        ) : null
      }
    >
      {list.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : list.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load connected apps. Try again in a moment.</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          No AI apps are connected. Add Amplychat to Claude, ChatGPT or Codex with the{" "}
          <Link className="font-medium text-brand-fg underline underline-offset-4" href={siteHref(SETUP_GUIDE_PATH) as Route}>
            setup guide
          </Link>
          . API keys for Claude Code and Codex are in Settings › Integrations.
        </p>
      ) : (
        <ul className="divide-y divide-line-subtle" aria-label="Connected AI apps">
          {items.map((item) => (
            <ConnectionRow key={item.id} connection={item} />
          ))}
        </ul>
      )}
      <AlertDialog open={confirmAll} onOpenChange={setConfirmAll}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect every AI app?</AlertDialogTitle>
            <AlertDialogDescription>
              Every connected app in this workspace stops working at once, for every member. Each one has to connect again to
              come back. API keys aren&rsquo;t affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep them</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                revokeAll.mutate(undefined, {
                  onSuccess: (done) => toast.success(`Disconnected ${done.revoked} ${done.revoked === 1 ? "app" : "apps"}`),
                  onError: (error) => toastError(error),
                })
              }
            >
              Disconnect all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsCard>
  );
}

function ConnectionRow({ connection }: { connection: AiConnection }) {
  const workspace = useCurrentWorkspace();
  const revoke = useRevokeAiConnection(workspace.id);
  const [confirming, setConfirming] = useState(false);
  const [open, setOpen] = useState(false);
  const activity = useAiConnectionActivity(workspace.id, connection.id, open);
  const who = connection.is_yours ? "You" : connection.member.name || connection.member.email;
  const calls = open ? (activity.data?.items ?? connection.recent_calls) : connection.recent_calls;

  return (
    <li data-testid="ai-connection" className="space-y-3 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            <Bot className="size-4 text-fg-secondary" aria-hidden />
            <span className="break-all">{connection.client_name}</span>
            {connection.verified_host ? (
              <Badge tone="neutral" title="This app's details come from its own website">
                {connection.verified_host}
              </Badge>
            ) : null}
          </p>
          <p className="text-xs text-fg-secondary">
            {who} · connected {relativeTime(connection.created_at)} ·{" "}
            {connection.last_used_at ? `last used ${relativeTime(connection.last_used_at)}` : "not used yet"} ·{" "}
            {connection.calls_7d} {connection.calls_7d === 1 ? "call" : "calls"} in 7 days
          </p>
          <div className="flex flex-wrap gap-1.5" aria-label={`What ${connection.client_name} may do`}>
            {connection.scopes.map((scope) => (
              <Badge key={scope} tone="neutral" shape="tag" title={scope}>
                {SCOPE_WORDS[scope] ?? scope}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={open}
            aria-controls={`activity-${connection.id}`}
            onClick={() => setOpen((value) => !value)}
          >
            <Activity aria-hidden /> {open ? "Hide activity" : "Activity"}
          </Button>
          <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
            <Trash2 aria-hidden /> Disconnect
          </Button>
        </div>
      </div>
      {open || calls.length > 0 ? (
        <div id={`activity-${connection.id}`}>
          {calls.length === 0 ? (
            <p className="text-xs text-fg-secondary">No tool calls yet.</p>
          ) : (
            <ol className="space-y-1" aria-label={`Recent activity of ${connection.client_name}`}>
              {calls.map((call) => (
                <li key={call.id} className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge tone={OUTCOME[call.outcome].tone}>{OUTCOME[call.outcome].label}</Badge>
                  <code className="font-mono">{call.tool}</code>
                  <span className="text-fg-secondary">{relativeTime(call.created_at)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect {connection.client_name}?</AlertDialogTitle>
            <AlertDialogDescription>
              It stops working on its next request. To use it again, connect it again from the app.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                revoke.mutate(connection.id, {
                  onSuccess: () => toast.success(`${connection.client_name} disconnected`),
                  onError: (error) => toastError(error),
                })
              }
            >
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}
