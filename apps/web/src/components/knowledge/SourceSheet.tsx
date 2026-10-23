"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileText, Network } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { CardInset } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useApi, useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import { keys, useCreateKnowledgeSource, useUpdateKnowledgeSource } from "@/lib/api/queries";
import type {
  KnowledgeCreateType,
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
      type: KnowledgeCreateType;
      /** "Add answer", from the gap banner (F-17) and from a suggestion (F-08), prefills the customer's question. */
      question?: string;
      gapId?: string;
    }
  | { kind: "edit"; source: KnowledgeSource };

export const SOURCE_TYPE_LABEL: Record<KnowledgeType, string> = {
  faq: "FAQ",
  text: "Note",
  url: "Web page",
  file: "File",
  site: "Website",
  page: "Page",
};

const TITLES: Record<KnowledgeType, { create: string; edit: string; hint: string }> = {
  faq: { create: "Add an answer", edit: "Edit FAQ", hint: "A question customers ask and the answer you give." },
  text: { create: "Add a note", edit: "Edit note", hint: "Policies and details in your own words, like shipping or returns." },
  url: { create: "Add a web page", edit: "Edit web page", hint: "One page, such as your FAQ or shipping page. Its main text is read." },
  file: { create: "Add a file", edit: "Edit file", hint: "PDF, DOCX, TXT or MD, up to 10 MB." },
  site: {
    create: "Add a website",
    edit: "Edit website",
    hint: "Reads the pages of your site, starting from this address. It follows the sitemap and links on the same site and respects robots.txt.",
  },
  page: { create: "Add a page", edit: "Page", hint: "" },
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
    } else if (type === "url" || type === "site") {
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
  // A website: check it again every week (the default), or only when asked.
  const [weekly, setWeekly] = useState(mode.kind === "edit" ? mode.source.site?.recrawl !== "off" : true);
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
      if (type === "site" && weekly !== (mode.source.site?.recrawl !== "off")) patch.recrawl = weekly ? "weekly" : "off";
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
    else if (type === "site") body = { type, url: v.url, title: v.title || null, recrawl: weekly ? "weekly" : "off" };
    else {
      if (!file) return setFileError("Choose a file.");
      try {
        const asset = await uploadFile(file);
        body = { type: "file", file_asset_id: asset.id, title: v.title || null };
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
          <Field id="source-question" invalid={!!errors.question}>
            <FieldLabel>Question</FieldLabel>
            <Input maxLength={500} {...form.register("question")} />
            <FieldError>{errors.question?.message}</FieldError>
          </Field>
          <Field id="source-body" invalid={!!errors.body}>
            <FieldLabel>Answer</FieldLabel>
            <Textarea rows={6} {...form.register("body")} />
            <FieldError>{errors.body?.message}</FieldError>
          </Field>
        </>
      ) : null}
      {type === "text" ? (
        <>
          <Field id="source-title" invalid={!!errors.title}>
            <FieldLabel>Title</FieldLabel>
            <Input maxLength={120} {...form.register("title")} />
            <FieldDescription>For example: Shipping policy</FieldDescription>
            <FieldError>{errors.title?.message}</FieldError>
          </Field>
          <Field id="source-body" invalid={!!errors.body}>
            <FieldLabel>Text</FieldLabel>
            <Textarea rows={10} {...form.register("body")} />
            <FieldError>{errors.body?.message}</FieldError>
          </Field>
        </>
      ) : null}
      {type === "url" ? (
        <>
          <Field id="source-url" invalid={!!errors.url}>
            <FieldLabel>Web address</FieldLabel>
            <Input type="url" inputMode="url" placeholder="https://" {...form.register("url")} />
            <FieldError>{errors.url?.message}</FieldError>
          </Field>
          <Field id="source-title" invalid={!!errors.title}>
            <FieldLabel>Title (optional)</FieldLabel>
            <Input maxLength={120} {...form.register("title")} />
            <FieldDescription>The page title is used when this is empty.</FieldDescription>
            <FieldError>{errors.title?.message}</FieldError>
          </Field>
        </>
      ) : null}
      {type === "site" ? (
        <>
          {editing ? (
            <CardInset padding="compact" className="flex items-center gap-2 text-sm">
              <Network className="size-4 shrink-0 text-fg-secondary" aria-hidden />
              <span className="truncate">{mode.kind === "edit" ? (mode.source.url ?? mode.source.title) : ""}</span>
            </CardInset>
          ) : (
            <Field id="source-url" invalid={!!errors.url}>
              <FieldLabel>Website address</FieldLabel>
              <Input type="url" inputMode="url" placeholder="https://" {...form.register("url")} />
              <FieldDescription>The first page to read, usually your home page.</FieldDescription>
              <FieldError>{errors.url?.message}</FieldError>
            </Field>
          )}
          <Field id="source-title" invalid={!!errors.title}>
            <FieldLabel>Title (optional)</FieldLabel>
            <Input maxLength={120} {...form.register("title")} />
            <FieldDescription>The site&apos;s address is used when this is empty.</FieldDescription>
            <FieldError>{errors.title?.message}</FieldError>
          </Field>
          <Field id="source-recrawl" orientation="horizontal">
            <Checkbox checked={weekly} onCheckedChange={(value) => setWeekly(value === true)} />
            <FieldLabel className="font-normal">Check for changes every week</FieldLabel>
          </Field>
        </>
      ) : null}
      {type === "file" ? (
        <>
          {editing ? (
            <CardInset padding="compact" className="flex items-center gap-2 text-sm">
              <FileText className="size-4 shrink-0 text-fg-secondary" aria-hidden />
              <span className="truncate">{mode.kind === "edit" ? (mode.source.file_name ?? mode.source.title) : ""}</span>
            </CardInset>
          ) : (
            <Field id="source-file" invalid={!!fileError}>
              <FieldLabel>File</FieldLabel>
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
                <Progress aria-label="Uploading" value={Math.round(progress * 100)} />
              ) : null}
              {fileError ? (
                <FieldError>{fileError}</FieldError>
              ) : (
                <FieldDescription>PDF, DOCX, TXT or MD, up to 10 MB.</FieldDescription>
              )}
            </Field>
          )}
          <Field id="source-title" invalid={!!errors.title}>
            <FieldLabel>Title (optional)</FieldLabel>
            <Input maxLength={120} {...form.register("title")} />
            <FieldDescription>The file name is used when this is empty.</FieldDescription>
            <FieldError>{errors.title?.message}</FieldError>
          </Field>
        </>
      ) : null}
      {editing && (type === "url" || type === "file" || type === "site") ? (
        <Field id="source-reingest" orientation="horizontal">
          <Checkbox checked={reingest} onCheckedChange={(value) => setReingest(value === true)} />
          <FieldLabel className="font-normal">
            {type === "url" ? "Fetch the page again" : type === "site" ? "Crawl the site again" : "Read the file again"}
          </FieldLabel>
        </Field>
      ) : null}

      {overLimit ? (
        <Alert
          tone="warning"
          urgent
          icon={<AlertTriangle />}
          action={
            workspace.role === "owner" || workspace.role === "admin" ? (
              <AlertAction type="button" onClick={() => upgrade.open(overLimit)}>
                Upgrade
              </AlertAction>
            ) : undefined
          }
        >
          {knowledgeLimitReached(overLimit.limit ?? limit)} Remove a source or upgrade for more.
        </Alert>
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
        <Button type="submit" loading={saving}>
          {editing ? "Save" : "Add"}
        </Button>
      </div>
    </form>
  );
}
