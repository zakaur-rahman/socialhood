"use client";

import { MessageCircle, RefreshCw, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import {
  useConnectWaCatalogue,
  useDisconnectWaCatalogue,
  useSocialAccounts,
  useSyncWaCatalogue,
  useWaCatalogue,
} from "@/lib/api/queries";
import type { WaCatalogueStatus } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

function ago(iso: string): string {
  const short = relativeTime(iso);
  return short === "now" ? "just now" : `${short} ago`;
}

/**
 * Products, WhatsApp catalogue (GR-33): copy the products to a Meta commerce catalogue so WhatsApp
 * product and product-list messages can show them, and keep it in step. The catalogue is created
 * and connected to the WhatsApp Business Account in Meta's Commerce Manager and WhatsApp Manager;
 * here the catalogue's id is entered and checked with Meta. Part of Pro (PD-8). Nothing here has run
 * against a real catalogue yet (C-121), and the card says Meta's own reason when it refuses.
 */
export function WhatsAppCatalogueCard({ wid }: { wid: string }) {
  const status = useWaCatalogue(wid);
  return (
    <SettingsCard
      id="whatsapp-catalogue"
      icon={<MessageCircle />}
      title="WhatsApp catalogue"
      description="Send products as WhatsApp product messages, and turn a customer's cart into an order."
      aside={status.data ? <ConnectionBadge status={status.data} /> : undefined}
    >
      {status.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : status.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load the WhatsApp catalogue. Reload the page to try again.</p>
      ) : (
        <Body wid={wid} status={status.data} />
      )}
    </SettingsCard>
  );
}

function ConnectionBadge({ status }: { status: WaCatalogueStatus }) {
  if (!status.connected) return <Badge tone="neutral">Not connected</Badge>;
  if (status.status === "needs_reconnect") return <Badge tone="danger">Needs attention</Badge>;
  if (status.syncing) return <Badge tone="brand">Syncing</Badge>;
  return <Badge tone="success">Connected</Badge>;
}

function Body({ wid, status }: { wid: string; status: WaCatalogueStatus }) {
  const workspace = useCurrentWorkspace();
  const upgrade = useUpgradeDialog();
  if (!status.entitled) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-secondary">WhatsApp product messages are part of Pro.</p>
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

function Connect({ wid, attention = false, catalogId = "" }: { wid: string; attention?: boolean; catalogId?: string }) {
  const accounts = useSocialAccounts(wid);
  const connect = useConnectWaCatalogue(wid);
  const numbers = (accounts.data ?? []).filter((account) => account.platform === "whatsapp");
  const [chosen, setChosen] = useState("");
  const [text, setText] = useState(catalogId);
  const [problem, setProblem] = useState<string | null>(null);
  const accountId = chosen || numbers[0]?.id || "";

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    connect.mutate(
      { social_account_id: accountId, catalog_id: text.trim() },
      {
        onSuccess: () => toast.success("WhatsApp catalogue connected. Your products are being sent."),
        onError: (error) => {
          if (error instanceof ApiError && (error.status === 409 || error.status === 422)) {
            setProblem(error.errors[0]?.message ?? error.detail ?? null);
          } else toastError(error, "Meta didn't respond. Try again.");
        },
      },
    );
  }

  if (accounts.isSuccess && numbers.length === 0) {
    return <p className="text-sm text-fg-secondary">Connect a WhatsApp number first (Settings, Connections).</p>;
  }
  return (
    <form className="space-y-2" onSubmit={submit}>
      {attention ? null : (
        <p className="text-sm text-fg-secondary">
          Create a catalogue in Meta Commerce Manager and connect it to your WhatsApp Business Account in WhatsApp
          Manager. Then enter its id here. Amplychat only adds and updates the items it sends.
        </p>
      )}
      <Field id="wa-catalogue-number">
        <FieldLabel>WhatsApp number</FieldLabel>
        <select
          value={accountId}
          onChange={(event) => setChosen(event.target.value)}
          className="h-9 w-full rounded-lg border border-line-strong bg-field px-2 text-sm"
        >
          {numbers.map((account) => (
            <option key={account.id} value={account.id}>
              {account.display_name ?? account.username ?? account.id}
            </option>
          ))}
        </select>
      </Field>
      <Field id="wa-catalogue-id" invalid={Boolean(problem)}>
        <FieldLabel>Catalogue id</FieldLabel>
        <Input maxLength={40} inputMode="numeric" value={text} onChange={(event) => setText(event.target.value)} />
        <FieldDescription>Find it in Commerce Manager, under Catalogue, Settings.</FieldDescription>
        <FieldError>{problem}</FieldError>
      </Field>
      <Button type="submit" loading={connect.isPending} disabled={!text.trim() || !accountId}>
        {attention ? "Connect again" : "Connect catalogue"}
      </Button>
    </form>
  );
}

function Connected({ wid, status }: { wid: string; status: WaCatalogueStatus }) {
  const sync = useSyncWaCatalogue(wid);
  const disconnect = useDisconnectWaCatalogue(wid);
  const attention = status.status === "needs_reconnect";
  const name = status.catalog_name ? `${status.catalog_name} (${status.catalog_id})` : status.catalog_id;

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-secondary">
        Connected to {name} through {status.account_label ?? "your WhatsApp number"}.{" "}
        {status.syncing
          ? "Sending products now."
          : status.synced_at
            ? `${status.items_synced} ${status.items_synced === 1 ? "item" : "items"} in the catalogue, checked ${ago(status.synced_at)}.`
            : "No sync has finished yet."}
      </p>
      {attention ? (
        <div className="space-y-2">
          <Alert tone="danger" urgent>
            {status.sync_error ?? status.last_error ?? "Meta no longer lets this number use the catalogue."}
          </Alert>
          <Connect wid={wid} attention catalogId={status.catalog_id ?? ""} />
        </div>
      ) : (
        <>
          {status.sync_error ? <Alert tone="warning">{status.sync_error}</Alert> : null}
          {status.items_error > 0 ? (
            <Alert tone="warning">
              <p>
                {status.items_error} {status.items_error === 1 ? "item can't" : "items can't"} be sent.
              </p>
              <ul className="mt-1 list-disc ps-5">
                {(status.problems ?? []).map((problem) => (
                  <li key={`${problem.name}-${problem.message}`}>
                    {problem.name}: {problem.message}
                  </li>
                ))}
              </ul>
            </Alert>
          ) : null}
          <p className="text-xs text-fg-secondary">
            Changes to products reach the catalogue within a few minutes. A product needs a price, a link and a
            picture to be sent.
          </p>
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {attention ? null : (
          <Button
            variant="secondary"
            size="sm"
            disabled={status.syncing}
            loading={sync.isPending}
            onClick={() =>
              sync.mutate(undefined, {
                onSuccess: () => toast.success("Sending your products again."),
                onError: (error) => toastError(error),
              })
            }
          >
            <RefreshCw aria-hidden /> Sync now
          </Button>
        )}
        <Button
          variant="destructive-ghost"
          size="sm"
          loading={disconnect.isPending}
          onClick={() =>
            disconnect.mutate(undefined, {
              onSuccess: () => toast.success("WhatsApp catalogue disconnected."),
              onError: (error) => toastError(error),
            })
          }
        >
          <Trash2 aria-hidden /> Disconnect
        </Button>
      </div>
    </div>
  );
}
