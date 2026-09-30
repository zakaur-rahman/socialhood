"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Bot, Building2, Info, Link2, ListChecks } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { SaveBar } from "@/components/settings/SaveBar";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { DeleteWorkspace } from "@/components/workspace/DeleteWorkspace";
import { ApiError } from "@/lib/api/errors";
import { useSocialAccounts, useUpdateWorkspace, useWorkspace } from "@/lib/api/queries";
import type { Workspace, WorkspacePatch } from "@/lib/api/types";
import { billingDate } from "@/lib/billing/plan";
import { PLAN_NAME, errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$/;
/** WorkspacePatch.name (apps/api schemas/workspaces.py) and the workspaces.name check: 1–80. */
const NAME_MAX = 80;
/** WorkspacePatch.automation_disclosure: up to 60 characters. */
const DISCLOSURE_MAX = 60;

const schema = z.object({
  name: z.string().trim().min(1, "Enter a workspace name.").max(NAME_MAX, `Use ${NAME_MAX} characters or fewer.`),
  slug: z
    .string()
    .trim()
    .regex(SLUG, "Use 3 to 48 lowercase letters, numbers and hyphens, starting and ending with a letter or number."),
  timezone: z.string().min(1, "Choose a timezone from the list."),
  reply_language: z.string().min(1),
  disclosure_on: z.boolean(),
  automation_disclosure: z.string().trim().max(DISCLOSURE_MAX, `Use ${DISCLOSURE_MAX} characters or fewer.`),
}).refine((values) => !values.disclosure_on || values.automation_disclosure.length > 0, {
  path: ["automation_disclosure"],
  message: "Enter the line to add, or turn the disclosure off.",
});
type Values = z.infer<typeof schema>;

/** FR-AUT-11: the line automated messages end with; null in the API means off. */
const DEFAULT_DISCLOSURE = "Sent automatically";

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

/** FR-ACC-03 / UX-SCR-07 (Workspace): name, URL, timezone, reply language and the automation
 * disclosure line (FR-AUT-11); for owners, the danger zone that deletes the workspace
 * (FR-ACC-05). C-066: cards, a sticky save bar, and a summary of the workspace beside them. */
export default function WorkspaceSettingsPage() {
  const current = useCurrentWorkspace();
  const workspace = useWorkspace(current.id);
  if (workspace.isPending) return <PageSkeleton rows={3} />;
  if (workspace.isError) return <ErrorState error={workspace.error} onRetry={() => void workspace.refetch()} />;
  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          label="Configuration"
          title="Workspace"
          description="Its name and address, the timezone schedules use, the language AI replies in, and how automated messages identify themselves."
        />
      }
    >
      <WorkspaceForm workspace={workspace.data} canEdit={current.role !== "agent"} />
    </SettingsFrame>
  );
}

function WorkspaceForm({ workspace, canEdit }: { workspace: Workspace; canEdit: boolean }) {
  const router = useRouter();
  const update = useUpdateWorkspace(workspace.id);
  const zones = useMemo(() => timezones(workspace.timezone), [workspace.timezone]);
  const suggested = browserTimezone();
  const [saveError, setSaveError] = useState<string | null>(null);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: formValues(workspace),
  });
  const { errors, isDirty } = form.formState;
  const timezone = useWatch({ control: form.control, name: "timezone" });
  const disclosureOn = useWatch({ control: form.control, name: "disclosure_on" });
  const disclosure = useWatch({ control: form.control, name: "automation_disclosure" });
  const name = useWatch({ control: form.control, name: "name" });

  const onSubmit = form.handleSubmit((values) => {
    setSaveError(null);
    const changes: WorkspacePatch = {};
    const dirty = form.formState.dirtyFields;
    for (const key of ["name", "slug", "timezone", "reply_language"] as const) {
      if (dirty[key]) changes[key] = values[key];
    }
    if (dirty.disclosure_on || dirty.automation_disclosure) {
      changes.automation_disclosure = values.disclosure_on ? values.automation_disclosure : null;
    }
    update.mutate(changes, {
      onSuccess: (saved) => {
        form.reset(formValues(saved));
        toast.success("Workspace settings saved");
        if (saved.slug !== workspace.slug) router.replace(`/w/${saved.slug}/settings/workspace`);
      },
      onError: (error) => {
        if (error instanceof ApiError && error.errors.length > 0) {
          const other: string[] = [];
          for (const field of error.errors) {
            if (field.field in values) form.setError(field.field as keyof Values, { message: field.message });
            else other.push(field.message);
          }
          setSaveError(other.length > 0 ? other.join(" ") : "Check the highlighted fields.");
          return;
        }
        setSaveError(errorMessage(error));
      },
    });
  });

  return (
    <>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:items-start">
        <div className="min-w-0 space-y-6">
          <form onSubmit={onSubmit} noValidate aria-label="Workspace settings">
            <SettingsCard
              id="general"
              icon={<Building2 />}
              title="General information"
              description="How this workspace is named, addressed and scheduled."
            >
              <div className="space-y-6">
                <Field
                  id="name"
                  label="Workspace name"
                  counter={`${name.length} / ${NAME_MAX}`}
                  error={errors.name?.message}
                >
                  <Input
                    id="name"
                    maxLength={NAME_MAX}
                    disabled={!canEdit}
                    aria-invalid={!!errors.name}
                    className="min-h-10"
                    {...form.register("name")}
                  />
                </Field>

                <Field
                  id="slug"
                  label="URL"
                  hint="Changing it changes the address of every page in this workspace."
                  error={errors.slug?.message}
                >
                  <div className="flex min-h-10 items-stretch overflow-hidden rounded-lg border border-line bg-field focus-within:ring-2 focus-within:ring-brand">
                    <span className="flex items-center border-r border-line bg-raised/60 px-3 text-sm text-fg-secondary" aria-hidden>
                      …/w/
                    </span>
                    <Input
                      id="slug"
                      disabled={!canEdit}
                      aria-invalid={!!errors.slug}
                      aria-describedby="slug-prefix"
                      className="min-h-10 rounded-none border-0 bg-transparent focus-visible:ring-0"
                      {...form.register("slug")}
                    />
                  </div>
                  <span id="slug-prefix" className="sr-only">
                    The address after /w/
                  </span>
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
                        <SelectTrigger id="timezone" className="min-h-10 w-full">
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
                      className="mt-2 min-h-10 rounded-md text-left text-sm text-brand-fg underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-brand md:min-h-0"
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
                        <SelectTrigger id="reply_language" className="min-h-10 w-full">
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

                <div className="space-y-4 rounded-xl border border-line-subtle bg-field/60 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <Label htmlFor="disclosure_on" className="flex items-center gap-2">
                        <Bot className="size-4 text-brand-fg" aria-hidden />
                        Say when a message is automated
                      </Label>
                      <p id="disclosure-hint" className="text-xs text-fg-secondary">
                        Adds a short line to messages sent by automations and AI auto replies. Some places require bots to
                        identify themselves. It counts toward Instagram&apos;s 1,000-byte limit.
                      </p>
                    </div>
                    <Controller
                      control={form.control}
                      name="disclosure_on"
                      render={({ field }) => (
                        <Switch
                          id="disclosure_on"
                          aria-describedby="disclosure-hint"
                          checked={field.value}
                          disabled={!canEdit}
                          onCheckedChange={(on) => {
                            field.onChange(on);
                            if (on && !form.getValues("automation_disclosure")) {
                              form.setValue("automation_disclosure", DEFAULT_DISCLOSURE, { shouldDirty: true });
                            }
                          }}
                        />
                      )}
                    />
                  </div>
                  {disclosureOn ? (
                    <>
                      <Field
                        id="automation_disclosure"
                        label="Line to add"
                        counter={`${disclosure.length} / ${DISCLOSURE_MAX}`}
                        error={errors.automation_disclosure?.message}
                      >
                        <Input
                          id="automation_disclosure"
                          maxLength={DISCLOSURE_MAX}
                          disabled={!canEdit}
                          aria-invalid={!!errors.automation_disclosure}
                          className="min-h-10"
                          {...form.register("automation_disclosure")}
                        />
                      </Field>
                      <DisclosurePreview line={disclosure.trim()} />
                    </>
                  ) : null}
                </div>

                {canEdit ? null : (
                  <p className="text-sm text-fg-secondary">Only owners and admins can change these settings.</p>
                )}
              </div>
            </SettingsCard>
          </form>
          <DeleteWorkspace />
        </div>
        <WorkspaceSummary workspace={workspace} />
      </div>
      {canEdit ? (
        <SaveBar
          dirty={isDirty}
          saving={update.isPending}
          error={saveError}
          onReset={() => {
            setSaveError(null);
            form.reset(formValues(workspace));
          }}
          onSave={() => void onSubmit()}
        />
      ) : null}
    </>
  );
}

/** What an automated message looks like with the line added (services/automations/render.py:
 * the text, a blank line, then the disclosure). */
function DisclosurePreview({ line }: { line: string }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-fg-secondary">Preview</p>
      <div className="max-w-sm rounded-2xl rounded-bl-md bg-raised px-3.5 py-2.5 text-sm whitespace-pre-line" data-testid="disclosure-preview">
        <span className="text-fg-secondary">Your automated message…</span>
        {line ? (
          <>
            {"\n\n"}
            <span>{line}</span>
          </>
        ) : null}
      </div>
    </div>
  );
}

/** A small true summary (C-066): plan, connected channels, members and when it was created. */
function WorkspaceSummary({ workspace }: { workspace: Workspace }) {
  const accounts = useSocialAccounts(workspace.id);
  const live = (accounts.data ?? []).filter((account) => account.status !== "disconnected");
  const instagram = live.filter((account) => account.platform === "instagram").length;
  const whatsapp = live.filter((account) => account.platform === "whatsapp").length;
  const channels = [
    instagram ? `Instagram (${instagram})` : null,
    whatsapp ? `WhatsApp (${whatsapp})` : null,
  ].filter(Boolean);
  return (
    <SettingsCard id="summary" icon={<ListChecks />} title="At a glance" className="xl:sticky xl:top-6">
      <dl className="divide-y divide-line-subtle text-sm">
        <SummaryRow label="Plan">{PLAN_NAME[workspace.plan]}</SummaryRow>
        <SummaryRow label="Connected channels">
          {accounts.isPending ? "…" : channels.length > 0 ? channels.join(", ") : "None yet"}
        </SummaryRow>
        <SummaryRow label="Members">{workspace.member_count}</SummaryRow>
        <SummaryRow label="Created">{billingDate(workspace.created_at, workspace.timezone)}</SummaryRow>
      </dl>
      <p className="mt-4 flex items-start gap-2 text-xs text-fg-secondary">
        <Link2 className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Address: <span className="break-all text-fg">/w/{workspace.slug}</span>
        </span>
      </p>
    </SettingsCard>
  );
}

function SummaryRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5 first:pt-0 last:pb-0">
      <dt className="text-fg-secondary">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

function formValues(workspace: Workspace): Values {
  return {
    name: workspace.name,
    slug: workspace.slug,
    timezone: workspace.timezone,
    reply_language: workspace.reply_language,
    disclosure_on: !!workspace.automation_disclosure,
    automation_disclosure: workspace.automation_disclosure ?? "",
  };
}

function Field({
  id,
  label,
  hint,
  counter,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  counter?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        {counter ? (
          <span className="text-xs text-fg-secondary tabular-nums" aria-hidden>
            {counter}
          </span>
        ) : null}
      </div>
      {children}
      {error ? (
        <p role="alert" className="text-sm text-danger-fg">
          {error}
        </p>
      ) : hint ? (
        <p className="flex items-start gap-1.5 text-xs text-fg-secondary">
          <Info className="mt-px size-3.5 shrink-0" aria-hidden />
          {hint}
        </p>
      ) : null}
    </div>
  );
}
