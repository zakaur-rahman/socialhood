"use client";

import { AlertTriangle, FlaskConical } from "lucide-react";
import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AUTO_UPGRADE } from "@/components/ai/AiModeControl";
import { AutoConfirmDialog } from "@/components/ai/AiModeDialogs";
import { AccountCard } from "@/components/connections/AccountCard";
import { ConnectWhatsAppButton, useWhatsAppConnect } from "@/components/connections/ConnectWhatsAppButton";
import { FacebookGlyph } from "@/components/connections/FacebookGlyph";
import { FacebookPagesDialog } from "@/components/connections/FacebookPagesDialog";
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
import { Alert, AlertAction, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SearchInput } from "@/components/ui/search-input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError } from "@/lib/api/errors";
import {
  useCompleteInstagramConnect,
  useCreateSandboxAccount,
  useDeleteAccountData,
  useDisconnectAccount,
  useResubscribeAccount,
  useSocialAccounts,
  useStartFacebookConnect,
  useStartInstagramConnect,
  useUpdateAccount,
} from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { useUpgradeDialog } from "@/lib/api/provider";
import { browser } from "@/lib/billing/browser";
import {
  completeConnectResult,
  connectResult,
  emptyStates,
  instagramConnected,
  type ConnectResult,
} from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { useDocumentTitle } from "@/lib/document-title";
import { useCurrentWorkspace } from "@/lib/workspace";

const SANDBOX_TOOLS = process.env.NODE_ENV !== "production";

/**
 * UX-SCR-07 Connections, F-03 (connect Instagram), F-04 (connect WhatsApp), F-05 (reconnect),
 * FR-CON-06 (disconnect). C-066: search and a segmented filter with counts over the list, and
 * two columns of account cards on wide screens. C-067 (amended by D-09): Delete account and data in each card's menu.
 */
export default function ConnectionsPage() {
  useDocumentTitle("Connections");
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
  const connectFacebook = useStartFacebookConnect(wid);
  const update = useUpdateAccount(wid);
  const resubscribe = useResubscribeAccount(wid);
  const disconnect = useDisconnectAccount(wid);
  const deleteData = useDeleteAccountData(wid);
  const sandbox = useCreateSandboxAccount(wid);
  const [connectError, setConnectError] = useState<ConnectFailure | null>(null);
  const whatsapp = useWhatsAppConnect(wid, (message) => setConnectError({ message, retry: "whatsapp" }));
  const upgrade = useUpgradeDialog();
  const [confirmAuto, setConfirmAuto] = useState<SocialAccount | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<AccountFilter>("all");

  const startConnect = useCallback(() => {
    setConnectError(null);
    connect.mutate(undefined, {
      onSuccess: (url) => browser.assign(url),
      // Over accounts_per_platform (402): the upgrade dialog says so.
      onError: (error) => toastError(error),
    });
  }, [connect]);

  // GR-29: Facebook's callback comes back with ?facebook=<nonce>; the Pages dialog lists and connects.
  const startFacebook = useCallback(() => {
    setConnectError(null);
    connectFacebook.mutate(undefined, {
      onSuccess: (url) => browser.assign(url),
      onError: (error) => toastError(error),
    });
  }, [connectFacebook]);
  const [facebookNonce, setFacebookNonce] = useFacebookNonce();

  const finishing = useConnectResult(wid, accounts.data, accounts.isError, setConnectError);

  if (accounts.isPending) return <PageSkeleton rows={2} />;
  if (accounts.isError) return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />;

  const empty = accounts.data.length === 0;
  const failWhatsApp = (message: string) => setConnectError({ message, retry: "whatsapp" });
  const retryConnect = () => {
    const platform = connectError?.retry;
    setConnectError(null);
    if (platform === "whatsapp") whatsapp.connect();
    else if (platform === "facebook") startFacebook();
    else startConnect();
  };
  const connectAlert = connectError ? (
    <Alert
      tone="warning"
      icon={<AlertTriangle />}
      onDismiss={() => setConnectError(null)}
      action={connectError.retry && canManage ? <AlertAction onClick={retryConnect}>Try again</AlertAction> : undefined}
    >
      <AlertDescription>{connectError.message}</AlertDescription>
    </Alert>
  ) : null;

  const addSandbox = (platform: "instagram" | "facebook") =>
    sandbox.mutate(platform, {
      onSuccess: () => toast.success(platform === "facebook" ? "Sandbox Page added" : "Sandbox account added"),
      onError: (error) =>
        toastError(
          error,
          error instanceof ApiError && error.status === 404
            ? "The sandbox is off. Set SANDBOX_PLATFORM_ENABLED=true for the API."
            : undefined,
        ),
    });

  // The empty state carries every Connect button, so the header keeps only the sandbox ones then.
  const connectButtons = canManage ? (
    <>
      {SANDBOX_TOOLS && workspace.role === "owner" ? (
        <>
          <Button variant="ghost" size="lg" loading={sandbox.isPending} onClick={() => addSandbox("instagram")}>
            <FlaskConical aria-hidden />
            Add sandbox account
          </Button>
          <Button variant="ghost" size="lg" loading={sandbox.isPending} onClick={() => addSandbox("facebook")}>
            <FlaskConical aria-hidden />
            Add sandbox Page
          </Button>
        </>
      ) : null}
      {empty ? null : (
        <>
          <ConnectWhatsAppButton wid={wid} onFailure={failWhatsApp} />
          <Button size="lg" loading={connectFacebook.isPending} onClick={startFacebook}>
            <FacebookGlyph className="size-4" />
            Connect Facebook
          </Button>
          <Button size="lg" loading={connect.isPending || finishing} onClick={startConnect}>
            <InstagramGlyph className="size-4" />
            Connect Instagram
          </Button>
        </>
      )}
    </>
  ) : null;

  const counts = filterCounts(accounts.data, query);
  const shown = visibleAccounts(accounts.data, filter, query);

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Connections"
          description="The Instagram, Facebook and WhatsApp accounts this workspace uses, and how the AI works on each."
          actions={connectButtons}
        />
      }
    >
      {connectAlert}
      {empty ? (
        <Card>
          <EmptyState
            title={emptyStates.connections.title}
            body={emptyStates.connections.body}
            icon={<InstagramGlyph className="size-8" />}
            action={
              canManage ? (
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <Button size="xl" loading={connect.isPending || finishing} onClick={startConnect}>
                    <InstagramGlyph className="size-4" />
                    Connect Instagram
                  </Button>
                  <Button size="xl" loading={connectFacebook.isPending} onClick={startFacebook}>
                    <FacebookGlyph className="size-4" />
                    Connect Facebook
                  </Button>
                  <ConnectWhatsAppButton wid={wid} size="xl" onFailure={failWhatsApp} />
                </div>
              ) : (
                <p className="text-sm text-fg-secondary">Ask an owner or admin to connect an account.</p>
              )
            }
          />
        </Card>
      ) : (
        <>
          <Card className="flex flex-col gap-2 p-2 lg:flex-row lg:items-center">
            <SearchInput
              label="Search accounts"
              placeholder="Search by name, handle or number"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              size="xl"
              className="flex-1"
            />
            {/* `default` beside the 40 px search: its track is 40 px outside, so the edges line up (C-073).
                Below lg it is a row of its own that scrolls on phones, with the edge fade (UI-ISS-058). */}
            <ToggleGroup
              value={filter}
              onValueChange={(value) => setFilter(value as AccountFilter)}
              aria-label="Show accounts"
              className="mask-fade-x overflow-x-auto pe-4 scroll-pe-4 lg:w-auto lg:mask-none lg:pe-1 lg:scroll-pe-0"
            >
              {ACCOUNT_FILTERS.map((option) => (
                <ToggleGroupItem key={option.value} value={option.value} className="shrink-0">
                  {option.label}
                  <span className="text-xs text-fg-secondary tabular-nums">{counts[option.value]}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </Card>
          {shown.length === 0 ? (
            <Card>
              <EmptyState
                title="No accounts match"
                body="Try another search or filter."
                action={
                  <Button
                    variant="secondary"
                    size="xl"
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                    }}
                  >
                    Show all accounts
                  </Button>
                }
              />
            </Card>
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
                    reconnecting:
                      account.platform === "whatsapp"
                        ? whatsapp.busy
                        : account.platform === "facebook"
                          ? connectFacebook.isPending
                          : connect.isPending,
                    retrying: resubscribe.isPending && resubscribe.variables === account.id,
                    disconnecting: disconnect.isPending && disconnect.variables?.id === account.id,
                    deleting: deleteData.isPending && deleteData.variables?.id === account.id,
                  }}
                  actions={{
                    onChange: (patch) =>
                      // F-09: Auto is confirmed first, with the escalation rules; on Free it
                      // opens the upgrade dialog instead (UI-061).
                      patch.ai_mode === "auto"
                        ? workspace.plan === "free"
                          ? upgrade.open(AUTO_UPGRADE)
                          : setConfirmAuto(account)
                        : update.mutate(
                            { id: account.id, patch },
                            {
                              // A 402 opens the upgrade dialog by itself (lib/api/provider.tsx).
                              onError: (error) => toastError(error),
                            },
                          ),
                    onReconnect:
                      account.platform === "whatsapp"
                        ? whatsapp.connect
                        : account.platform === "facebook"
                          ? startFacebook
                          : startConnect,
                    onRetrySubscribe: () =>
                      resubscribe.mutate(account.id, {
                        onSuccess: (saved) =>
                          saved?.status === "active"
                            ? toast.success("Subscribed to messages")
                            : toast.error(saved?.last_error ?? "Couldn't subscribe to messages. Try again."),
                        onError: (error) => toastError(error),
                      }),
                    onDisconnect: () =>
                      disconnect.mutate(
                        { id: account.id },
                        {
                          onSuccess: () => toast.success(`${handleOf(account)} disconnected`),
                          onError: (error) => toastError(error),
                        },
                      ),
                    // C-067: the dialog stays open on a refusal; a typed-handle mismatch shows
                    // under its field, anything else as a toast.
                    onDelete: async (confirm, mode) => {
                      try {
                        await deleteData.mutateAsync({ id: account.id, confirm, mode });
                      } catch (error) {
                        if (!isConfirmError(error)) toastError(error);
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
      <FacebookPagesDialog key={facebookNonce ?? "closed"} wid={wid} nonce={facebookNonce} onClose={() => setFacebookNonce(null)} />
      <AutoConfirmDialog
        open={Boolean(confirmAuto)}
        onOpenChange={(open) => (open ? undefined : setConfirmAuto(null))}
        target={confirmAuto ? handleOf(confirmAuto) : "this account"}
        onConfirm={() => {
          if (confirmAuto) {
            update.mutate(
              { id: confirmAuto.id, patch: { ai_mode: "auto" } },
              {
                onError: (error) => toastError(error),
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

/** UI-061: the last connect error, shown inline until dismissed; `retry` is the platform to try again. */
type ConnectFailure = { message: string; retry: "instagram" | "facebook" | "whatsapp" | null };

function showConnectResult(
  result: ConnectResult | null,
  fail: (failure: ConnectFailure) => void,
  platform: "instagram" | "facebook" = "instagram",
) {
  if (result?.kind === "success") toast.success(result.message);
  else if (result) fail({ message: result.message, retry: result.retry ? platform : null });
}

/**
 * GR-29: Facebook's callback redirects here with ?facebook=<nonce> (X-1, as for Instagram). The
 * page opens with it, so the dialog takes the nonce at once; the parameter is dropped straight away
 * so a refresh doesn't open the dialog again.
 */
function useFacebookNonce() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [nonce, setNonce] = useState<string | null>(() => params.get("facebook"));
  const dropped = useRef(false);

  useEffect(() => {
    if (dropped.current || !params.has("facebook")) return;
    dropped.current = true;
    router.replace(pathname as Route, { scroll: false });
  }, [params, router, pathname]);

  return [nonce, setNonce] as const;
}

/**
 * The OAuth callback redirects here with ?instagram=<nonce> (X-1: the page, signed in, finishes
 * the connect; the callback never does) or ?error=…. Post the nonce once, show the toast once,
 * and drop the parameters straight away so a refresh repeats neither. ?connected=instagram is
 * still understood (a link from before X-1); that toast waits for the list to name the account.
 */
function useConnectResult(
  wid: string,
  accounts: SocialAccount[] | undefined,
  failed: boolean,
  fail: (failure: ConnectFailure) => void,
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
    const platform = params.get("platform") === "facebook" ? "facebook" : "instagram";
    if (!nonce && params.has("connected") && accounts === undefined && !failed) return;
    shown.current = true;
    router.replace(pathname as Route, { scroll: false });
    if (nonce) {
      finish(nonce, {
        onSuccess: (account) => showConnectResult(instagramConnected(account.username), fail),
        onError: (error) => showConnectResult(completeConnectResult(error), fail),
      });
      return;
    }
    const newest = [...(accounts ?? [])]
      .filter((a) => a.connected_at)
      .sort((a, b) => (b.connected_at ?? "").localeCompare(a.connected_at ?? ""))[0];
    showConnectResult(connectResult(new URLSearchParams(params.toString()), newest?.username), fail, platform);
  }, [params, accounts, failed, fail, router, pathname, finish]);

  return complete.isPending;
}
