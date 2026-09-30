"use client";

import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AutoConfirmDialog } from "@/components/ai/AiModeDialogs";
import { AccountCard } from "@/components/connections/AccountCard";
import { ConnectWhatsAppButton, useWhatsAppConnect } from "@/components/connections/ConnectWhatsAppButton";
import { InstagramGlyph } from "@/components/connections/InstagramGlyph";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Button } from "@/components/ui/button";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import {
  useCreateSandboxAccount,
  useDisconnectAccount,
  useResubscribeAccount,
  useSocialAccounts,
  useStartInstagramConnect,
  useUpdateAccount,
} from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { connectResult, emptyStates, errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

const SANDBOX_TOOLS = process.env.NODE_ENV !== "production";

/** UX-SCR-07 Connections, F-03 (connect Instagram), F-04 (connect WhatsApp), F-05 (reconnect), FR-CON-06 (disconnect). */
export default function ConnectionsPage() {
  return (
    <Suspense fallback={<PageSkeleton rows={2} />}>
      <Connections />
    </Suspense>
  );
}

function Connections() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const canManage = workspace.role !== "agent";
  const accounts = useSocialAccounts(wid);
  const connect = useStartInstagramConnect(wid);
  const update = useUpdateAccount(wid);
  const resubscribe = useResubscribeAccount(wid);
  const disconnect = useDisconnectAccount(wid);
  const sandbox = useCreateSandboxAccount(wid);
  const whatsapp = useWhatsAppConnect(wid);
  const [confirmAuto, setConfirmAuto] = useState<SocialAccount | null>(null);

  const startConnect = useCallback(() => {
    connect.mutate(undefined, {
      onSuccess: (url) => window.location.assign(url),
      onError: (error) => toast.error(errorMessage(error)),
    });
  }, [connect]);

  useConnectResultToast(accounts.data, accounts.isError, startConnect);

  if (accounts.isPending) return <PageSkeleton rows={2} />;
  if (accounts.isError) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />;

  const connectButtons = canManage ? (
    <>
      {SANDBOX_TOOLS && workspace.role === "owner" ? (
        <Button
          variant="ghost"
          size="sm"
          disabled={sandbox.isPending}
          onClick={() =>
            sandbox.mutate(undefined, {
              onSuccess: () => toast.success("Sandbox account added"),
              onError: (error) =>
                toast.error(
                  error instanceof ApiError && error.status === 404
                    ? "The sandbox is off. Set SANDBOX_PLATFORM_ENABLED=true for the API."
                    : errorMessage(error),
                ),
            })
          }
        >
          Add sandbox account
        </Button>
      ) : null}
      <ConnectWhatsAppButton wid={wid} />
      <Button className="bg-brand-gradient text-white" disabled={connect.isPending} onClick={startConnect}>
        <InstagramGlyph className="size-4" />
        {connect.isPending ? "Opening Instagram…" : "Connect Instagram"}
      </Button>
    </>
  ) : null;

  return (
    <PageFrame title="Connections" actions={connectButtons}>
      {accounts.data.length === 0 ? (
        <div className="rounded-xl border border-line bg-panel">
          <EmptyState
            title={emptyStates.connections.title}
            body={emptyStates.connections.body}
            icon={<InstagramGlyph className="size-8" />}
            action={
              canManage ? (
                <Button className="bg-brand-gradient text-white" disabled={connect.isPending} onClick={startConnect}>
                  Connect Instagram
                </Button>
              ) : (
                <p className="text-sm text-fg-secondary">Ask an owner or admin to connect an account.</p>
              )
            }
          />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {accounts.data.map((account) => (
            <AccountCard
              key={account.id}
              account={account}
              plan={workspace.plan}
              canManage={canManage}
              busy={{
                saving: update.isPending && update.variables?.id === account.id,
                reconnecting: account.platform === "whatsapp" ? whatsapp.busy : connect.isPending,
                retrying: resubscribe.isPending && resubscribe.variables === account.id,
                disconnecting: disconnect.isPending && disconnect.variables?.id === account.id,
              }}
              actions={{
                onChange: (patch) =>
                  // F-09: Auto is confirmed first, with the escalation rules.
                  patch.ai_mode === "auto"
                    ? setConfirmAuto(account)
                    : update.mutate(
                        { id: account.id, patch },
                        {
                          // A 402 opens the upgrade dialog by itself (lib/api/provider.tsx).
                          onError: (error) => (isPlanLimitError(error) ? undefined : toast.error(errorMessage(error))),
                        },
                      ),
                onReconnect: account.platform === "whatsapp" ? whatsapp.connect : startConnect,
                onRetrySubscribe: () =>
                  resubscribe.mutate(account.id, {
                    onSuccess: (saved) =>
                      saved?.status === "active"
                        ? toast.success("Subscribed to messages")
                        : toast.error(saved?.last_error ?? "Couldn't subscribe to messages. Try again."),
                    onError: (error) => toast.error(errorMessage(error)),
                  }),
                onDisconnect: (deleteData) =>
                  disconnect.mutate(
                    { id: account.id, deleteData },
                    {
                      onSuccess: () => toast.success(`${handleOf(account)} disconnected`),
                      onError: (error) => toast.error(errorMessage(error)),
                    },
                  ),
              }}
            />
          ))}
        </div>
      )}
      <AutoConfirmDialog
        open={Boolean(confirmAuto)}
        onOpenChange={(open) => (open ? undefined : setConfirmAuto(null))}
        target={confirmAuto ? handleOf(confirmAuto) : "this account"}
        onConfirm={() => {
          if (confirmAuto) {
            update.mutate(
              { id: confirmAuto.id, patch: { ai_mode: "auto" } },
              {
                onError: (error) => (isPlanLimitError(error) ? undefined : toast.error(errorMessage(error))),
              },
            );
          }
          setConfirmAuto(null);
        }}
      />
    </PageFrame>
  );
}

function handleOf(account: SocialAccount): string {
  return account.username ? `@${account.username}` : (account.display_name ?? "Account");
}

/**
 * The OAuth callback redirects here with ?connected=instagram or ?error=…; show the toast once,
 * then drop the parameters so a refresh does not repeat it. Success waits for the account list
 * so the toast can name the account.
 */
function useConnectResultToast(
  accounts: SocialAccount[] | undefined,
  failed: boolean,
  retry: () => void,
) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const shown = useRef(false);

  useEffect(() => {
    if (shown.current || !(params.has("connected") || params.has("error"))) return;
    if (params.has("connected") && accounts === undefined && !failed) return;
    shown.current = true;
    const newest = [...(accounts ?? [])]
      .filter((a) => a.connected_at)
      .sort((a, b) => (b.connected_at ?? "").localeCompare(a.connected_at ?? ""))[0];
    const result = connectResult(new URLSearchParams(params.toString()), newest?.username);
    if (result?.kind === "success") toast.success(result.message);
    else if (result) {
      toast.error(result.message, result.retry ? { action: { label: "Try again", onClick: retry } } : undefined);
    }
    router.replace(pathname as Route, { scroll: false });
  }, [params, accounts, failed, retry, router, pathname]);
}
