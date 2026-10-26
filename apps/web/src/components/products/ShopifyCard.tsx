"use client";

import { RefreshCw, ShoppingBag, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { SettingsCard } from "@/components/settings/SettingsCard";
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
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import {
  useCompleteShopifyConnect,
  useDisconnectShopify,
  useShopify,
  useStartShopifyConnect,
  useSyncShopify,
} from "@/lib/api/queries";
import type { ShopifyStatus } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/** What the callback's ?error= means, in plain words. */
const CALLBACK_ERRORS: Record<string, string> = {
  access_denied: "Shopify wasn't connected: you cancelled it.",
  connect_failed: "Shopify didn't respond. Try connecting again.",
};

/** The reasons the API refuses the nonce, in the screen's words. */
function completeMessage(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.status === 404) return "That connection link expired. Connect Shopify again.";
  if (error.status === 403)
    return "This Shopify connection was started by someone else, so it wasn't added. To connect your own store, use Connect Shopify.";
  if (error.status === 409) return error.detail ?? "That store is connected to another workspace.";
  return null;
}

/**
 * Products, Shopify (GR-31): connect a store, copy its products, and keep them in step through
 * Shopify's webhooks. It stays off until the Shopify app is set up on the server (the owner's
 * Partner account), and the plan must include the catalogue. Disconnecting removes the products the
 * store made, unless asked to keep them, because their prices would no longer be kept up to date.
 */
export function ShopifyCard({ wid }: { wid: string }) {
  const status = useShopify(wid);
  useShopifyReturn(wid);

  return (
    <SettingsCard
      id="shopify"
      icon={<ShoppingBag />}
      title="Shopify"
      description="Copy your store's products, with variants, prices and stock, and keep them up to date."
      aside={status.data ? <ConnectionBadge status={status.data} /> : undefined}
    >
      {status.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : status.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load Shopify. Reload the page to try again.</p>
      ) : (
        <Body wid={wid} status={status.data} />
      )}
    </SettingsCard>
  );
}

/** The OAuth callback sends the browser back with ?shopify=<nonce> (finish once) or ?error=. */
function useShopifyReturn(wid: string) {
  const params = useSearchParams();
  const complete = useCompleteShopifyConnect(wid);
  const { mutate: finish } = complete;
  const handled = useRef(false);
  const nonce = params?.get("shopify") ?? null;
  const error = params?.get("error") ?? null;

  useEffect(() => {
    if (handled.current || (!nonce && !(error && error in CALLBACK_ERRORS))) return;
    handled.current = true;
    window.history.replaceState(null, "", window.location.pathname); // a refresh repeats nothing
    if (!nonce) {
      toast.error(CALLBACK_ERRORS[error ?? ""]);
      return;
    }
    finish(nonce, {
      onSuccess: () => toast.success("Shopify connected. Your products are being copied."),
      onError: (failure) => {
        const message = completeMessage(failure);
        if (message) toast.error(message);
        else toastError(failure, "Shopify didn't respond. Try connecting again.");
      },
    });
  }, [nonce, error, finish]);
}

function ago(iso: string): string {
  const short = relativeTime(iso);
  return short === "now" ? "just now" : `${short} ago`;
}

function ConnectionBadge({ status }: { status: ShopifyStatus }) {
  if (!status.connected) return <Badge tone="neutral">Not connected</Badge>;
  if (status.status === "needs_reconnect") return <Badge tone="danger">Reconnect needed</Badge>;
  if (status.syncing) return <Badge tone="brand">Syncing</Badge>;
  return <Badge tone="success">Connected</Badge>;
}

function Body({ wid, status }: { wid: string; status: ShopifyStatus }) {
  const workspace = useCurrentWorkspace();
  const upgrade = useUpgradeDialog();
  if (!status.available) {
    return <p className="text-sm text-fg-secondary">Shopify isn&rsquo;t set up on this server yet.</p>;
  }
  if (!status.entitled) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-secondary">
          The product catalogue, with Shopify import, is part of Pro.
        </p>
        {workspace.role === "agent" ? null : (
          <Button type="button" variant="secondary" size="sm" onClick={() => upgrade.open(COMMERCE_UPGRADE)}>
            See plans
          </Button>
        )}
      </div>
    );
  }
  if (!status.connected) return <Connect wid={wid} />;
  return <Connected wid={wid} status={status} />;
}

function Connect({ wid, reconnect = false, shop = "" }: { wid: string; reconnect?: boolean; shop?: string }) {
  const start = useStartShopifyConnect(wid);
  const [text, setText] = useState(shop);
  const [problem, setProblem] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    start.mutate(text.trim(), {
      onSuccess: (url) => browser.assign(url),
      onError: (error) => {
        const field = error instanceof ApiError ? error.errors.find((item) => item.field === "shop") : undefined;
        if (field) setProblem(field.message);
        else toastError(error);
      },
    });
  }

  return (
    <form className="space-y-2" onSubmit={submit}>
      {reconnect ? null : (
        <p className="text-sm text-fg-secondary">
          Amplychat asks for read access to your products only. It never changes your store.
        </p>
      )}
      <Field id="shopify-store" invalid={Boolean(problem)}>
        <FieldLabel>Your store&rsquo;s address</FieldLabel>
        <Input
          maxLength={100}
          placeholder="my-store.myshopify.com"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <FieldDescription>The one ending in .myshopify.com, even if customers see another address.</FieldDescription>
        <FieldError>{problem}</FieldError>
      </Field>
      <Button type="submit" loading={start.isPending} disabled={!text.trim()}>
        {reconnect ? "Reconnect Shopify" : "Connect Shopify"}
      </Button>
    </form>
  );
}

function Connected({ wid, status }: { wid: string; status: ShopifyStatus }) {
  const sync = useSyncShopify(wid);
  const [confirming, setConfirming] = useState(false);
  const needsReconnect = status.status === "needs_reconnect";
  const name = status.shop_name ? `${status.shop_name} (${status.shop_domain})` : status.shop_domain;

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-secondary">
        Connected to {name}.{" "}
        {status.syncing
          ? "Copying products now."
          : status.synced_at
            ? `${status.products_synced} ${status.products_synced === 1 ? "product" : "products"} copied ${ago(status.synced_at)}.`
            : "No sync has finished yet."}
      </p>
      {needsReconnect ? (
        <div className="space-y-2">
          <Alert tone="danger" urgent>
            {status.sync_error ?? status.last_error ?? "Access was removed in Shopify. Reconnect to keep your products in step."}
          </Alert>
          <Connect wid={wid} reconnect shop={status.shop_domain ?? ""} />
        </div>
      ) : (
        <>
          {status.sync_error ? <Alert tone="warning">{status.sync_error}</Alert> : null}
          {status.last_error ? <Alert tone="warning">{status.last_error}</Alert> : null}
          <p className="text-xs text-fg-secondary">
            Changes in Shopify reach the catalogue in a moment. Prices, stock and links here follow your store, so edit
            them there.
          </p>
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {needsReconnect ? null : (
          <Button
            variant="secondary"
            size="sm"
            disabled={status.syncing}
            loading={sync.isPending}
            onClick={() =>
              sync.mutate(undefined, {
                onSuccess: () => toast.success("Copying your products again."),
                onError: (error) => toastError(error),
              })
            }
          >
            <RefreshCw aria-hidden /> Sync now
          </Button>
        )}
        <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
          <Trash2 aria-hidden /> Disconnect
        </Button>
      </div>
      <Disconnect wid={wid} open={confirming} onOpenChange={setConfirming} />
    </div>
  );
}

function Disconnect({ wid, open, onOpenChange }: { wid: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const disconnect = useDisconnectShopify(wid);
  const [keep, setKeep] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect Shopify?</AlertDialogTitle>
          <AlertDialogDescription>
            Amplychat stops copying products. The products it copied are removed, because their prices and stock would
            no longer be kept up to date, unless you keep them.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Field id="shopify-keep" orientation="horizontal">
          <Checkbox checked={keep} onCheckedChange={(value) => setKeep(value === true)} />
          <FieldLabel className="font-normal">Keep the products I already have</FieldLabel>
        </Field>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() =>
              disconnect.mutate(
                { keepProducts: keep },
                {
                  onSuccess: () => toast.success("Shopify disconnected."),
                  onError: (error) => toastError(error),
                },
              )
            }
          >
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
