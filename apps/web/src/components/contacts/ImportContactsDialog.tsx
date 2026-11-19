"use client";

import { Download, FileUp } from "lucide-react";
import { useId, useMemo, useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useImportContacts, usePreviewContactImport, useSocialAccounts } from "@/lib/api/queries";
import type { ContactImportPreview, ContactImportRow } from "@/lib/api/types";
import { CSV_MAX_CHARS } from "@/lib/catalogue/format";
import { errorMessage } from "@/lib/copy";
import { accountName } from "@/lib/inbox/format";
import { useCurrentWorkspace } from "@/lib/workspace";

export const IMPORT_TEMPLATE =
  "Phone,Name,Email,Tags,WhatsApp marketing\n+919876543210,Asha Rao,asha@example.com,vip; march,yes";

const ACTION: Record<ContactImportRow["action"], { label: string; tone: "success" | "brand" | "neutral" | "danger" }> = {
  create: { label: "New", tone: "success" },
  update: { label: "Update", tone: "brand" },
  unchanged: { label: "No change", tone: "neutral" },
  skip: { label: "Left out", tone: "danger" },
};

/** Offer the starter file as a download (a Blob, so nothing leaves the browser). */
function downloadTemplate() {
  const url = URL.createObjectURL(new Blob([IMPORT_TEMPLATE + "\n"], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "contacts-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Import contacts from a CSV file (GR-43), admins only, onto a WhatsApp number. The file has the
 * columns of the contacts export, so an exported file imports back as no change. Existing contacts
 * only get blanks filled and tags added. The "WhatsApp marketing" column counts only when the
 * admin ticks that these people agreed; it never overrides a STOP or any other withdrawal.
 */
export function ImportContactsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="xl">
        <DialogHeader>
          <DialogTitle>Import contacts from a CSV file</DialogTitle>
          <DialogDescription>
            Check the file here before anything is saved. Rows with a problem are left out; the rest are imported.
          </DialogDescription>
        </DialogHeader>
        {open ? <ImportBody onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function ImportBody({ onDone }: { onDone: () => void }) {
  const wid = useCurrentWorkspace().id;
  const accounts = useSocialAccounts(wid);
  const preview = usePreviewContactImport(wid);
  const run = useImportContacts(wid);
  const fileRef = useRef<HTMLInputElement>(null);
  const consentId = useId();
  const numbers = useMemo(
    () => (accounts.data ?? []).filter((a) => a.platform === "whatsapp" && a.status !== "disconnected"),
    [accounts.data],
  );
  const [picked, setPicked] = useState<string | null>(null);
  const accountId = picked ?? (numbers.length === 1 ? numbers[0].id : null);
  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [result, setResult] = useState<ContactImportPreview | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  // The preview is read again whenever the file, the number or the tick changes.
  const check = (csv: string | null, account: string | null, tick: boolean, name = fileName) => {
    setResult(null);
    setProblem(null);
    if (csv === null || account === null) return;
    preview.mutate(
      { account_id: account, csv, grant_consent: tick, file_name: name },
      { onSuccess: setResult, onError: (error) => setProblem(errorMessage(error)) },
    );
  };

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!chosen) return;
    const content = chosen.size > CSV_MAX_CHARS ? null : await chosen.text();
    if (content === null || content.length > CSV_MAX_CHARS) {
      setText(null);
      setResult(null);
      setProblem("That file is too large. Split it into smaller files.");
      return;
    }
    setText(content);
    setFileName(chosen.name);
    check(content, accountId, agreed, chosen.name);
  };

  const importNow = () => {
    if (text === null || accountId === null) return;
    setProblem(null);
    run.mutate(
      { account_id: accountId, csv: text, grant_consent: agreed, file_name: fileName },
      {
        onSuccess: (done) => {
          const people = done.created + done.updated;
          toast.success(
            `Imported ${done.created} new and ${done.updated} updated ${people === 1 ? "contact" : "contacts"}` +
              (done.skipped ? `, ${done.skipped} ${done.skipped === 1 ? "row" : "rows"} left out` : ""),
          );
          onDone();
        },
        onError: (error) => setProblem(errorMessage(error)),
      },
    );
  };

  const importable = result ? result.created + result.updated : 0;

  return (
    <div className="space-y-4">
      {numbers.length === 0 && !accounts.isPending ? (
        <p className="text-sm text-fg-secondary">
          Contacts can only be imported to a WhatsApp number. Connect one first; Instagram contacts appear when they
          message or comment.
        </p>
      ) : (
        <>
          {numbers.length > 1 ? (
            <Select
              value={accountId ?? ""}
              onValueChange={(value) => {
                setPicked(value);
                check(text, value, agreed);
              }}
            >
              <SelectTrigger aria-label="WhatsApp number" className="w-full sm:w-72">
                <SelectValue placeholder="Choose a WhatsApp number" />
              </SelectTrigger>
              <SelectContent>
                {numbers.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {accountName(account)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => fileRef.current?.click()}
              loading={preview.isPending}
              disabled={accountId === null}
            >
              <FileUp aria-hidden /> {fileName ? "Choose another file" : "Choose a CSV file"}
            </Button>
            <Button type="button" variant="ghost" onClick={downloadTemplate}>
              <Download aria-hidden /> Download a starter file
            </Button>
            {fileName ? <span className="min-w-0 truncate text-sm text-fg-secondary">{fileName}</span> : null}
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={onFile}
              data-testid="csv-file-input"
            />
          </div>

          <div className="flex items-start gap-2 text-sm">
            <Checkbox
              id={consentId}
              checked={agreed}
              onCheckedChange={(on) => {
                setAgreed(on === true);
                check(text, accountId, on === true);
              }}
              className="mt-0.5"
            />
            <label htmlFor={consentId}>
              These people agreed to get WhatsApp marketing from us
              <span className="block text-xs text-fg-secondary">
                Without this, the &ldquo;WhatsApp marketing&rdquo; column is ignored. Each yes is saved with who imported
                it, when, the file name and the row. Anyone who replied STOP stays opted out.
              </span>
            </label>
          </div>
        </>
      )}

      {result === null ? (
        <details className="rounded-lg border border-line px-3 py-2 text-sm" open={!fileName}>
          <summary className="cursor-pointer font-medium">What the file needs</summary>
          <div className="mt-2 space-y-2 text-fg-secondary">
            <p>
              The first line is the header row, in the same columns as the contacts export, so an exported file imports
              back as no change. <strong className="text-fg">Phone</strong> is required; the others are optional:
            </p>
            <p className="font-mono text-xs break-words">
              Phone, Name, Email, Tags, WhatsApp marketing, and one column for each custom field
            </p>
            <ul className="list-disc space-y-1 ps-5">
              <li>Separate tags with a semicolon, like vip; march.</li>
              <li>A contact that already exists only gets blanks filled and tags added. Nothing typed is overwritten.</li>
              <li>Up to 5,000 rows in one file.</li>
            </ul>
          </div>
        </details>
      ) : (
        <Summary preview={result} />
      )}

      {result ? <Rows rows={result.rows} total={result.total_rows} /> : null}

      {problem ? (
        <p role="alert" className="text-sm text-danger-fg">
          {problem}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="button" onClick={importNow} loading={run.isPending} disabled={importable === 0}>
          {importable > 0 ? `Import ${importable.toLocaleString("en")} ${importable === 1 ? "contact" : "contacts"}` : "Import"}
        </Button>
      </div>
    </div>
  );
}

function Summary({ preview }: { preview: ContactImportPreview }) {
  return (
    <div className="space-y-1" aria-label="What the file would do">
      <p className="text-sm">
        {preview.total_rows} {preview.total_rows === 1 ? "row" : "rows"}: {preview.created} new, {preview.updated} to
        update, {preview.unchanged} unchanged, {preview.skipped} left out.
      </p>
      {preview.consents_granted > 0 ? (
        <p className="text-xs text-fg-secondary">{preview.consents_granted} will be marked as agreed to WhatsApp marketing.</p>
      ) : null}
      {preview.consent_ignored > 0 ? (
        <p className="text-xs text-fg-secondary">
          {preview.consent_ignored} said yes to WhatsApp marketing, but that is ignored until you tick the box above.
        </p>
      ) : null}
      {preview.consents_kept_withdrawn > 0 ? (
        <p className="text-xs text-fg-secondary">
          {preview.consents_kept_withdrawn} withdrew their consent earlier, so they stay opted out.
        </p>
      ) : null}
      {preview.ignored_columns.length > 0 ? (
        <p className="text-xs text-fg-secondary">Not used: {preview.ignored_columns.join(", ")}.</p>
      ) : null}
    </div>
  );
}

function Rows({ rows, total }: { rows: ContactImportRow[]; total: number }) {
  return (
    <div className="max-h-80 overflow-y-auto rounded-lg border border-line">
      <Table scrollLabel="Rows in the file">
        <TableCaption className="sr-only">What each row of the file would do</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead className="w-14">Row</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const action = ACTION[row.action];
            return (
              <TableRow key={row.line}>
                <TableCell className="text-fg-secondary">{row.line}</TableCell>
                <TableCell className="break-words">{row.phone || "(no number)"}</TableCell>
                <TableCell className="space-y-1">
                  <Badge tone={action.tone}>{action.label}</Badge>
                  {(row.reasons ?? []).map((message) => (
                    <p key={message} className={row.action === "skip" ? "text-xs text-danger-fg" : "text-xs text-fg-secondary"}>
                      {message}
                    </p>
                  ))}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {rows.length < total ? (
        <p className="border-t border-line px-3 py-2 text-xs text-fg-secondary">
          Showing the first {rows.length} of {total} rows.
        </p>
      ) : null}
    </div>
  );
}
