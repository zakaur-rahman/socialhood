"use client";

import { ArrowDown, ArrowUp, ExternalLink, FileSpreadsheet, Plus, Send, Trash2, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { SettingsCard, SectionLabel } from "@/components/settings/SettingsCard";
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
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import {
  useCompleteGoogleConnect,
  useCreateGoogleSheet,
  useDisconnectGoogleSheets,
  useGoogleSheets,
  useSaveSheetMapping,
  useSelectGoogleSheet,
  useSendSheetTest,
  useStartGoogleConnect,
} from "@/lib/api/queries";
import type { GoogleSheetColumn, GoogleSheetRow, GoogleSheetsStatus } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import {
  addColumn,
  canSave,
  fieldLabel,
  moveColumn,
  removeColumn,
  renameColumn,
  sameColumns,
  unusedFields,
} from "./sheetMapping";

const DEFAULT_TITLE = "Social Hood leads";

const ROW: Record<GoogleSheetRow["status"], { label: string; tone: "success" | "warning" | "danger" }> = {
  succeeded: { label: "Added", tone: "success" },
  pending: { label: "Waiting", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};

/** What the callback's ?error= means, in plain words. */
const CALLBACK_ERRORS: Record<string, string> = {
  access_denied: "Google wasn't connected: you cancelled it.",
  connect_failed: "Google didn't respond. Try connecting again.",
};

/** The reasons the API refuses the nonce, in the screen's words. */
function completeMessage(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.status === 404) return "That connection link expired. Connect Google again.";
  if (error.status === 403)
    return "This Google connection was started by someone else, so it wasn't added. To connect your own account, use Connect Google.";
  return null;
}

/**
 * Settings › Integrations, Google Sheets (GR-27): connect a Google account (the narrow drive.file
 * access: Social Hood can only use sheets it makes, or that Google lets it open), make or choose a
 * sheet, say which field goes in which column, send a test row and see how the latest rows did.
 * Every captured lead is added as a new row. Owners and admins.
 */
export function GoogleSheetsCard({ wid }: { wid: string }) {
  const status = useGoogleSheets(wid);
  useGoogleReturn(wid);

  return (
    <SettingsCard
      id="google-sheets"
      icon={<FileSpreadsheet />}
      title="Google Sheets"
      description="Add every lead you capture to a Google Sheet as a new row."
      aside={status.data ? <ConnectionBadge status={status.data} /> : undefined}
    >
      {status.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : status.isError ? (
        <p className="text-sm text-fg-secondary">Couldn&rsquo;t load Google Sheets. Reload the page to try again.</p>
      ) : (
        <Body wid={wid} status={status.data} />
      )}
    </SettingsCard>
  );
}

/** The OAuth callback sends the browser back with ?google=<nonce> (finish once) or ?error=. */
function useGoogleReturn(wid: string) {
  const params = useSearchParams();
  const complete = useCompleteGoogleConnect(wid);
  const { mutate: finish } = complete;
  const handled = useRef(false);
  const nonce = params?.get("google") ?? null;
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
      onSuccess: () => toast.success("Google connected. Create or choose a sheet next."),
      onError: (failure) => {
        const message = completeMessage(failure);
        if (message) toast.error(message);
        else toastError(failure, "Google didn't respond. Try connecting again.");
      },
    });
  }, [nonce, error, finish]);
}

function ConnectionBadge({ status }: { status: GoogleSheetsStatus }) {
  if (!status.connected) return <Badge tone="neutral">Not connected</Badge>;
  if (status.status === "needs_reconnect") return <Badge tone="danger">Reconnect needed</Badge>;
  return <Badge tone="success">Connected</Badge>;
}

function Body({ wid, status }: { wid: string; status: GoogleSheetsStatus }) {
  const { slug } = useCurrentWorkspace();
  if (!status.available) {
    return <p className="text-sm text-fg-secondary">Google Sheets isn&rsquo;t set up on this server yet.</p>;
  }
  if (!status.entitled) {
    return (
      <p className="text-sm text-fg-secondary">
        Google Sheets sync is part of Pro.{" "}
        <Link href={`/w/${slug}/settings/billing` as Route} className="text-brand-fg underline-offset-4 hover:underline">
          See plans
        </Link>
      </p>
    );
  }
  if (!status.connected) return <Connect wid={wid} />;
  return <Connected wid={wid} status={status} />;
}

function Connect({ wid, reconnect = false }: { wid: string; reconnect?: boolean }) {
  const start = useStartGoogleConnect(wid);
  return (
    <div className="space-y-2">
      {reconnect ? null : (
        <p className="text-sm text-fg-secondary">
          Social Hood asks Google for the narrowest access: it can use only the sheets it makes for you, never the
          rest of your Drive.
        </p>
      )}
      <Button
        loading={start.isPending}
        onClick={() =>
          start.mutate(undefined, {
            onSuccess: (url) => browser.assign(url),
            onError: (error) => toastError(error),
          })
        }
      >
        {reconnect ? "Reconnect Google" : "Connect Google"}
      </Button>
    </div>
  );
}

function Connected({ wid, status }: { wid: string; status: GoogleSheetsStatus }) {
  const test = useSendSheetTest(wid);
  const [confirming, setConfirming] = useState(false);
  const needsReconnect = status.status === "needs_reconnect";
  const sheet = status.sheet;

  return (
    <div className="space-y-6">
      <p className="text-sm text-fg-secondary">
        {status.google_email ? <>Connected as {status.google_email}.</> : "Connected to Google."}
      </p>
      {needsReconnect ? (
        <div className="space-y-2">
          <Alert tone="danger" urgent>
            {status.last_error ?? "Access was removed: reconnect Google in Settings, under Integrations."}
          </Alert>
          <Connect wid={wid} reconnect />
        </div>
      ) : status.last_error ? (
        <Alert tone="warning">{status.last_error}</Alert>
      ) : null}

      <SheetPicker wid={wid} status={status} disabled={needsReconnect} />
      {needsReconnect ? null : <Columns wid={wid} status={status} />}

      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!sheet || needsReconnect}
          loading={test.isPending}
          onClick={() =>
            test.mutate(undefined, {
              onSuccess: () => toast.success("Test row added to your sheet."),
              onError: (error) => toastError(error),
            })
          }
        >
          <Send aria-hidden /> Send a test row
        </Button>
        <Button variant="destructive-ghost" size="sm" onClick={() => setConfirming(true)}>
          <Trash2 aria-hidden /> Disconnect
        </Button>
      </div>

      <Rows status={status} />
      <Disconnect wid={wid} open={confirming} onOpenChange={setConfirming} />
    </div>
  );
}

function SheetPicker({ wid, status, disabled }: { wid: string; status: GoogleSheetsStatus; disabled: boolean }) {
  const create = useCreateGoogleSheet(wid);
  const select = useSelectGoogleSheet(wid);
  const [changing, setChanging] = useState(false);
  const [title, setTitle] = useState(DEFAULT_TITLE);
  const [link, setLink] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const sheet = status.sheet;
  const open = !sheet || changing;

  function submitLink(event: React.FormEvent) {
    event.preventDefault();
    setLinkError(null);
    select.mutate(link, {
      onSuccess: () => {
        setLink("");
        setChanging(false);
        toast.success("Leads will be added to that sheet.");
      },
      onError: (error) => {
        const field = error instanceof ApiError ? error.errors.find((e) => e.field === "link") : undefined;
        if (field) setLinkError(field.message);
        else toastError(error);
      },
    });
  }

  return (
    <div className="space-y-3">
      <SectionLabel>Sheet</SectionLabel>
      {sheet ? (
        <p className="flex flex-wrap items-center gap-x-2 text-sm">
          <a
            href={sheet.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-brand-fg underline-offset-4 hover:underline"
          >
            {sheet.title || "Your sheet"} <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <span className="text-fg-secondary">(tab {sheet.tab})</span>
          {disabled ? null : (
            <Button variant="ghost" size="xs" onClick={() => setChanging((value) => !value)}>
              {changing ? "Keep this sheet" : "Change sheet"}
            </Button>
          )}
        </p>
      ) : (
        <p className="text-sm text-fg-secondary">No sheet yet. Leads you capture wait until you pick one.</p>
      )}
      {open && !disabled ? (
        <div className="grid gap-4 md:grid-cols-2">
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate(title.trim() || DEFAULT_TITLE, {
                onSuccess: () => {
                  setChanging(false);
                  toast.success("Sheet created in your Google Drive.");
                },
                onError: (error) => toastError(error),
              });
            }}
          >
            <Field>
              <FieldLabel htmlFor="sheet-title">New sheet name</FieldLabel>
              <Input id="sheet-title" maxLength={100} value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <Button type="submit" size="sm" loading={create.isPending}>
              <Plus aria-hidden /> Create sheet
            </Button>
          </form>
          <form className="space-y-2" onSubmit={submitLink}>
            <Field invalid={Boolean(linkError)}>
              <FieldLabel htmlFor="sheet-link">Or use a sheet by its link</FieldLabel>
              <Input
                id="sheet-link"
                maxLength={300}
                placeholder="https://docs.google.com/spreadsheets/d/…"
                value={link}
                aria-invalid={linkError ? true : undefined}
                aria-describedby={linkError ? "sheet-link-error" : undefined}
                onChange={(e) => setLink(e.target.value)}
              />
              {linkError ? (
                <p id="sheet-link-error" className="text-sm text-danger-fg">
                  {linkError}
                </p>
              ) : null}
            </Field>
            <Button type="submit" size="sm" variant="secondary" disabled={!link.trim()} loading={select.isPending}>
              Use this sheet
            </Button>
          </form>
        </div>
      ) : null}
    </div>
  );
}

/** Which field goes in which column. Edited here, saved with one button. */
function Columns({ wid, status }: { wid: string; status: GoogleSheetsStatus }) {
  const save = useSaveSheetMapping(wid);
  const [edits, setEdits] = useState<GoogleSheetColumn[] | null>(null);
  const saved = status.columns ?? [];
  const fields = status.fields ?? [];
  const columns = edits ?? saved;
  const dirty = edits !== null && !sameColumns(edits, saved);
  const unused = unusedFields(fields, columns);
  const change = (next: GoogleSheetColumn[]) => setEdits(next);

  return (
    <div className="space-y-3">
      <SectionLabel>Columns</SectionLabel>
      <p className="text-sm text-fg-secondary">
        One column for each field, in this order. The header is the column&rsquo;s name in the first row of a sheet
        Social Hood made; a sheet you already had keeps its own first row.
      </p>
      <ul className="space-y-2" aria-label="Columns">
        {columns.map((column, index) => {
          const label = fieldLabel(fields, column.field);
          return (
            <li key={column.field} className="flex flex-wrap items-center gap-2" data-testid="sheet-column">
              <span className="w-28 shrink-0 text-sm text-fg-secondary">{label}</span>
              <Input
                aria-label={`Header for ${label}`}
                className="min-w-40 flex-1"
                maxLength={100}
                value={column.header}
                onChange={(e) => change(renameColumn(columns, index, e.target.value))}
              />
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Move ${label} up`}
                disabled={index === 0}
                onClick={() => change(moveColumn(columns, index, -1))}
              >
                <ArrowUp aria-hidden />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Move ${label} down`}
                disabled={index === columns.length - 1}
                onClick={() => change(moveColumn(columns, index, 1))}
              >
                <ArrowDown aria-hidden />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${label}`}
                disabled={columns.length === 1}
                onClick={() => change(removeColumn(columns, index))}
              >
                <X aria-hidden />
              </Button>
            </li>
          );
        })}
      </ul>
      {unused.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Add a column">
          {unused.map((option) => (
            <Button key={option.field} variant="outline" size="xs" onClick={() => change(addColumn(columns, option))}>
              <Plus aria-hidden /> {option.label}
            </Button>
          ))}
        </div>
      ) : null}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!dirty || !canSave(columns)}
          loading={save.isPending}
          onClick={() =>
            save.mutate(columns, {
              onSuccess: () => {
                setEdits(null);
                toast.success("Columns saved.");
              },
              onError: (error) => toastError(error),
            })
          }
        >
          Save columns
        </Button>
        {dirty ? (
          <Button variant="ghost" size="sm" onClick={() => setEdits(null)}>
            Undo changes
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function Rows({ status }: { status: GoogleSheetsStatus }) {
  const recent = status.recent ?? [];
  if (recent.length === 0) {
    return status.sheet ? (
      <p className="text-sm text-fg-secondary">No rows yet. A lead you capture shows up here and in your sheet.</p>
    ) : null;
  }
  return (
    <div className="space-y-2">
      <SectionLabel>Latest rows</SectionLabel>
      <p className="text-sm text-fg-secondary">
        {status.pending_rows} waiting, {status.failed_rows} failed.
      </p>
      <ul className="divide-y divide-line-subtle" aria-label="Latest rows">
        {recent.map((row) => {
          const state = ROW[row.status];
          return (
            <li key={row.id} data-testid="sheet-row" className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <Badge tone={state.tone}>{state.label}</Badge>
              <span className="text-fg-secondary">{relativeTime(row.last_attempt_at ?? row.created_at)}</span>
              {row.attempts > 1 ? <span className="text-fg-secondary">{row.attempts} attempts</span> : null}
              {row.error ? <span className="basis-full text-fg-secondary">{row.error}</span> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Disconnect({
  wid,
  open,
  onOpenChange,
}: {
  wid: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const disconnect = useDisconnectGoogleSheets(wid);
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect Google?</AlertDialogTitle>
          <AlertDialogDescription>
            New leads stop going to your sheet and rows still waiting are dropped. The sheet and the rows already in it
            stay in your Google Drive.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() =>
              disconnect.mutate(undefined, {
                onSuccess: () => toast.success("Google disconnected"),
                onError: (error) => toastError(error),
              })
            }
          >
            Disconnect Google
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
