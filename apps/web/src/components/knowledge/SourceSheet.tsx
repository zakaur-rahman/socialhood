"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useApi, useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import { keys, useCreateKnowledgeSource, useUpdateKnowledgeSource } from "@/lib/api/queries";
import type {
  KnowledgeSource,
  KnowledgeSourceCreate,
  KnowledgeSourceList,
  KnowledgeSourcePatch,
  KnowledgeType,
  MediaAsset,
} from "@/lib/api/types";
import { errorMessage, knowledgeLimitReached } from "@/lib/copy";
import { formatBytes } from "@/lib/inbox/format";
import { KNOWLEDGE_FILE_RULE, UploadError, uploadAsset } from "@/lib/media/upload";
import { useCurrentWorkspace } from "@/lib/workspace";

/** Tests inject a fake; the app uploads through the API and Cloudinary as a raw asset. */
export type KnowledgeUploader = (
  file: File,
  options: { onProgress: (fraction: number) => void; signal: AbortSignal },
) => Promise<MediaAsset>;

export type SourceSheetMode =
  | {
      kind: "create";
      type: KnowledgeType;
      /** "Add answer" (F-17) and "Add to knowledge" (F-08) prefill the customer's question. */
      question?: string;
      gapId?: string;
    }
  | { kind: "edit"; source: KnowledgeSource };

export const SOURCE_TYPE_LABEL: Record<KnowledgeType, string> = {
  faq: "FAQ",
  text: "Note",
  url: "Web page",
  file: "File",
};

const TITLES: Record<KnowledgeType, { create: string; edit: string; hint: string }> = {
  faq: { create: "Add an FAQ", edit: "Edit FAQ", hint: "A question customers ask and the answer you give." },
  text: { create: "Add a note", edit: "Edit note", hint: "Policies and details in your own words, like shipping or returns." },
  url: { create: "Add a web page", edit: "Edit web page", hint: "One page, such as your FAQ or shipping page. Its main text is read." },
  file: { create: "Add a file", edit: "Edit file", hint: "PDF, DOCX, TXT or MD, up to 10 MB." },
};

const values = z.object({
  title: z.string().trim().max(120, "Use 120 characters or fewer."),
  question: z.string().trim().max(500, "Use 500 characters or fewer."),
  body: z.string().trim().max(20000, "Use 20,000 characters or fewer."),
  url: z.string().trim().max(2000, "Use 2,000 characters or fewer."),
});
type Values = z.infer<typeof values>;

function isWebAddress(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") && Boolean(url.hostname.includes("."));
  } catch {
    return false;
  }
}

function schemaFor(type: KnowledgeType) {
  return values.superRefine((v, ctx) => {
    const need = (path: keyof Values, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
    if (type === "faq") {
      if (!v.question) need("question", "Enter the customer's question.");
      if (!v.body) need("body", "Enter the answer.");
    } else if (type === "text") {
      if (!v.title) need("title", "Enter a title.");
      if (!v.body) need("body", "Enter the text.");
    } else if (type === "url") {
      if (!isWebAddress(v.url)) need("url", "Enter a web address starting with http:// or https://.");
    }
  });
}

function initialValues(mode: SourceSheetMode): Values {
  if (mode.kind === "edit") {
    const s = mode.source;
    return { title: s.title ?? "", question: s.question ?? "", body: s.body ?? "", url: s.url ?? "" };
  }
  return { title: "", question: mode.question ?? "", body: "", url: "" };
}

/**
 * F-14 "Add knowledge" and edits: a right sheet with the form for an FAQ, a note, a web page or a
 * file (signed upload as raw). With a gap id, saving an FAQ answers that gap (F-17).
 */
export function SourceSheet({
  mode,
  onOpenChange,
  onSaved,
  upload,
}: {
  /** null: closed. */
  mode: SourceSheetMode | null;
  onOpenChange: (open: boolean) => void;
  onSaved?: (source: KnowledgeSource) => void;
  upload?: KnowledgeUploader;
}) {
  const type = mode ? (mode.kind === "edit" ? mode.source.type : mode.type) : "faq";
  const copy = TITLES[type];
  // No Radix trigger opens it (a menu item, Edit, Train AI, Add answer), so focus goes back by hand to
  // what had it (UX-A11Y-02); Radix alone left it on <body>.
  const returnFocus = useReturnFocus();
  return (
    <Sheet open={Boolean(mode)} onOpenChange={onOpenChange}>
      {/* The raised overlay surface and its shadow come from SheetContent (D-12). `panel`: the full screen
          below 768 px and 420 px beside the page from there (the call-site `w-full sm:max-w-md` lost to
          the default size's three-quarter width, 281 px on a 375 px phone). */}
      <SheetContent side="right" size="panel" className="gap-0 overflow-y-auto p-0" {...returnFocus}>
        <SheetHeader className="border-b border-line p-4 pr-12">
          <SheetTitle>{mode?.kind === "edit" ? copy.edit : copy.create}</SheetTitle>
          <SheetDescription>{copy.hint}</SheetDescription>
        </SheetHeader>
        {mode ? (
          <SourceForm
            // A new prefill or source is a new form.
            key={mode.kind === "edit" ? `edit-${mode.source.id}` : `create-${mode.type}-${mode.gapId ?? ""}-${mode.question ?? ""}`}
            mode={mode}
            type={type}
            upload={upload}
            onDone={(source) => {
              onSaved?.(source);
              onOpenChange(false);
            }}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function SourceForm({
  mode,
  type,
  upload,
  onDone,
  onCancel,
}: {
  mode: SourceSheetMode;
  type: KnowledgeType;
  upload?: KnowledgeUploader;
  onDone: (source: KnowledgeSource) => void;
  onCancel: () => void;
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const api = useApi();
  const queryClient = useQueryClient();
  const create = useCreateKnowledgeSource(wid);
  const update = useUpdateKnowledgeSource(wid);
  const editing = mode.kind === "edit";
  const form = useForm<Values>({ resolver: zodResolver(schemaFor(type)), defaultValues: initialValues(mode) });
  const { errors } = form.formState;
  const [reingest, setReingest] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [overLimit, setOverLimit] = useState<UpgradeRequest | null>(null);
  const upgrade = useUpgradeDialog();
  const fileRef = useRef<HTMLInputElement>(null);
  const saving = create.isPending || update.isPending || progress !== null;

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!chosen) return;
    const problem = KNOWLEDGE_FILE_RULE.check(chosen);
    setFileError(problem);
    setFile(problem ? null : chosen);
  };

  const fail = (error: unknown) => {
    setProgress(null);
    if (isPlanLimitError(error)) {
      // The form keeps what was typed and says which limit stopped it, with Upgrade opening the
      // dialog (the create opts out of the automatic one: INLINE_PLAN_LIMITS).
      setOverLimit(upgradeRequestFrom(error));
      return;
    }
    if (error instanceof ApiError && error.errors.length > 0) {
      for (const field of error.errors) {
        if (field.field in form.getValues()) form.setError(field.field as keyof Values, { message: field.message });
        else setFormError(field.message);
      }
      return;
    }
    setFormError(error instanceof UploadError ? error.message : errorMessage(error));
  };

  const uploadFile = async (chosen: File): Promise<MediaAsset> => {
    setProgress(0);
    const options = { onProgress: setProgress, signal: new AbortController().signal };
    return upload
      ? upload(chosen, options)
      : uploadAsset(api, wid, chosen, { ...options, purpose: "knowledge", resourceType: "raw" });
  };

  const submit = form.handleSubmit(async (v) => {
    setFormError(null);
    setOverLimit(null);
    if (mode.kind === "edit") {
      const before = initialValues(mode);
      const patch: Partial<KnowledgeSourcePatch> = {};
      for (const key of ["title", "question", "body", "url"] as const) {
        if (v[key] !== before[key].trim()) patch[key] = v[key] || null;
      }
      if (reingest) patch.reingest = true;
      if (Object.keys(patch).length === 0) return onCancel();
      update.mutate(
        { id: mode.source.id, patch },
        {
          onSuccess: (source) => {
            toast.success("Saved. The AI uses the new version once it's processed.");
            onDone(source);
          },
          onError: fail,
        },
      );
      return;
    }
    let body: KnowledgeSourceCreate;
    if (type === "faq") body = { type, question: v.question, body: v.body, gap_id: mode.gapId ?? null };
    else if (type === "text") body = { type, title: v.title, body: v.body };
    else if (type === "url") body = { type, url: v.url, title: v.title || null };
    else {
      if (!file) return setFileError("Choose a file.");
      try {
        const asset = await uploadFile(file);
        body = { type, file_asset_id: asset.id, title: v.title || null };
      } catch (error) {
        return fail(error);
      }
    }
    create.mutate(body, {
      onSuccess: (source) => {
        setProgress(null);
        toast.success("Added to knowledge");
        onDone(source);
      },
      onError: fail,
    });
  });

  const limit = queryClient.getQueryData<KnowledgeSourceList>(keys.knowledgeSources(wid))?.usage.characters_limit;

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5 p-4" aria-label={editing ? TITLES[type].edit : TITLES[type].create}>
      {type === "faq" ? (
        <>
          <Field id="source-question" label="Question" error={errors.question?.message}>
            <Input id="source-question" maxLength={500} aria-invalid={!!errors.question} {...form.register("question")} />
          </Field>
          <Field id="source-body" label="Answer" error={errors.body?.message}>
            <Textarea id="source-body" rows={6} aria-invalid={!!errors.body} {...form.register("body")} />
          </Field>
        </>
      ) : null}
      {type === "text" ? (
        <>
          <Field id="source-title" label="Title" hint="For example: Shipping policy" error={errors.title?.message}>
            <Input id="source-title" maxLength={120} aria-invalid={!!errors.title} {...form.register("title")} />
          </Field>
          <Field id="source-body" label="Text" error={errors.body?.message}>
            <Textarea id="source-body" rows={10} aria-invalid={!!errors.body} {...form.register("body")} />
          </Field>
        </>
      ) : null}
      {type === "url" ? (
        <>
          <Field id="source-url" label="Web address" error={errors.url?.message}>
            <Input
              id="source-url"
              type="url"
              inputMode="url"
              placeholder="https://"
              aria-invalid={!!errors.url}
              {...form.register("url")}
            />
          </Field>
          <Field id="source-title" label="Title (optional)" hint="The page title is used when this is empty." error={errors.title?.message}>
            <Input id="source-title" maxLength={120} {...form.register("title")} />
          </Field>
        </>
      ) : null}
      {type === "file" ? (
        <>
          {editing ? (
            <p className="flex items-center gap-2 rounded-lg border border-line bg-field px-3 py-2 text-sm">
              <FileText className="size-4 shrink-0 text-fg-secondary" aria-hidden />
              <span className="truncate">{mode.kind === "edit" ? (mode.source.file_name ?? mode.source.title) : ""}</span>
            </p>
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="source-file">File</Label>
              <div className="flex items-center gap-3 rounded-lg border border-dashed border-line-strong bg-field px-3 py-3">
                <Button type="button" variant="secondary" size="sm" onClick={() => fileRef.current?.click()} disabled={saving}>
                  Choose file
                </Button>
                <span className="min-w-0 flex-1 truncate text-sm text-fg-secondary">
                  {file ? `${file.name} · ${formatBytes(file.size)}` : "No file chosen"}
                </span>
                <input
                  ref={fileRef}
                  id="source-file"
                  type="file"
                  className="sr-only"
                  accept={KNOWLEDGE_FILE_RULE.accept}
                  onChange={onFile}
                  data-testid="knowledge-file-input"
                />
              </div>
              {progress !== null ? (
                <div
                  role="progressbar"
                  aria-label="Uploading"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(progress * 100)}
                  className="h-1.5 overflow-hidden rounded-full bg-raised"
                >
                  <span className="bg-brand-gradient-decor block h-full" style={{ width: `${Math.round(progress * 100)}%` }} />
                </div>
              ) : null}
              {fileError ? (
                <p role="alert" className="text-sm text-danger-fg">
                  {fileError}
                </p>
              ) : (
                <p className="text-xs text-fg-secondary">PDF, DOCX, TXT or MD, up to 10 MB.</p>
              )}
            </div>
          )}
          <Field id="source-title" label="Title (optional)" hint="The file name is used when this is empty." error={errors.title?.message}>
            <Input id="source-title" maxLength={120} {...form.register("title")} />
          </Field>
        </>
      ) : null}
      {editing && (type === "url" || type === "file") ? (
        <div className="flex items-center gap-3">
          <Checkbox id="source-reingest" checked={reingest} onCheckedChange={(value) => setReingest(value === true)} />
          <Label htmlFor="source-reingest" className="font-normal">
            {type === "url" ? "Fetch the page again" : "Read the file again"}
          </Label>
        </div>
      ) : null}

      {overLimit ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
          <p className="flex-1">
            {knowledgeLimitReached(overLimit.limit ?? limit)} Remove a source or upgrade for more.
          </p>
          {workspace.role === "owner" || workspace.role === "admin" ? (
            // A banner action (DESIGN_SYSTEM §11): `secondary`, small.
            <Button type="button" variant="secondary" size="sm" onClick={() => upgrade.open(overLimit)}>
              Upgrade
            </Button>
          ) : null}
        </div>
      ) : null}
      {formError ? (
        <p role="alert" className="text-sm text-danger-fg">
          {formError}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {progress !== null ? "Uploading…" : saving ? "Saving…" : editing ? "Save" : "Add"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p role="alert" className="text-sm text-danger-fg">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-fg-secondary">{hint}</p>
      ) : null}
    </div>
  );
}
