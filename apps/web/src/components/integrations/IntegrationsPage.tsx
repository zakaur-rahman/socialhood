"use client";

import { Check, Copy, Plus, RotateCcw, Send, Trash2, Webhook } from "lucide-react";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { GoogleSheetsCard } from "@/components/integrations/GoogleSheetsCard";
import { ApiKeysSection } from "@/components/integrations/ApiKeysSection";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api/errors";
import {
  useCreateWebhookEndpoint,
  useDeleteWebhookEndpoint,
  useReplayWebhookDelivery,
  useRotateWebhookSecret,
  useSendWebhookTest,
  useUpdateWebhookEndpoint,
  useWebhookDeliveries,
  useWebhookEndpoints,
  useWebhookEvents,
} from "@/lib/api/queries";
import type { WebhookDelivery, WebhookEndpoint, WebhookEventName, WebhookEventType } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const STATUS: Record<WebhookEndpoint["status"], { label: string; tone: "success" | "neutral" | "danger" }> = {
  active: { label: "On", tone: "success" },
  paused: { label: "Paused", tone: "neutral" },
  disabled: { label: "Turned off after failures", tone: "danger" },
};

const DELIVERY: Record<WebhookDelivery["status"], { label: string; tone: "success" | "warning" | "danger" }> = {
  succeeded: { label: "Delivered", tone: "success" },
  pending: { label: "Trying", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};

/**
 * Settings › Integrations (GR-04): webhook endpoints that receive Social Hood's events as they
 * happen. Add one (its signing secret is shown once), turn it on or off, send a test event, see
 * each delivery's last attempt and replay one. Above them, the Google Sheets card (GR-27) adds
 * every captured lead to a sheet. Owners and admins.
 */
export function IntegrationsPage() {
  const { id: wid } = useCurrentWorkspace();
  const endpoints = useWebhookEndpoints(wid);
  const catalogue = useWebhookEvents(wid);
  const [adding, setAdding] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const items = endpoints.data?.items ?? [];
  const limit = endpoints.data?.limit ?? null;

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Integrations"
          description="Send events to Zapier, Make, your CRM or your own server as they happen. Each request is signed, so you can check it came from Social Hood."
          actions={
            <Button onClick={() => setAdding(true)}>
              <Plus aria-hidden /> Add endpoint
            </Button>
          }
        />
      }
    >
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <GoogleSheetsCard wid={wid} />
      </Suspense>
      {endpoints.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Webhook />}
          title="No endpoints yet"
          body="Add a webhook address to receive new leads, messages and tags as they happen."
          action={
            <Button variant="secondary" onClick={() => setAdding(true)}>
              <Plus aria-hidden /> Add endpoint
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {items.map((endpoint) => (
            <EndpointCard key={endpoint.id} endpoint={endpoint} wid={wid} onSecret={setSecret} />
          ))}
          {limit !== null ? (
            <p className="text-sm text-fg-secondary">
              {items.length} of {limit} endpoint{limit === 1 ? "" : "s"} on your plan.
            </p>
          ) : null}
        </div>
      )}
      <AddEndpointDialog
        open={adding}
        onOpenChange={setAdding}
        wid={wid}
        events={catalogue.data ?? []}
        onCreated={(value) => {
          setAdding(false);
          setSecret(value);
        }}
      />
      <SecretDialog secret={secret} onClose={() => setSecret(null)} />
      <ApiKeysSection />
    </SettingsFrame>
  );
}

function EndpointCard({
  endpoint,
  wid,
  onSecret,
}: {
  endpoint: WebhookEndpoint;
  wid: string;
  onSecret: (secret: string) => void;
}) {
  const update = useUpdateWebhookEndpoint(wid);
  const remove = useDeleteWebhookEndpoint(wid);
  const rotate = useRotateWebhookSecret(wid);
  const test = useSendWebhookTest(wid);
  const [confirming, setConfirming] = useState(false);
  const status = STATUS[endpoint.status];
  const on = endpoint.status === "active";

  return (
    <SettingsCard
      id={`endpoint-${endpoint.id}`}
      icon={<Webhook />}
      title={<span className="break-all">{endpoint.description || endpoint.url}</span>}
      description={endpoint.description ? <span className="break-all">{endpoint.url}</span> : undefined}
      aside={
        <div className="flex items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          <Switch
            aria-label={`Send events to ${endpoint.description || endpoint.url}`}
            checked={on}
            disabled={update.isPending}
            onCheckedChange={(checked) =>
              update.mutate(
                { id: endpoint.id, body: { status: checked ? "active" : "paused" } },
                { onError: (error) => toastError(error) },
              )
            }
          />
        </div>
      }
    >
      <div className="flex flex-wrap gap-1.5" aria-label="Events">
        {endpoint.events.map((name) => (
          <Badge key={name} tone="neutral" shape="tag">
            {name}
          </Badge>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!on}
          loading={test.isPending}
          onClick={() =>
            test.mutate(endpoint.id, {
              onSuccess: () => toast.success("Test event sent. It shows in the log below."),
              onError: (error) => toastError(error),
            })
          }
        >
          <Send aria-hidden /> Send test event
        </Button>
        <Button
          variant="ghost"
          size="sm"
          loading={rotate.isPending}
          onClick={() =>
            rotate.mutate(endpoint.id, {
              onSuccess: (rotated) => onSecret(rotated.signing_secret),
              onError: (error) => toastError(error),
            })
          }
        >
          <RotateCcw aria-hidden /> New signing secret
        </Button>
        <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
          <Trash2 aria-hidden /> Delete
        </Button>
      </div>
      <Deliveries wid={wid} endpointId={endpoint.id} />
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this endpoint?</AlertDialogTitle>
            <AlertDialogDescription>
              It stops receiving events at once, and its delivery log goes with it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                remove.mutate(endpoint.id, {
                  onSuccess: () => toast.success("Endpoint deleted"),
                  onError: (error) => toastError(error),
                })
              }
            >
              Delete endpoint
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsCard>
  );
}

function Deliveries({ wid, endpointId }: { wid: string; endpointId: string }) {
  const deliveries = useWebhookDeliveries(wid, endpointId);
  const replay = useReplayWebhookDelivery(wid);
  const items = deliveries.data?.items ?? [];
  if (deliveries.isPending) return <Skeleton className="h-24 w-full" />;
  if (items.length === 0) {
    return <p className="text-sm text-fg-secondary">No deliveries yet. Send a test event to try it.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableCaption className="sr-only">Latest deliveries</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Event</TableHead>
            <TableHead>Result</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead>Response</TableHead>
            <TableHead>When</TableHead>
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((d) => {
            const status = DELIVERY[d.status];
            return (
              <TableRow key={d.id} data-testid="webhook-delivery">
                <TableCell className="font-mono text-xs">{d.event_type}</TableCell>
                <TableCell>
                  <Badge tone={status.tone}>{status.label}</Badge>
                  {d.error ? <p className="mt-1 text-xs text-fg-secondary">{d.error}</p> : null}
                </TableCell>
                <TableCell className="tabular-nums">{d.attempts}</TableCell>
                <TableCell className="tabular-nums">
                  {d.response_code ?? "—"}
                  {d.duration_ms != null ? <span className="text-fg-secondary"> · {d.duration_ms} ms</span> : null}
                </TableCell>
                <TableCell className="whitespace-nowrap text-fg-secondary">
                  {relativeTime(d.last_attempt_at ?? d.created_at)}
                </TableCell>
                <TableCell>
                  {d.status === "failed" ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Send ${d.event_type} again`}
                      onClick={() =>
                        replay.mutate(d.id, {
                          onSuccess: () => toast.success("Sent again"),
                          onError: (error) => toastError(error),
                        })
                      }
                    >
                      <RotateCcw aria-hidden /> Send again
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function AddEndpointDialog({
  open,
  onOpenChange,
  wid,
  events,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  wid: string;
  events: WebhookEventType[];
  onCreated: (secret: string) => void;
}) {
  const create = useCreateWebhookEndpoint(wid);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [chosen, setChosen] = useState<WebhookEventName[]>(["lead.captured"]);
  const [urlError, setUrlError] = useState<string | null>(null);

  function toggle(name: WebhookEventName, checked: boolean) {
    setChosen((current) => (checked ? [...current, name] : current.filter((n) => n !== name)));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setUrlError(null);
    create.mutate(
      { url, description: description || null, events: chosen },
      {
        onSuccess: (made) => {
          setUrl("");
          setDescription("");
          setChosen(["lead.captured"]);
          onCreated(made.signing_secret);
        },
        onError: (error) => {
          const field = error instanceof ApiError ? error.errors.find((e) => e.field === "url") : undefined;
          if (field) setUrlError(field.message);
          else toastError(error);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Add a webhook endpoint</DialogTitle>
            <DialogDescription>We send a POST request with JSON to this address for each event you choose.</DialogDescription>
          </DialogHeader>
          <Field invalid={Boolean(urlError)}>
            <FieldLabel htmlFor="webhook-url">Endpoint address</FieldLabel>
            <Input
              id="webhook-url"
              type="url"
              required
              placeholder="https://hooks.zapier.com/…"
              value={url}
              aria-invalid={urlError ? true : undefined}
              aria-describedby={urlError ? "webhook-url-error" : undefined}
              onChange={(e) => setUrl(e.target.value)}
            />
            {urlError ? (
              <p id="webhook-url-error" className="text-sm text-danger-fg">
                {urlError}
              </p>
            ) : null}
          </Field>
          <Field>
            <FieldLabel htmlFor="webhook-description">Name (optional)</FieldLabel>
            <Input
              id="webhook-description"
              maxLength={100}
              placeholder="Zapier: new leads to Sheets"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Events</legend>
            {events.map((e) => (
              <label key={e.type} className="flex items-start gap-2 text-sm">
                <Checkbox
                  checked={chosen.includes(e.type)}
                  onCheckedChange={(checked) => toggle(e.type, checked === true)}
                  aria-describedby={`event-${e.type}`}
                />
                <span>
                  <span className="font-mono text-xs">{e.type}</span>
                  <FieldDescription id={`event-${e.type}`}>
                    {e.description}
                    {e.emitted ? "" : " Coming with that feature."}
                  </FieldDescription>
                </span>
              </label>
            ))}
          </fieldset>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={chosen.length === 0}>
              Add endpoint
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SecretDialog({ secret, onClose }: { secret: string | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog
      open={secret !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false);
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Your signing secret</DialogTitle>
          <DialogDescription>
            Copy it now: you won&rsquo;t see it again. Use it to check each request&rsquo;s webhook-signature header
            (Standard Webhooks).
          </DialogDescription>
        </DialogHeader>
        <code data-testid="signing-secret" className="block rounded-md bg-raised p-3 font-mono text-sm break-all">
          {secret}
        </code>
        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => {
              if (!secret) return;
              void navigator.clipboard?.writeText(secret).then(() => setCopied(true));
            }}
          >
            {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? "Copied" : "Copy secret"}
          </Button>
          <Button onClick={() => onClose()}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
