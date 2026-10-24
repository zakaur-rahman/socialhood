"use client";

import { AlertTriangle, Download, FileUp } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import { useImportProducts, usePreviewProductImport } from "@/lib/api/queries";
import type { CatalogueLimits, CsvImportPreview, CsvImportRow } from "@/lib/api/types";
import { CSV_COLUMNS, CSV_TEMPLATE, readCsvFile } from "@/lib/catalogue/format";
import { errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

const ACTION: Record<CsvImportRow["action"], { label: string; tone: "success" | "brand" | "danger" }> = {
  create: { label: "New", tone: "success" },
  update: { label: "Update", tone: "brand" },
  error: { label: "Left out", tone: "danger" },
};

/** Offer the starter file as a download (a Blob, so nothing leaves the browser). */
function downloadTemplate() {
  const url = URL.createObjectURL(new Blob([CSV_TEMPLATE + "\n"], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "products-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Import products from a CSV file (GR-31): choose a file, see what each line would do (new, update
 * or left out and why), then import the valid lines. A line is matched by SKU, else by the product
 * name and variant; a blank cell never clears a value. The file is read again when it is imported.
 */
export function ImportDialog({
  open,
  onOpenChange,
  limits,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  limits: CatalogueLimits | undefined;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="xl">
        <DialogHeader>
          <DialogTitle>Import products from a CSV file</DialogTitle>
          <DialogDescription>
            Check the file here before anything is saved. Lines with a problem are left out; the rest are imported.
          </DialogDescription>
        </DialogHeader>
        {open ? <ImportBody limits={limits} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function ImportBody({ limits, onDone }: { limits: CatalogueLimits | undefined; onDone: () => void }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const preview = usePreviewProductImport(wid);
  const run = useImportProducts(wid);
  const upgrade = useUpgradeDialog();
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<CsvImportPreview | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [overLimit, setOverLimit] = useState<UpgradeRequest | null>(null);
  const canUpgrade = workspace.role === "owner" || workspace.role === "admin";

  const fail = (error: unknown) => {
    if (isPlanLimitError(error)) {
      setOverLimit(upgradeRequestFrom(error));
      return;
    }
    setProblem(errorMessage(error));
  };

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!chosen) return;
    setProblem(null);
    setOverLimit(null);
    setResult(null);
    const read = await readCsvFile(chosen);
    if ("error" in read) {
      setProblem(read.error);
      return;
    }
    setText(read.text);
    setFileName(chosen.name);
    preview.mutate(read.text, { onSuccess: setResult, onError: fail });
  };

  const importNow = () => {
    if (text === null) return;
    setProblem(null);
    run.mutate(text, {
      onSuccess: (done) => {
        toast.success(
          `Imported ${done.products} ${done.products === 1 ? "product" : "products"}` +
            (done.skipped ? `, ${done.skipped} ${done.skipped === 1 ? "line" : "lines"} left out` : ""),
        );
        onDone();
      },
      onError: fail,
    });
  };

  const importable = result ? result.create + result.update : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" onClick={() => fileRef.current?.click()} loading={preview.isPending}>
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

      {result === null ? (
        <details className="rounded-lg border border-line px-3 py-2 text-sm" open={!fileName}>
          <summary className="cursor-pointer font-medium">What the file needs</summary>
          <div className="mt-2 space-y-2 text-fg-secondary">
            <p>
              The first line is the header row. <strong className="text-fg">name</strong> and{" "}
              <strong className="text-fg">price</strong> are required; the other columns are optional:
            </p>
            <p className="font-mono text-xs break-words">{CSV_COLUMNS.join(", ")}</p>
            <ul className="list-disc space-y-1 ps-5">
              <li>One line is one product, or one variant of it. Lines with the same name are one product.</li>
              <li>A line with a variant (or option values) is a variant of that product, with its own price and stock.</li>
              <li>A line is matched by sku, else by the product name and variant. A match is updated.</li>
              <li>A blank cell never clears a value, and stock stays blank when you don&apos;t track it.</li>
              <li>
                {limits
                  ? `Your plan takes up to ${limits.import_row_cap.toLocaleString("en")} lines in one file.`
                  : "Your plan sets how many lines one file can have."}
              </li>
            </ul>
          </div>
        </details>
      ) : (
        <Summary preview={result} />
      )}

      {result ? <Lines rows={result.rows} total={result.total_rows} /> : null}

      {overLimit ? (
        <Alert
          tone="warning"
          urgent
          icon={<AlertTriangle />}
          action={
            canUpgrade ? (
              <AlertAction type="button" onClick={() => upgrade.open(overLimit.entitlement ? overLimit : COMMERCE_UPGRADE)}>
                Upgrade
              </AlertAction>
            ) : undefined
          }
        >
          {overLimit.code === "quota_exceeded"
            ? (overLimit.detail ?? "Your plan's import limit is reached.")
            : "The product catalogue is part of Pro."}
        </Alert>
      ) : null}
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
          {importable > 0 ? `Import ${importable} ${importable === 1 ? "line" : "lines"}` : "Import"}
        </Button>
      </div>
    </div>
  );
}

function Summary({ preview }: { preview: CsvImportPreview }) {
  return (
    <div className="space-y-2" aria-label="What the file would do">
      <p className="text-sm">
        {preview.total_rows} {preview.total_rows === 1 ? "line" : "lines"}: {preview.create} new, {preview.update} to
        update, {preview.errors} left out.
      </p>
      {preview.ignored_columns.length > 0 ? (
        <p className="text-xs text-fg-secondary">Not used: {preview.ignored_columns.join(", ")}.</p>
      ) : null}
    </div>
  );
}

function Lines({ rows, total }: { rows: CsvImportRow[]; total: number }) {
  return (
    <div className="max-h-80 overflow-y-auto rounded-lg border border-line">
      <Table scrollLabel="Lines in the file">
        <TableCaption className="sr-only">What each line of the file would do</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead className="w-14">Line</TableHead>
            <TableHead>Product</TableHead>
            <TableHead>Variant</TableHead>
            <TableHead>Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const action = ACTION[row.action];
            return (
              <TableRow key={row.line}>
                <TableCell className="text-fg-secondary">{row.line}</TableCell>
                <TableCell className="break-words">{row.name || "(no name)"}</TableCell>
                <TableCell className="break-words">{row.variant ?? ""}</TableCell>
                <TableCell className="space-y-1">
                  <Badge tone={action.tone}>{action.label}</Badge>
                  {row.errors.map((message) => (
                    <p key={message} className="text-xs text-danger-fg">
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
          Showing the first {rows.length} of {total} lines.
        </p>
      ) : null}
    </div>
  );
}
