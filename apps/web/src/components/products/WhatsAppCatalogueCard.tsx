"use client";

import { Copy, Link2, MessageCircle, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
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
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import {
  useConnectWaCatalogue,
  useDisconnectWaCatalogue,
  useRenewWaCatalogueFeedLink,
  useSocialAccounts,
  useWaCatalogue,
} from "@/lib/api/queries";
import type { WaCatalogueStatus } from "@/lib/api/types";
import { plural } from "@/lib/copy";
import { timeAgo } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * Products, WhatsApp catalogue (GR-33, C-215): lets WhatsApp product and product-list messages show
 * the products. Meta's WhatsApp sign-up never gives an app access to a catalogue, so Amplychat
 * publishes the products at a secret feed link and the business adds that link once in Commerce
 * Manager as a scheduled data feed; Meta fetches it hourly. Owners and admins see the link (the API
 * leaves it out for other roles). Part of Creator and Business (PD-8).
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
  if (status.last_error) return <Badge tone="danger">Needs attention</Badge>;
  if (!status.feed_fetched_at) return <Badge tone="neutral">Waiting for Meta</Badge>;
  return <Badge tone="success">Connected</Badge>;
}

function Body({ wid, status }: { wid: string; status: WaCatalogueStatus }) {
  const workspace = useCurrentWorkspace();
  const upgrade = useUpgradeDialog();
  if (!status.entitled) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-secondary">WhatsApp product messages are part of Creator and Business.</p>
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

function Connect({ wid }: { wid: string }) {
  const accounts = useSocialAccounts(wid);
  const connect = useConnectWaCatalogue(wid);
  const numbers = (accounts.data ?? []).filter((account) => account.platform === "whatsapp");
  const [chosen, setChosen] = useState("");
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const accountId = chosen || numbers[0]?.id || "";

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    connect.mutate(
      { social_account_id: accountId, catalog_id: text.trim() },
      {
        onSuccess: () => toast.success("WhatsApp catalogue connected. Now add the feed link in Commerce Manager."),
        onError: (error) => {
          if (error instanceof ApiError && (error.status === 409 || error.status === 422)) {
            setProblem(error.errors[0]?.message ?? error.detail ?? null);
          } else toastError(error);
        },
      },
    );
  }

  if (accounts.isSuccess && numbers.length === 0) {
    return <p className="text-sm text-fg-secondary">Connect a WhatsApp number first, in Connections.</p>;
  }
  return (
    <form className="space-y-2" onSubmit={submit}>
      <ol className="list-decimal space-y-1 ps-5 text-sm text-fg-secondary">
        <li>In Meta Commerce Manager, create a catalogue in the business portfolio that owns your WhatsApp number.</li>
        <li>Link it to the number in WhatsApp Manager &rsaquo; Catalogue.</li>
        <li>Enter its id here.</li>
      </ol>
      <Field id="wa-catalogue-number">
        <FieldLabel>WhatsApp number</FieldLabel>
        <select
          value={accountId}
          onChange={(event) => setChosen(event.target.value)}
          className="h-9 w-full rounded-lg border border-line-strong bg-field-input px-2 text-sm"
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
        <Input maxLength={30} inputMode="numeric" value={text} onChange={(event) => setText(event.target.value)} />
        <FieldDescription>Commerce Manager &rsaquo; Catalogue &rsaquo; Settings.</FieldDescription>
        <FieldError>{problem}</FieldError>
      </Field>
      <Button type="submit" loading={connect.isPending} disabled={!text.trim() || !accountId}>
        Connect catalogue
      </Button>
    </form>
  );
}

function Connected({ wid, status }: { wid: string; status: WaCatalogueStatus }) {
  const disconnect = useDisconnectWaCatalogue(wid);
  const [renewing, setRenewing] = useState(false);
  const feedUrl = status.feed_url;

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-secondary">
        Connected to catalogue {status.catalog_id} through {status.account_label ?? "your WhatsApp number"}.{" "}
        {status.feed_fetched_at
          ? `Meta last fetched your products ${timeAgo(status.feed_fetched_at)}.`
          : "Meta hasn't fetched your products yet — add the link in Commerce Manager."}
      </p>
      {status.last_error ? <Alert tone="warning">{status.last_error}</Alert> : null}

      <dl className="grid grid-cols-3 gap-2 text-sm">
        <Count label="In the catalogue" value={status.items_synced} />
        <Count label="Waiting for Meta's next fetch" value={status.items_pending} />
        <Count label="Problems" value={status.items_error} />
      </dl>
      {status.items_error > 0 ? (
        <Alert tone="warning">
          <p>
            {status.items_error} {plural(status.items_error, "product can't", "products can't")} be in the catalogue.
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

      {feedUrl ? (
        <>
          <FeedLink url={feedUrl} />
          <div className="space-y-1 text-sm text-fg-secondary">
            <p>Add it once in Commerce Manager:</p>
            <ol className="list-decimal space-y-1 ps-5">
              <li>Data sources &rsaquo; Add items &rsaquo; Data file.</li>
              <li>Create a data file from scratch &rsaquo; Upload via URL or Google Sheets.</li>
              <li>Paste the link and set the schedule to hourly.</li>
            </ol>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => setRenewing(true)}>
              <Link2 aria-hidden /> New link
            </Button>
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
          <RenewLink wid={wid} open={renewing} onOpenChange={setRenewing} />
        </>
      ) : null}
    </div>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line p-2">
      <dt className="text-xs text-fg-secondary">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function FeedLink({ url }: { url: string }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Feed link copied");
    } catch {
      toast.error("Couldn't copy. Select the link and copy it by hand.");
    }
  }
  return (
    <Field id="wa-catalogue-feed">
      <FieldLabel>Feed link</FieldLabel>
      <div className="flex gap-2">
        <Input readOnly value={url} onFocus={(event) => event.currentTarget.select()} />
        <Button type="button" variant="secondary" onClick={() => void copy()}>
          <Copy aria-hidden /> Copy
        </Button>
      </div>
      <FieldDescription>Keep it private: anyone with the link can see your product list.</FieldDescription>
    </Field>
  );
}

function RenewLink({ wid, open, onOpenChange }: { wid: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const renew = useRenewWaCatalogueFeedLink(wid);
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Make a new feed link?</AlertDialogTitle>
          <AlertDialogDescription>
            The old link stops working at once. Paste the new one in Commerce Manager, or Meta can&rsquo;t fetch your
            products.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() =>
              renew.mutate(undefined, {
                onSuccess: () => toast.success("New feed link made. Paste it in Commerce Manager."),
                onError: (error) => toastError(error),
              })
            }
          >
            Make new link
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
