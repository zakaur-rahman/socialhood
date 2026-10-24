"use client";

import { Landmark, Trash2 } from "lucide-react";
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
  useConnectRazorpay,
  useDisconnectRazorpay,
  usePaymentSettings,
  useRemoveUpi,
  useSaveUpi,
} from "@/lib/api/queries";
import type { PaymentSettings } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";

/**
 * Payments (GR-32): the business's own Razorpay keys and/or UPI address. Money goes to the
 * business's account, never through Social Hood. Razorpay: the keys are checked with Razorpay before
 * they are saved, and a webhook address is shown to add in the Razorpay dashboard with the same
 * webhook secret, which is how a paid link reaches the order. UPI has no confirmation from the
 * bank, so those orders are marked paid by hand. Owners and admins; part of Pro.
 */
export function PaymentsCard({ wid }: { wid: string }) {
  const settings = usePaymentSettings(wid);
  return (
    <SettingsCard
      id="payments"
      icon={<Landmark />}
      title="Payments"
      description="Customers pay your own account. Add Razorpay for payment links, or a UPI address."
    >
      {settings.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : settings.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load payment settings. Reload the page to try again.</p>
      ) : (
        <Body wid={wid} settings={settings.data} />
      )}
    </SettingsCard>
  );
}

function Body({ wid, settings }: { wid: string; settings: PaymentSettings }) {
  const upgrade = useUpgradeDialog();
  if (!settings.entitled) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-secondary">Orders and payment requests are part of Pro.</p>
        <Button type="button" variant="secondary" size="sm" onClick={() => upgrade.open(COMMERCE_UPGRADE)}>
          See plans
        </Button>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <RazorpaySection wid={wid} settings={settings} />
      <UpiSection wid={wid} settings={settings} />
    </div>
  );
}

function RazorpaySection({ wid, settings }: { wid: string; settings: PaymentSettings }) {
  const connect = useConnectRazorpay(wid);
  const disconnect = useDisconnectRazorpay(wid);
  const [keyId, setKeyId] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [webhookKey, setWebhookKey] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    connect.mutate(
      { key_id: keyId.trim(), private_key: privateKey.trim(), webhook_key: webhookKey.trim() },
      {
        onSuccess: () => {
          setPrivateKey("");
          setWebhookKey("");
          toast.success("Razorpay connected.");
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 422) setProblem(error.errors[0]?.message ?? error.detail ?? null);
          else toastError(error);
        },
      },
    );
  }

  return (
    <section className="space-y-3" aria-labelledby="razorpay-title">
      <div className="flex flex-wrap items-center gap-2">
        <h3 id="razorpay-title" className="text-sm font-semibold">
          Razorpay
        </h3>
        <Badge tone={settings.razorpay_connected ? "success" : "neutral"}>
          {settings.razorpay_connected ? (settings.razorpay_test_mode ? "Connected, test mode" : "Connected") : "Not connected"}
        </Badge>
      </div>
      {settings.razorpay_connected ? (
        <div className="space-y-3">
          <p className="text-sm text-fg-secondary">
            Using key {settings.razorpay_key_id}. A payment link is made for each order you ask payment for.
          </p>
          {settings.razorpay_error ? <Alert tone="warning">{settings.razorpay_error}</Alert> : null}
          <div className="space-y-1 rounded-lg border border-line p-3 text-sm">
            <p className="font-medium">Add this webhook in your Razorpay dashboard</p>
            <p className="text-fg-secondary">
              Settings, Webhooks, Add new webhook. Use the same webhook secret you entered here, and turn on{" "}
              {(settings.webhook_events ?? []).join(", ")}.
            </p>
            {settings.webhook_url ? (
              <p className="font-mono text-xs break-all" data-testid="webhook-url">
                {settings.webhook_url}
              </p>
            ) : (
              <p className="text-fg-secondary">The server&rsquo;s public address isn&rsquo;t set, so there is no address to show yet.</p>
            )}
            <p className="text-xs text-fg-secondary">
              {settings.webhook_seen_at
                ? `Last event received ${relativeTime(settings.webhook_seen_at) === "now" ? "just now" : `${relativeTime(settings.webhook_seen_at)} ago`}.`
                : "No event received yet. Without the webhook, paid links don't mark orders paid."}
            </p>
          </div>
          <Button
            variant="destructive-ghost"
            size="sm"
            loading={disconnect.isPending}
            onClick={() =>
              disconnect.mutate(undefined, {
                onSuccess: () => toast.success("Razorpay disconnected."),
                onError: (error) => toastError(error),
              })
            }
          >
            <Trash2 aria-hidden /> Disconnect Razorpay
          </Button>
        </div>
      ) : (
        <form className="space-y-2" onSubmit={submit}>
          <p className="text-sm text-fg-secondary">
            Use the keys from your Razorpay dashboard (Settings, API keys). Start with test keys (rzp_test_…) to try it
            without real money.
          </p>
          <Field id="rzp-key-id" invalid={Boolean(problem)}>
            <FieldLabel>Key id</FieldLabel>
            <Input maxLength={64} placeholder="rzp_test_…" value={keyId} onChange={(e) => setKeyId(e.target.value)} />
          </Field>
          <Field id="rzp-private-key">
            <FieldLabel>Key secret</FieldLabel>
            <Input
              type="password"
              autoComplete="off"
              maxLength={128}
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
            />
          </Field>
          <Field id="rzp-webhook-key">
            <FieldLabel>Webhook secret</FieldLabel>
            <Input
              type="password"
              autoComplete="off"
              maxLength={128}
              value={webhookKey}
              onChange={(e) => setWebhookKey(e.target.value)}
            />
            <FieldDescription>
              Make one up (at least 8 characters). You enter the same one when you add the webhook in Razorpay.
            </FieldDescription>
            <FieldError>{problem}</FieldError>
          </Field>
          <Button type="submit" loading={connect.isPending} disabled={!keyId.trim() || !privateKey.trim() || webhookKey.trim().length < 8}>
            Connect Razorpay
          </Button>
        </form>
      )}
    </section>
  );
}

function UpiSection({ wid, settings }: { wid: string; settings: PaymentSettings }) {
  const save = useSaveUpi(wid);
  const remove = useRemoveUpi(wid);
  const [vpa, setVpa] = useState(settings.upi_vpa ?? "");
  const [name, setName] = useState(settings.upi_name ?? "");
  const [problem, setProblem] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    save.mutate(
      { vpa: vpa.trim(), name: name.trim() },
      {
        onSuccess: () => toast.success("UPI address saved."),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 422) setProblem("Enter an address like shop@okbank.");
          else toastError(error);
        },
      },
    );
  }

  return (
    <section className="space-y-3" aria-labelledby="upi-title">
      <div className="flex flex-wrap items-center gap-2">
        <h3 id="upi-title" className="text-sm font-semibold">
          UPI
        </h3>
        <Badge tone={settings.upi_vpa ? "success" : "neutral"}>{settings.upi_vpa ? "Set up" : "Not set up"}</Badge>
      </div>
      <Alert tone="brand">
        A UPI request has no confirmation from the bank. When the customer says they have paid, open the order and mark it
        paid. Social Hood records who did it and when.
      </Alert>
      <form className="space-y-2" onSubmit={submit}>
        <Field id="upi-vpa" invalid={Boolean(problem)}>
          <FieldLabel>UPI address</FieldLabel>
          <Input maxLength={100} placeholder="shop@okbank" value={vpa} onChange={(e) => setVpa(e.target.value)} />
          <FieldError>{problem}</FieldError>
        </Field>
        <Field id="upi-name">
          <FieldLabel>Name shown to the customer</FieldLabel>
          <Input maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" loading={save.isPending} disabled={!vpa.trim() || !name.trim()}>
            Save UPI address
          </Button>
          {settings.upi_vpa ? (
            <Button
              type="button"
              variant="destructive-ghost"
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(undefined, {
                  onSuccess: () => {
                    setVpa("");
                    setName("");
                    toast.success("UPI address removed.");
                  },
                  onError: (error) => toastError(error),
                })
              }
            >
              Remove
            </Button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
