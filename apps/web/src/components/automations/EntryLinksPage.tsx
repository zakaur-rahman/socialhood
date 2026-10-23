"use client";

import { Copy, Download, Plus, QrCode, Trash2 } from "lucide-react";
import type { Route } from "next";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
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
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import {
  useAutomations,
  useCreateEntryLink,
  useDeleteEntryLink,
  useDownloadEntryLinkQr,
  useEntryLinkQr,
  useEntryLinks,
  useSocialAccounts,
  useUpdateEntryLink,
} from "@/lib/api/queries";
import type { Automation, EntryLink, QrFormat } from "@/lib/api/types";
import { accountLabel, instagramAccounts } from "@/lib/automations/accounts";
import { formatCount } from "@/lib/comments/format";
import { emptyStates } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const NONE = "none";

/** Save a blob as a file through a temporary link. */
function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** The entry link automations of one account, for the picker (an automation can serve many links). */
function useEntryAutomations(wid: string, accountId: string | null): Automation[] {
  const list = useAutomations(wid, { accountId, status: null, trigger: "entry_link", q: "", sort: "created" });
  return useMemo(() => list.data?.items ?? [], [list.data]);
}

/**
 * GR-08: ig.me links that open a chat with the account and start an entry link automation, each
 * with a QR code to download and counts of the chats and runs it led to. Instagram only: WhatsApp
 * has no way to tag a link.
 */
export function EntryLinksPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const links = useEntryLinks(wid);
  const [creating, setCreating] = useState(false);
  const [qrFor, setQrFor] = useState<EntryLink | null>(null);
  const [removing, setRemoving] = useState<EntryLink | null>(null);
  const remove = useDeleteEntryLink(wid);

  let content;
  if (links.isPending) {
    content = (
      <Card>
        <ul aria-busy="true" aria-label="Loading entry links" className="divide-y divide-line-subtle">
          {Array.from({ length: 3 }, (_, i) => (
            <li key={i} className="space-y-2 px-4 py-4">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </li>
          ))}
        </ul>
      </Card>
    );
  } else if (links.isError) {
    content = <ErrorState error={links.error} onRetry={() => void links.refetch()} />;
  } else if (links.data.length === 0) {
    content = (
      <Card>
        <EmptyState
          size="compact"
          {...emptyStates.entryLinks}
          action={
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden /> New entry link
            </Button>
          }
        />
      </Card>
    );
  } else {
    content = (
      <Card className="overflow-hidden p-0">
        <ul aria-label="Entry links" className="divide-y divide-line-subtle">
          {links.data.map((link) => (
            <LinkRow key={link.id} wid={wid} link={link} onQr={() => setQrFor(link)} onDelete={() => setRemoving(link)} />
          ))}
        </ul>
      </Card>
    );
  }

  return (
    <PageFrame
      title="Entry links"
      back={{ href: `/w/${workspace.slug}/automations` as Route, label: "Automations" }}
      actions={
        <Button size="lg" onClick={() => setCreating(true)}>
          <Plus aria-hidden /> New <span className="max-[359px]:sr-only">entry link</span>
        </Button>
      }
    >
      <div className="space-y-4">
        <p className="max-w-prose text-sm text-fg-secondary">
          An entry link opens a chat with your Instagram account and starts the automation you choose. Share it as a
          link or print the QR code.
        </p>
        {content}
      </div>
      <CreateDialog wid={wid} open={creating} onOpenChange={setCreating} />
      <QrDialog wid={wid} link={qrFor} onClose={() => setQrFor(null)} />
      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this link?</AlertDialogTitle>
            <AlertDialogDescription>
              The link and its QR code stop starting the automation. Chats it already opened stay in your inbox.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!removing) return;
                remove.mutate(removing.id, {
                  onSuccess: () => toast.success("Link deleted"),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Delete link
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}

function LinkRow({
  wid,
  link,
  onQr,
  onDelete,
}: {
  wid: string;
  link: EntryLink;
  onQr: () => void;
  onDelete: () => void;
}) {
  const download = useDownloadEntryLinkQr(wid);
  const [editing, setEditing] = useState(false);

  function copy() {
    void navigator.clipboard
      ?.writeText(link.url)
      .then(() => toast.success("Link copied"))
      .catch(() => toast.error("Couldn't copy the link. Select it and copy by hand."));
  }

  function save(format: QrFormat) {
    download.mutate(
      { id: link.id, format },
      { onSuccess: (blob) => saveBlob(blob, `${link.code}.${format}`), onError: (error) => toastError(error) },
    );
  }

  return (
    <li className="space-y-3 px-4 py-4" data-testid="entry-link-row">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="truncate text-sm font-medium">{link.name}</p>
          <p className="break-all text-xs text-fg-secondary" data-testid="entry-link-url">
            {link.url}
          </p>
          <p className="text-xs text-fg-secondary">
            {link.automation_name ? `Starts "${link.automation_name}"` : "Starts no automation"}
          </p>
        </div>
        <dl className="flex gap-5 text-sm tabular-nums">
          <div>
            <dt className="text-xs text-fg-secondary">Chats opened</dt>
            <dd className="font-medium" data-testid="entry-link-opened">
              {formatCount(link.opened_conversations)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-fg-secondary">Runs</dt>
            <dd className="font-medium" data-testid="entry-link-runs">
              {formatCount(link.runs)}
            </dd>
          </div>
        </dl>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={copy}>
          <Copy aria-hidden /> Copy link
        </Button>
        <Button variant="secondary" size="sm" onClick={onQr}>
          <QrCode aria-hidden /> QR code
        </Button>
        <Button variant="ghost" size="sm" onClick={() => save("svg")} loading={download.isPending}>
          <Download aria-hidden /> SVG
        </Button>
        <Button variant="ghost" size="sm" onClick={() => save("png")} loading={download.isPending}>
          <Download aria-hidden /> PNG
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <Button variant="destructive-ghost" size="sm" onClick={onDelete}>
          <Trash2 aria-hidden /> Delete
        </Button>
      </div>
      <EditDialog wid={wid} link={link} open={editing} onOpenChange={setEditing} />
    </li>
  );
}

function AutomationPicker({
  id,
  automations,
  value,
  onChange,
}: {
  id: string;
  automations: Automation[];
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <Select value={value ?? NONE} onValueChange={(next) => onChange(next === NONE ? null : next)}>
      <SelectTrigger id={id} aria-label="Automation to start">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>None, only record where chats come from</SelectItem>
        {automations.map((automation) => (
          <SelectItem key={automation.id} value={automation.id}>
            {automation.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function CreateDialog({
  wid,
  open,
  onOpenChange,
}: {
  wid: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateEntryLink(wid);
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);
  const [name, setName] = useState("");
  const [accountId, setAccountId] = useState<string | null>(null);
  const [automationId, setAutomationId] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const account = accountId ?? accounts[0]?.id ?? null;
  const automations = useEntryAutomations(wid, account);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!account) return;
    setNameError(null);
    create.mutate(
      { social_account_id: account, name, automation_id: automationId },
      {
        onSuccess: () => {
          setName("");
          setAutomationId(null);
          onOpenChange(false);
          toast.success("Entry link made");
        },
        onError: (error) => {
          const field = error instanceof ApiError ? error.errors.find((e) => e.field === "name") : undefined;
          if (field) setNameError(field.message);
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
            <DialogTitle>New entry link</DialogTitle>
            <DialogDescription>
              Name it for where you will put it, like &quot;Shop window&quot; or &quot;Bio&quot;.
            </DialogDescription>
          </DialogHeader>
          <Field invalid={Boolean(nameError)}>
            <FieldLabel htmlFor="entry-link-name">Name</FieldLabel>
            <Input
              id="entry-link-name"
              required
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            {nameError ? <p className="text-sm text-danger-fg">{nameError}</p> : null}
          </Field>
          {accounts.length > 1 ? (
            <Field>
              <FieldLabel htmlFor="entry-link-account">Account</FieldLabel>
              <Select
                value={account ?? ""}
                onValueChange={(value) => {
                  setAccountId(value);
                  setAutomationId(null);
                }}
              >
                <SelectTrigger id="entry-link-account" aria-label="Account">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {accountLabel(item)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          <Field>
            <FieldLabel htmlFor="entry-link-automation">Automation to start</FieldLabel>
            <AutomationPicker
              id="entry-link-automation"
              automations={automations}
              value={automationId}
              onChange={setAutomationId}
            />
            {automations.length === 0 ? (
              <p className="text-xs text-fg-secondary">
                Make an automation that starts from an entry link first, then choose it here.
              </p>
            ) : null}
          </Field>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={!account || !name.trim()}>
              Make link
            </Button>
          </DialogFooter>
        </form>
        {accounts.length === 0 && allAccounts.isSuccess ? (
          <p className="text-sm text-fg-secondary">Connect an Instagram account to make entry links.</p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditDialog({
  wid,
  link,
  open,
  onOpenChange,
}: {
  wid: string;
  link: EntryLink;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const update = useUpdateEntryLink(wid);
  const [name, setName] = useState(link.name);
  const [automationId, setAutomationId] = useState<string | null>(link.automation_id ?? null);
  const automations = useEntryAutomations(wid, open ? link.social_account_id : null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    update.mutate(
      { id: link.id, body: { name, automation_id: automationId } },
      {
        onSuccess: () => {
          onOpenChange(false);
          toast.success("Link saved");
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
            <DialogTitle>Edit entry link</DialogTitle>
            <DialogDescription>The address and QR code stay the same, so printed copies keep working.</DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor={`entry-link-name-${link.id}`}>Name</FieldLabel>
            <Input
              id={`entry-link-name-${link.id}`}
              required
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor={`entry-link-automation-${link.id}`}>Automation to start</FieldLabel>
            <AutomationPicker
              id={`entry-link-automation-${link.id}`}
              automations={automations}
              value={automationId}
              onChange={setAutomationId}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={update.isPending} disabled={!name.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function QrDialog({ wid, link, onClose }: { wid: string; link: EntryLink | null; onClose: () => void }) {
  const qr = useEntryLinkQr(wid, link?.id ?? "", link !== null);
  const [src, setSrc] = useState<string | null>(null);
  const blob = qr.data;
  useEffect(() => {
    if (!blob) {
      setSrc(null);
      return;
    }
    const url = URL.createObjectURL(blob);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [blob]);

  return (
    <Dialog open={link !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{link?.name ?? "QR code"}</DialogTitle>
          <DialogDescription>Scan it with a phone camera to open a chat with you.</DialogDescription>
        </DialogHeader>
        <div className="grid place-items-center">
          {qr.isError ? (
            <ErrorState size="compact" error={qr.error} onRetry={() => void qr.refetch()} />
          ) : src ? (
            // eslint-disable-next-line @next/next/no-img-element -- a blob URL of the QR code
            <img src={src} alt={`QR code for ${link?.name ?? "the link"}`} className="size-56 bg-white p-2" />
          ) : (
            <Skeleton className="size-56" aria-label="Loading the QR code" />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
