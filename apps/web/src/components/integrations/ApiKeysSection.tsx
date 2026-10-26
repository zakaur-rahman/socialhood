"use client";

import { Check, Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { BILLING_HREF } from "@/components/shell/nav";
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
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/lib/api/queries";
import type { ApiKey, ApiScope, ApiScopeName } from "@/lib/api/types";
import { siteHref } from "@/lib/marketing/site";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/** What a new key can do before the member changes it: read-only, the safer start. */
const DEFAULT_SCOPES: ApiScopeName[] = ["contacts:read"];

/**
 * Settings › Integrations › API keys (GR-25): keys for the public API and the Zapier app. Make a
 * key with a name and scopes (it is shown once, in a copy dialog), see when each was last used,
 * revoke one. The public API is part of Pro and Max: a Free workspace is told so instead of
 * being offered the form. Owners and admins, like the webhook endpoints beside it.
 */
export function ApiKeysSection() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const keys = useApiKeys(wid);
  const [adding, setAdding] = useState(false);
  const [shown, setShown] = useState<string | null>(null);
  const items = keys.data?.items ?? [];
  const free = workspace.plan === "free";

  return (
    <SettingsCard
      id="api-keys"
      icon={<KeyRound />}
      title="API keys"
      description={
        <>
          Connect your own tools, or Zapier, to your contacts and conversations.{" "}
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
          <p className="text-sm">The public API, API keys and Zapier are part of Pro.</p>
          <Button asChild variant="secondary">
            <Link href={BILLING_HREF(workspace.slug)}>See plans</Link>
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
            <KeyRow key={key.id} apiKey={key} wid={wid} catalogue={keys.data?.scopes ?? []} />
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

function KeyRow({ apiKey, wid, catalogue }: { apiKey: ApiKey; wid: string; catalogue: ApiScope[] }) {
  const revoke = useRevokeApiKey(wid);
  const [confirming, setConfirming] = useState(false);
  const revoked = apiKey.revoked_at !== null && apiKey.revoked_at !== undefined;
  const label = (scope: ApiScopeName) => catalogue.find((s) => s.scope === scope)?.description ?? scope;

  return (
    <li data-testid="api-key" className="flex flex-wrap items-start justify-between gap-3 py-4 first:pt-0 last:pb-0">
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold break-all">{apiKey.name}</p>
          {revoked ? <Badge tone="neutral">Revoked</Badge> : null}
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
        </p>
      </div>
      {revoked ? null : (
        <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
          <Trash2 aria-hidden /> Revoke
        </Button>
      )}
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

  function toggle(scope: ApiScopeName, checked: boolean) {
    setChosen((current) => (checked ? [...current, scope] : current.filter((s) => s !== scope)));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    create.mutate(
      { name: name.trim(), scopes: chosen },
      {
        onSuccess: (made) => {
          setName("");
          setChosen(DEFAULT_SCOPES);
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
