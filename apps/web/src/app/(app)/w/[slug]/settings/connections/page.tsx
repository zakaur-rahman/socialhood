"use client";

import { FlaskConical, Search } from "lucide-react";
import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AutoConfirmDialog } from "@/components/ai/AiModeDialogs";
import { AccountCard } from "@/components/connections/AccountCard";
import { ConnectWhatsAppButton, useWhatsAppConnect } from "@/components/connections/ConnectWhatsAppButton";
import {
  ACCOUNT_FILTERS,
  filterCounts,
  visibleAccounts,
  type AccountFilter,
} from "@/components/connections/filters";
import { InstagramGlyph } from "@/components/connections/InstagramGlyph";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import {
  useCompleteInstagramConnect,
  useCreateSandboxAccount,
  useDeleteAccountData,
  useDisconnectAccount,
  useResubscribeAccount,
  useSocialAccounts,
  useStartInstagramConnect,
  useUpdateAccount,
} from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import {
  completeConnectResult,
  connectResult,
  emptyStates,
  errorMessage,
  instagramConnected,
  type ConnectResult,
} from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const SANDBOX_TOOLS = process.env.NODE_ENV !== "production";

/**
 * UX-SCR-07 Connections, F-03 (connect Instagram), F-04 (connect WhatsApp), F-05 (reconnect),
 * FR-CON-06 (disconnect). C-066: search and a segmented filter with counts over the list, and
 * two columns of account cards on wide screens. C-067: Disconnect and delete data, and Remove.
 */
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
  const deleteData = useDeleteAccountData(wid);
  const sandbox = useCreateSandboxAccount(wid);
  const whatsapp = useWhatsAppConnect(wid);
  const [confirmAuto, setConfirmAuto] = useState<SocialAccount | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<AccountFilter>("all");

  const startConnect = useCallback(() => {
    connect.mutate(undefined, {
      onSuccess: (url) => browser.assign(url),
      // Over accounts_per_platform (402): the upgrade dialog says so.
      onError: (error) => toastError(error),
    });
  }, [connect]);

  const finishing = useConnectResultToast(wid, accounts.data, accounts.isError, startConnect);

  if (accounts.isPending) return <PageSkeleton rows={2} />;
  if (accounts.isError) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />;

  const connectButtons = canManage ? (
    <>
      {SANDBOX_TOOLS && workspace.role === "owner" ? (
        <Button
          variant="ghost"
          className="min-h-10 px-3 md:min-h-9"
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
          <FlaskConical aria-hidden />
          Add sandbox account
        </Button>
      ) : null}
      <ConnectWhatsAppButton wid={wid} />
      <Button
        className="bg-brand-gradient min-h-10 px-4 text-white md:min-h-9"
        disabled={connect.isPending || finishing}
        onClick={startConnect}
      >
        <InstagramGlyph className="size-4" />
        {finishing ? "Connecting Instagram…" : connect.isPending ? "Opening Instagram…" : "Connect Instagram"}
      </Button>
    </>
  ) : null;

  const counts = filterCounts(accounts.data, query);
  const shown = visibleAccounts(accounts.data, filter, query);

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          label="Channels"
          title="Connections"
          description="The Instagram and WhatsApp accounts this workspace uses, and how the AI works on each."
          actions={connectButtons}
        />
      }
    >
      {accounts.data.length === 0 ? (
        <div className="rounded-2xl border border-line bg-panel">
          <EmptyState
            title={emptyStates.connections.title}
            body={emptyStates.connections.body}
            icon={<InstagramGlyph className="size-8" />}
            action={
              canManage ? (
                <Button className="bg-brand-gradient min-h-10 text-white" disabled={connect.isPending} onClick={startConnect}>
                  Connect Instagram
                </Button>
              ) : (
                <p className="text-sm text-fg-secondary">Ask an owner or admin to connect an account.</p>
              )
            }
          />
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-2 rounded-2xl border border-line bg-panel p-2 lg:flex-row lg:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary" aria-hidden />
              <Input
                type="search"
                aria-label="Search accounts"
                placeholder="Search by name, handle or number"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-h-10 border-0 bg-field pl-9"
              />
            </div>
            <ToggleGroup
              value={filter}
              onValueChange={(value) => setFilter(value as AccountFilter)}
              aria-label="Show accounts"
              className="overflow-x-auto lg:w-auto"
            >
              {ACCOUNT_FILTERS.map((option) => (
                <ToggleGroupItem key={option.value} value={option.value} className="min-h-9 shrink-0 px-3">
                  {option.label}
                  <span className="text-xs text-fg-secondary tabular-nums">{counts[option.value]}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          {shown.length === 0 ? (
            <div className="rounded-2xl border border-line bg-panel">
              <EmptyState
                title="No accounts match"
                body="Try another search or filter."
                action={
                  <Button
                    variant="secondary"
                    className="min-h-10"
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                    }}
                  >
                    Show all accounts
                  </Button>
                }
              />
            </div>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {shown.map((account) => (
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
                    deleting: deleteData.isPending && deleteData.variables?.id === account.id,
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
                    onDisconnect: () =>
                      disconnect.mutate(
                        { id: account.id },
                        {
                          onSuccess: () => toast.success(`${handleOf(account)} disconnected`),
                          onError: (error) => toast.error(errorMessage(error)),
                        },
                      ),
                    // C-067: the dialog stays open on a refusal; a typed-handle mismatch shows
                    // under its field, anything else as a toast.
                    onDelete: async (confirm, mode) => {
                      try {
                        await deleteData.mutateAsync({ id: account.id, confirm, mode });
                      } catch (error) {
                        if (!isConfirmError(error)) toast.error(errorMessage(error));
                        throw error;
                      }
                      toast.success(`Deleting ${handleOf(account)} and its data`);
                    },
                  }}
                />
              ))}
            </div>
          )}
        </>
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
    </SettingsFrame>
  );
}

function handleOf(account: SocialAccount): string {
  return account.username ? `@${account.username}` : (account.display_name ?? "Account");
}

function isConfirmError(error: unknown): boolean {
  return error instanceof ApiError && error.errors.some((e) => e.field === "confirm");
}

function showConnectResult(result: ConnectResult | null, retry: () => void) {
  if (result?.kind === "success") toast.success(result.message);
  else if (result) {
    toast.error(result.message, result.retry ? { action: { label: "Try again", onClick: retry } } : undefined);
  }
}

/**
 * The OAuth callback redirects here with ?instagram=<nonce> (X-1: the page, signed in, finishes
 * the connect; the callback never does) or ?error=…. Post the nonce once, show the toast once,
 * and drop the parameters straight away so a refresh repeats neither. ?connected=instagram is
 * still understood (a link from before X-1); that toast waits for the list to name the account.
 */
function useConnectResultToast(
  wid: string,
  accounts: SocialAccount[] | undefined,
  failed: boolean,
  retry: () => void,
) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const complete = useCompleteInstagramConnect(wid);
  const { mutate: finish } = complete;
  const shown = useRef(false);

  useEffect(() => {
    if (shown.current || !(params.has("instagram") || params.has("connected") || params.has("error"))) return;
    const nonce = params.get("instagram");
    if (!nonce && params.has("connected") && accounts === undefined && !failed) return;
    shown.current = true;
    router.replace(pathname as Route, { scroll: false });
    if (nonce) {
      finish(nonce, {
        onSuccess: (account) => showConnectResult(instagramConnected(account.username), retry),
        onError: (error) => showConnectResult(completeConnectResult(error), retry),
      });
      return;
    }
    const newest = [...(accounts ?? [])]
      .filter((a) => a.connected_at)
      .sort((a, b) => (b.connected_at ?? "").localeCompare(a.connected_at ?? ""))[0];
    showConnectResult(connectResult(new URLSearchParams(params.toString()), newest?.username), retry);
  }, [params, accounts, failed, retry, router, pathname, finish]);

  return complete.isPending;
}
