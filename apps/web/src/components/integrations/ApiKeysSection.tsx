"use client";

import { Activity, Check, Copy, KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ToolCallList } from "@/components/ai-connections/ToolCallList";
import { PLANS_HREF } from "@/components/shell/nav";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ChipInput } from "@/components/ui/chip-input";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiKeyActivity, useApiKeys, useCreateApiKey, useRevokeApiKey, useUpdateApiKey } from "@/lib/api/queries";
import type { ApiKey, ApiKeyCreate, ApiScope, ApiScopeName } from "@/lib/api/types";
import { siteHref } from "@/lib/marketing/site";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/** What a new key can do before the member changes it: read-only, the safer start. */
const DEFAULT_SCOPES: ApiScopeName[] = ["contacts:read"];

/** C-167: how long a new key lasts. "never" is the default. */
const EXPIRY_CHOICES = [
  { value: "never", label: "Never" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
  { value: "365", label: "1 year" },
] as const;
type ExpiryChoice = (typeof EXPIRY_CHOICES)[number]["value"];
const MAX_ALLOWED_IPS = 20;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "12 Jan 2027", in the workspace's time zone. */
function expiryDate(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "numeric", year: "numeric", timeZone })
    .formatToParts(new Date(iso))
    .reduce<Record<string, string>>((all, part) => ({ ...all, [part.type]: part.value }), {});
  return `${Number(parts.day)} ${MONTHS[Number(parts.month) - 1]} ${parts.year}`;
}

/** "Expires 12 Jan 2027", "Expired", or null for a key that never expires. */
function expiryText(apiKey: Pick<ApiKey, "expires_at">, timeZone: string, now: Date = new Date()): string | null {
  if (!apiKey.expires_at) return null;
  return new Date(apiKey.expires_at).getTime() <= now.getTime() ? "Expired" : `Expires ${expiryDate(apiKey.expires_at, timeZone)}`;
}

const IP_HINT = "IP addresses or CIDR ranges, IPv4 or IPv6, like 203.0.113.7 or 10.0.0.0/8. Leave empty to allow any address.";

/**
 * Settings › API keys (GR-25, own section since C-165): keys for the public API, the Zapier app and AI apps over MCP. Make a
 * key with a name and scopes (it is shown once, in a copy dialog), see when each was last used,
 * revoke one. The public API is part of Business and Agency: a workspace without it is told so
 * instead of being offered the form. Owners and admins, like the webhook endpoints. Activity shows a
 * key's latest tool calls over MCP, as for a connected app.
 *
 * C-167: a key can expire (30 days, 90 days, a year, or never) and can be limited to IP addresses
 * and ranges. The list shows both; the name and the addresses can be edited later, the scopes
 * never. A key whose maker's account is gone says "Made by a former member".
 */
export function ApiKeysSection() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const keys = useApiKeys(wid);
  const [adding, setAdding] = useState(false);
  const [shown, setShown] = useState<string | null>(null);
  const items = keys.data?.items ?? [];
  // C-172, C-174: API keys are on Business (stored plan max) and Agency.
  const free = workspace.plan !== "max" && workspace.plan !== "agency";

  return (
    <SettingsCard
      id="api-keys"
      icon={<KeyRound />}
      title="API keys"
      description={
        <>
          Connect your own tools, Zapier or an AI app to this workspace.{" "}
          <Link className="font-medium text-brand-fg underline underline-offset-4" href={siteHref("/developers/api") as Route}>
            Read the API reference
          </Link>
          .
        </>
      }
      aside={
        free ? null : (
          <Button onClick={() => setAdding(true)}>
            <Plus aria-hidden /> Create API key
          </Button>
        )
      }
    >
      {free && items.length === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-raised p-4">
          <p className="text-sm">The public API, API keys and Zapier are part of Business and Agency.</p>
          <Button asChild variant="secondary">
            <Link href={PLANS_HREF(workspace.slug)}>See plans</Link>
          </Button>
        </div>
      ) : keys.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : keys.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load your API keys. Try again in a moment.</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          No API keys yet. Make one to read contacts, tag them or send a message from another tool.
        </p>
      ) : (
        <ul className="divide-y divide-line-subtle" aria-label="API keys">
          {items.map((key) => (
            <KeyRow
              key={key.id}
              apiKey={key}
              wid={wid}
              timeZone={workspace.timezone}
              catalogue={keys.data?.scopes ?? []}
            />
          ))}
        </ul>
      )}
      <CreateKeyDialog
        open={adding}
        onOpenChange={setAdding}
        wid={wid}
        catalogue={keys.data?.scopes ?? []}
        onCreated={(key) => {
          setAdding(false);
          setShown(key);
        }}
      />
      <KeyDialog value={shown} onClose={() => setShown(null)} />
    </SettingsCard>
  );
}

function KeyRow({
  apiKey,
  wid,
  timeZone,
  catalogue,
}: {
  apiKey: ApiKey;
  wid: string;
  timeZone: string;
  catalogue: ApiScope[];
}) {
  const revoke = useRevokeApiKey(wid);
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const activity = useApiKeyActivity(wid, apiKey.id, open);
  const revoked = apiKey.revoked_at !== null && apiKey.revoked_at !== undefined;
  const label = (scope: ApiScopeName) => catalogue.find((s) => s.scope === scope)?.description ?? scope;
  const expiry = revoked ? null : expiryText(apiKey, timeZone);
  const allowed = apiKey.allowed_ips ?? [];

  return (
    <li data-testid="api-key" className="flex flex-wrap items-start justify-between gap-3 py-4 first:pt-0 last:pb-0">
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold break-all">{apiKey.name}</p>
          {revoked ? <Badge tone="neutral">Revoked</Badge> : null}
          {expiry === "Expired" ? <Badge tone="warning">Expired</Badge> : null}
        </div>
        <p className="font-mono text-xs text-fg-secondary">{apiKey.key_prefix}&hellip;</p>
        <div className="flex flex-wrap gap-1.5" aria-label={`Scopes of ${apiKey.name}`}>
          {apiKey.scopes.map((scope) => (
            <Badge key={scope} tone="neutral" shape="tag" title={label(scope)}>
              {scope}
            </Badge>
          ))}
        </div>
        <p className="text-xs text-fg-secondary">
          Made {relativeTime(apiKey.created_at)}
          {revoked
            ? ` · revoked ${relativeTime(apiKey.revoked_at as string)}`
            : apiKey.last_used_at
              ? ` · last used ${relativeTime(apiKey.last_used_at)}`
              : " · never used"}
          {expiry && expiry !== "Expired" ? ` · ${expiry.replace("Expires", "expires")}` : ""}
        </p>
        {allowed.length > 0 ? (
          <p className="text-xs text-fg-secondary" data-testid="api-key-ips">
            Only from <span className="font-mono">{allowed.join(", ")}</span>
          </p>
        ) : null}
        {apiKey.made_by_former_member && !revoked ? (
          <p className="text-xs text-fg-secondary">Made by a former member. Revoke it if nothing still needs it.</p>
        ) : null}
        {open ? (
          <div id={`key-activity-${apiKey.id}`}>
            {activity.data ? (
              <ToolCallList
                calls={activity.data.items}
                label={`Recent activity of ${apiKey.name}`}
                empty="No tool calls from an AI app yet. Requests to the public API aren't listed here."
              />
            ) : activity.isError ? (
              <p className="text-xs text-fg-secondary">Couldn&rsquo;t load its activity. Try again in a moment.</p>
            ) : (
              <Skeleton className="h-4 w-40" />
            )}
          </div>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1">
        {/* A revoked key keeps its history: that is when someone asks what it did. */}
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-controls={`key-activity-${apiKey.id}`}
          onClick={() => setOpen((value) => !value)}
        >
          <Activity aria-hidden /> {open ? "Hide activity" : "Activity"}
        </Button>
        {revoked ? null : (
          <>
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)} aria-label={`Edit ${apiKey.name}`}>
              <Pencil aria-hidden /> Edit
            </Button>
            <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
              <Trash2 aria-hidden /> Revoke
            </Button>
          </>
        )}
      </div>
      {editing ? <EditKeyDialog apiKey={apiKey} wid={wid} onClose={() => setEditing(false)} /> : null}
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke {apiKey.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Anything using this key stops working at once, and the Zapier triggers it set up are removed. You can&rsquo;t
              undo this.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                revoke.mutate(apiKey.id, {
                  onSuccess: () => toast.success("API key revoked"),
                  onError: (error) => toastError(error),
                })
              }
            >
              Revoke key
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}

function CreateKeyDialog({
  open,
  onOpenChange,
  wid,
  catalogue,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  wid: string;
  catalogue: ApiScope[];
  onCreated: (key: string) => void;
}) {
  const create = useCreateApiKey(wid);
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState<ApiScopeName[]>(DEFAULT_SCOPES);
  const [expiry, setExpiry] = useState<ExpiryChoice>("never");
  const [ips, setIps] = useState<string[]>([]);

  function toggle(scope: ApiScopeName, checked: boolean) {
    setChosen((current) => (checked ? [...current, scope] : current.filter((s) => s !== scope)));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const body: ApiKeyCreate = { name: name.trim(), scopes: chosen };
    if (expiry !== "never") body.expires_in_days = Number(expiry) as ApiKeyCreate["expires_in_days"];
    if (ips.length > 0) body.allowed_ips = ips;
    create.mutate(
      body,
      {
        onSuccess: (made) => {
          setName("");
          setChosen(DEFAULT_SCOPES);
          setExpiry("never");
          setIps([]);
          onCreated(made.key);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Create an API key</DialogTitle>
            <DialogDescription>
              Give it only the scopes the tool needs. You can&rsquo;t change a key&rsquo;s scopes later: make another.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="api-key-name">Name</FieldLabel>
            <Input
              id="api-key-name"
              required
              maxLength={80}
              placeholder="Zapier"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Scopes</legend>
            {catalogue.map((entry) => (
              <label key={entry.scope} className="flex items-start gap-2 text-sm">
                <Checkbox
                  checked={chosen.includes(entry.scope)}
                  onCheckedChange={(checked) => toggle(entry.scope, checked === true)}
                  aria-describedby={`scope-${entry.scope}`}
                />
                <span>
                  <span className="font-mono text-xs">{entry.scope}</span>
                  <FieldDescription id={`scope-${entry.scope}`}>{entry.description}</FieldDescription>
                </span>
              </label>
            ))}
          </fieldset>
          <Field>
            <FieldLabel htmlFor="api-key-expiry">Expires</FieldLabel>
            <Select value={expiry} onValueChange={(value) => setExpiry(value as ExpiryChoice)}>
              <SelectTrigger id="api-key-expiry" className="w-full sm:w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXPIRY_CHOICES.map((choice) => (
                  <SelectItem key={choice.value} value={choice.value}>
                    {choice.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FieldDescription>We&rsquo;ll remind owners and admins a week before it stops working.</FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="api-key-ips">Allowed IP addresses</FieldLabel>
            <ChipInput
              id="api-key-ips"
              value={ips}
              onValueChange={setIps}
              listLabel="Allowed IP addresses"
              separator="comma"
              max={MAX_ALLOWED_IPS}
              maxLength={50}
              placeholder="Any address"
              hint={IP_HINT}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={name.trim() === "" || chosen.length === 0}>
              Create key
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** C-167: rename a key or change the addresses it works from. Scopes stay as they were made. */
function EditKeyDialog({ apiKey, wid, onClose }: { apiKey: ApiKey; wid: string; onClose: () => void }) {
  const update = useUpdateApiKey(wid);
  const [name, setName] = useState(apiKey.name);
  const [ips, setIps] = useState<string[]>(apiKey.allowed_ips ?? []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    update.mutate(
      { id: apiKey.id, body: { name: name.trim(), allowed_ips: ips } },
      {
        onSuccess: () => {
          toast.success("API key saved");
          onClose();
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Edit {apiKey.name}</DialogTitle>
            <DialogDescription>
              Change its name or where it can be used from. Its scopes stay as they are: make another key for different
              ones.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor={`api-key-name-${apiKey.id}`}>Name</FieldLabel>
            <Input
              id={`api-key-name-${apiKey.id}`}
              required
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor={`api-key-ips-${apiKey.id}`}>Allowed IP addresses</FieldLabel>
            <ChipInput
              id={`api-key-ips-${apiKey.id}`}
              value={ips}
              onValueChange={setIps}
              listLabel="Allowed IP addresses"
              separator="comma"
              max={MAX_ALLOWED_IPS}
              maxLength={50}
              placeholder="Any address"
              hint={IP_HINT}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={update.isPending} disabled={name.trim() === ""}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The new key, shown once. Closing it is the only way to lose it, so it asks for a copy first. */
function KeyDialog({ value, onClose }: { value: string | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog
      open={value !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false);
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Your API key</DialogTitle>
          <DialogDescription>
            Copy it now: you won&rsquo;t see it again. Keep it secret, and send it as{" "}
            <span className="font-mono text-xs">Authorization: Bearer &lt;key&gt;</span>.
          </DialogDescription>
        </DialogHeader>
        <code data-testid="api-key-value" className="block rounded-md bg-raised p-3 font-mono text-sm break-all">
          {value}
        </code>
        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => {
              if (!value) return;
              void navigator.clipboard?.writeText(value).then(() => setCopied(true));
            }}
          >
            {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? "Copied" : "Copy key"}
          </Button>
          <Button onClick={() => onClose()}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
