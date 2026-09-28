"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import { useUpdateWorkspace, useWorkspace } from "@/lib/api/queries";
import type { Workspace, WorkspacePatch } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$/;

const schema = z.object({
  name: z.string().trim().min(1, "Enter a workspace name.").max(80, "Use 80 characters or fewer."),
  slug: z
    .string()
    .trim()
    .regex(SLUG, "Use 3 to 48 lowercase letters, numbers and hyphens, starting and ending with a letter or number."),
  timezone: z.string().min(1, "Choose a timezone from the list."),
  reply_language: z.string().min(1),
});
type Values = z.infer<typeof schema>;

const LANGUAGES = [
  ["auto", "Customer's language"],
  ["en", "English"],
  ["hi", "Hindi"],
  ["bn", "Bengali"],
  ["ta", "Tamil"],
  ["te", "Telugu"],
  ["mr", "Marathi"],
  ["gu", "Gujarati"],
  ["kn", "Kannada"],
  ["ml", "Malayalam"],
  ["pa", "Punjabi"],
  ["ur", "Urdu"],
  ["ar", "Arabic"],
  ["id", "Indonesian"],
  ["es", "Spanish"],
  ["pt", "Portuguese"],
  ["fr", "French"],
  ["de", "German"],
] as const;

function timezones(current: string): string[] {
  const zones = new Set(Intl.supportedValuesOf("timeZone"));
  zones.add("UTC");
  zones.add(current);
  return [...zones].sort();
}

function browserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return null;
  }
}

/** FR-ACC-03 / UX-SCR-07 (Workspace): name, URL, timezone and reply language. */
export default function WorkspaceSettingsPage() {
  const current = useCurrentWorkspace();
  const workspace = useWorkspace(current.id);
  if (workspace.isPending) return <PageSkeleton rows={3} />;
  if (workspace.isError) return <ErrorState error={workspace.error} onRetry={() => void workspace.refetch()} />;
  return (
    <PageFrame title="Workspace">
      <WorkspaceForm workspace={workspace.data} canEdit={current.role !== "agent"} />
    </PageFrame>
  );
}

function WorkspaceForm({ workspace, canEdit }: { workspace: Workspace; canEdit: boolean }) {
  const router = useRouter();
  const update = useUpdateWorkspace(workspace.id);
  const zones = useMemo(() => timezones(workspace.timezone), [workspace.timezone]);
  const suggested = browserTimezone();

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: workspace.name,
      slug: workspace.slug,
      timezone: workspace.timezone,
      reply_language: workspace.reply_language,
    },
  });
  const { errors, isDirty } = form.formState;
  const timezone = useWatch({ control: form.control, name: "timezone" });

  const onSubmit = form.handleSubmit((values) => {
    const changes: WorkspacePatch = {};
    for (const key of Object.keys(values) as (keyof Values)[]) {
      if (form.formState.dirtyFields[key]) changes[key] = values[key];
    }
    update.mutate(changes, {
      onSuccess: (saved) => {
        form.reset({
          name: saved.name,
          slug: saved.slug,
          timezone: saved.timezone,
          reply_language: saved.reply_language,
        });
        toast.success("Workspace settings saved");
        if (saved.slug !== workspace.slug) router.replace(`/w/${saved.slug}/settings/workspace`);
      },
      onError: (error) => {
        if (error instanceof ApiError && error.errors.length > 0) {
          for (const field of error.errors) {
            if (field.field in values) form.setError(field.field as keyof Values, { message: field.message });
          }
          return;
        }
        toast.error(errorMessage(error));
      },
    });
  });

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-xl space-y-6 rounded-xl border border-line bg-panel p-5">
      <Field id="name" label="Workspace name" error={errors.name?.message}>
        <Input id="name" disabled={!canEdit} aria-invalid={!!errors.name} {...form.register("name")} />
      </Field>

      <Field
        id="slug"
        label="URL"
        hint="Changing it changes the address of every page in this workspace."
        error={errors.slug?.message}
      >
        <div className="flex items-center rounded-lg border border-line bg-field focus-within:ring-2 focus-within:ring-brand">
          <span className="pl-3 text-sm text-fg-secondary">/w/</span>
          <Input
            id="slug"
            disabled={!canEdit}
            aria-invalid={!!errors.slug}
            className="border-0 bg-transparent pl-1 focus-visible:ring-0"
            {...form.register("slug")}
          />
        </div>
      </Field>

      <Field
        id="timezone"
        label="Timezone"
        hint="Scheduling screens show and accept times in this timezone."
        error={errors.timezone?.message}
      >
        <Controller
          control={form.control}
          name="timezone"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange} disabled={!canEdit}>
              <SelectTrigger id="timezone" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {zones.map((zone) => (
                  <SelectItem key={zone} value={zone}>
                    {zone.replaceAll("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        {canEdit && suggested && suggested !== timezone ? (
          <button
            type="button"
            className="mt-2 text-sm text-brand-fg underline-offset-4 hover:underline"
            onClick={() => form.setValue("timezone", suggested, { shouldDirty: true })}
          >
            Use your browser&apos;s timezone ({suggested.replaceAll("_", " ")})
          </button>
        ) : null}
      </Field>

      <Field
        id="reply_language"
        label="Default reply language"
        hint="The language AI replies use. Customer's language answers in whatever they wrote in."
        error={errors.reply_language?.message}
      >
        <Controller
          control={form.control}
          name="reply_language"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange} disabled={!canEdit}>
              <SelectTrigger id="reply_language" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGES.map(([code, label]) => (
                  <SelectItem key={code} value={code}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </Field>

      {canEdit ? (
        <div className="flex justify-end">
          <Button type="submit" disabled={!isDirty || update.isPending} className="bg-brand-gradient text-white">
            {update.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      ) : (
        <p className="text-sm text-fg-secondary">Only owners and admins can change these settings.</p>
      )}
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
