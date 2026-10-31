"use client";

import { AlertTriangle, Bot, Check, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { LogoMark } from "@/components/marketing/primitives";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ApiError } from "@/lib/api/errors";
import { useApproveConnect, useConnectRequest, useDenyConnect } from "@/lib/api/queries";
import type { ConnectRequest, ConnectWorkspace } from "@/lib/api/types";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";

const ROLE = { owner: "Owner", admin: "Admin", agent: "Agent" } as const;
const PLAN: Record<string, string> = { free: "Free", pro: "Pro", max: "Max" };

/** Sends the browser on to the AI app. A seam so tests can watch it. */
export const navigate = { to: (url: string) => window.location.assign(url) };

/**
 * The AI app consent page (C-165 phase C; 01-design.md §3.5), at /connect/authorize?request=…,
 * signed in with the member's Clerk session. It names the app (its metadata document's host when
 * it has one, else "not verified") and where the browser goes back to, lists what the app asked
 * for in plain words (each group can be unticked), and lets the member pick one workspace. Allow
 * and Deny both go back to the app: with a code, or with access_denied.
 */
export function ConsentPage() {
  const params = useSearchParams();
  const id = params.get("request") ?? "";
  const request = useConnectRequest(id);

  if (!id) return <Expired />;
  if (request.isPending) return <PageSkeleton fullPage />;
  if (request.isError) {
    if (request.error instanceof ApiError && request.error.status === 404) return <Expired />;
    return <ErrorState fullPage error={request.error} onRetry={() => void request.refetch()} />;
  }
  return <Consent id={id} request={request.data} />;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main id="main" className="grid min-h-dvh place-items-start justify-center bg-canvas px-4 py-10 md:place-items-center">
      <div className="w-full max-w-lg space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <LogoMark className="size-7" /> Amplychat
        </div>
        {children}
      </div>
    </main>
  );
}

function Expired() {
  return (
    <Shell>
      <Card padding="roomy" className="space-y-2">
        <h1 className="text-xl font-semibold">This request has expired</h1>
        <p className="text-sm text-fg-secondary">
          Sign-in requests last 10 minutes and can be answered once. Start connecting again from your AI app.
        </p>
      </Card>
    </Shell>
  );
}

function Consent({ id, request }: { id: string; request: ConnectRequest }) {
  const approve = useApproveConnect(id);
  const deny = useDenyConnect(id);
  const firstOpen = request.workspaces.find((w) => w.can_connect);
  const [workspaceId, setWorkspaceId] = useState(firstOpen?.id ?? "");
  const [unticked, setUnticked] = useState<Set<string>>(new Set());
  const workspace = request.workspaces.find((w) => w.id === workspaceId);
  const scopes = useMemo(
    () => request.groups.filter((g) => !unticked.has(g.id)).flatMap((g) => g.scopes.map((s) => s.scope)),
    [request.groups, unticked],
  );
  const busy = approve.isPending || deny.isPending;
  const app = request.client.name;

  function allow() {
    approve.mutate(
      { workspace_id: workspaceId, scopes },
      { onSuccess: (done) => navigate.to(done.redirect_to), onError: (error) => toastError(error) },
    );
  }

  function cancel() {
    deny.mutate(undefined, { onSuccess: (done) => navigate.to(done.redirect_to), onError: (error) => toastError(error) });
  }

  return (
    <Shell>
      <Card padding="roomy" className="space-y-6">
        <header className="flex items-start gap-3">
          <ClientMark request={request} />
          <div className="min-w-0 space-y-1">
            <h1 className="text-xl font-semibold text-balance">
              {app} wants to connect to Amplychat
            </h1>
            <p className="text-sm text-fg-secondary">
              Signed in as {request.member.email} · Goes back to{" "}
              <span className="font-medium text-fg">{request.client.redirect_host}</span>
            </p>
            <p className="text-xs text-fg-secondary">
              {request.client.verified_host ? (
                <>Details from {request.client.verified_host}</>
              ) : (
                <>This app registered itself; Amplychat hasn&rsquo;t checked its name.</>
              )}
            </p>
          </div>
        </header>

        {request.client.loopback ? (
          <p role="note" className="flex gap-2 rounded-lg bg-warning-soft p-3 text-sm text-warning">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              This app runs on a computer, not a website. Only allow it if you started the connection on this computer.
            </span>
          </p>
        ) : null}

        <WorkspacePicker workspaces={request.workspaces} value={workspaceId} onChange={setWorkspaceId} />

        <fieldset className="space-y-3">
          <legend className="mb-1 text-sm font-medium">{app} will be able to</legend>
          <p className="flex gap-2 text-sm">
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            {request.always}
          </p>
          {request.groups.map((group) => {
            const checked = !unticked.has(group.id);
            const boxId = `scope-${group.id}`;
            return (
              <div key={group.id} className="flex gap-3">
                <Checkbox
                  id={boxId}
                  checked={checked}
                  aria-describedby={`${boxId}-what`}
                  onCheckedChange={(value) =>
                    setUnticked((current) => {
                      const next = new Set(current);
                      if (value === true) next.delete(group.id);
                      else next.add(group.id);
                      return next;
                    })
                  }
                  className="mt-0.5"
                />
                <div className="min-w-0">
                  <label htmlFor={boxId} className="text-sm font-medium">
                    {group.label}
                  </label>
                  <ul id={`${boxId}-what`} className="list-disc space-y-0.5 pl-4 text-sm text-fg-secondary">
                    {group.scopes.map((scope) => (
                      <li key={scope.scope}>{scope.description}</li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </fieldset>

        <p className="flex gap-2 text-xs text-fg-secondary">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {app} acts as you, and can&rsquo;t do anything your role
            {workspace ? ` (${ROLE[workspace.role]})` : ""} doesn&rsquo;t allow. You can disconnect it any time in Settings ›
            Connected AI apps. Messages and comments it reads are sent to {app}&rsquo;s provider under their terms.
          </span>
        </p>

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={cancel} loading={deny.isPending} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={allow} loading={approve.isPending} disabled={busy || !workspace?.can_connect}>
            Allow
          </Button>
        </div>
      </Card>
    </Shell>
  );
}

function ClientMark({ request }: { request: ConnectRequest }) {
  const [broken, setBroken] = useState(false);
  if (request.client.logo_url && !broken) {
    return (
      // A third party's logo from its own metadata document's host (the API shows no other):
      // a plain img, no referrer, fixed size, nothing but the picture.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={request.client.logo_url}
        alt=""
        width={40}
        height={40}
        referrerPolicy="no-referrer"
        className="size-10 shrink-0 rounded-lg border border-line object-contain"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-raised text-fg-secondary" aria-hidden>
      <Bot className="size-5" />
    </span>
  );
}

function WorkspacePicker({
  workspaces,
  value,
  onChange,
}: {
  workspaces: ConnectWorkspace[];
  value: string;
  onChange: (id: string) => void;
}) {
  if (workspaces.length === 0) {
    return <p className="text-sm text-fg-secondary">You aren&rsquo;t in any workspace yet.</p>;
  }
  return (
    <fieldset className="space-y-2">
      <legend className="mb-1 text-sm font-medium">Workspace</legend>
      {workspaces.map((workspace) => {
        const id = `ws-${workspace.id}`;
        return (
          <label
            key={workspace.id}
            htmlFor={id}
            className={cn(
              "flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm",
              value === workspace.id && "border-brand-line bg-brand-soft",
              !workspace.can_connect && "cursor-not-allowed opacity-70",
            )}
          >
            <input
              id={id}
              type="radio"
              name="connect-workspace"
              value={workspace.id}
              checked={value === workspace.id}
              disabled={!workspace.can_connect}
              aria-describedby={workspace.reason ? `${id}-reason` : undefined}
              onChange={() => onChange(workspace.id)}
              className="accent-brand"
            />
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium break-all">{workspace.name}</span>
                <Badge tone="neutral">{PLAN[workspace.plan] ?? workspace.plan}</Badge>
                <span className="text-xs text-fg-secondary">{ROLE[workspace.role]}</span>
              </span>
              {workspace.reason ? (
                <span id={`${id}-reason`} className="block text-xs text-fg-secondary">
                  {workspace.reason}
                </span>
              ) : null}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
