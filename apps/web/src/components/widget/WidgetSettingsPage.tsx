"use client";

import { Copy, Globe } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { SaveBar } from "@/components/settings/SaveBar";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { Button } from "@/components/ui/button";
import { ChipInput } from "@/components/ui/chip-input";
import { DisabledReason } from "@/components/ui/disabled-reason";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import { useSaveWidgetSettings, useWidgetSettings } from "@/lib/api/queries";
import type { WidgetEmailCapture, WidgetPosition, WidgetSettings } from "@/lib/api/types";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import {
  CONSENT_TEXT_MAX,
  DOMAIN_MAX_CHARS,
  DOMAINS_MAX,
  EMAIL_CAPTURE_LABEL,
  EMAIL_PROMPT_MAX,
  GREETING_MAX,
  isDirty,
  isLive,
  problem,
  TITLE_MAX,
  toBody,
  toForm,
  type WidgetForm as Form,
} from "@/lib/widget/form";
import { useCurrentWorkspace } from "@/lib/workspace";
import { MONO } from "@/styles/tokens";
import { widgetAccents } from "./accents";

const BRANDING_UPGRADE = { code: "entitlement_required", entitlement: "widget_remove_branding" } as const;

/**
 * GR-28: Settings → Website chat. Owners and admins add the sites that may show the chat, copy the
 * one-line embed code, and choose how it looks and what it asks a visitor. Chats arrive in the
 * inbox as "Website"; the AI mode is the account's, set in AI rules and takeover. Free keeps the
 * "Powered by Social Hood" link; Pro and Max can turn it off (PD-7).
 */
export function WidgetSettingsPage() {
  const workspace = useCurrentWorkspace();
  const settings = useWidgetSettings(workspace.id);

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Website chat"
          description="A chat bubble for your website. Visitors' chats arrive in your inbox, and the AI answers from your knowledge like it does on Instagram."
        />
      }
    >
      {settings.isPending ? (
        <PageSkeleton rows={3} />
      ) : settings.isError ? (
        <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
      ) : (
        <WidgetForm key={JSON.stringify(settings.data)} saved={settings.data} />
      )}
    </SettingsFrame>
  );
}

function WidgetForm({ saved }: { saved: WidgetSettings }) {
  const workspace = useCurrentWorkspace();
  const save = useSaveWidgetSettings(workspace.id);
  const upgrade = useUpgradeDialog();
  const [form, setForm] = useState<Form>(() => toForm(saved));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const change = (patch: Partial<Form>) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors({});
    setSaveError(null);
  };
  const dirty = isDirty(form, saved);
  const blocked = problem(form);
  const domainError = Object.entries(errors).find(([field]) => field.startsWith("allowed_domains"))?.[1];

  function submit(event?: React.FormEvent) {
    event?.preventDefault();
    if (!dirty || blocked) return;
    setErrors({});
    save.mutate(toBody(form, saved), {
      onSuccess: () => toast.success("Website chat saved"),
      onError: (error) => {
        if (error instanceof ApiError && error.errors.length > 0) {
          setErrors(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
          setSaveError(error.errors[0]?.message ?? null);
        } else {
          setSaveError(error.message);
          toastError(error);
        }
      },
    });
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <InstallCard saved={saved} form={form} onChange={change} domainError={domainError} />
      <LookCard form={form} onChange={change} />
      <VisitorCard form={form} onChange={change} errors={errors} />
      <BrandingCard
        saved={saved}
        form={form}
        slug={workspace.slug}
        onChange={change}
        onUpgrade={() => upgrade.open(BRANDING_UPGRADE)}
      />
      {blocked && dirty ? <p className="text-sm text-fg-secondary">{blocked}</p> : null}
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        error={saveError}
        onReset={() => {
          setErrors({});
          setSaveError(null);
          setForm(toForm(saved));
        }}
        onSave={() => submit()}
      />
    </form>
  );
}

type CardProps = { form: Form; onChange: (patch: Partial<Form>) => void };

function InstallCard({ saved, form, onChange, domainError }: CardProps & { saved: WidgetSettings; domainError?: string }) {
  const live = isLive(form);

  async function copy() {
    try {
      await navigator.clipboard.writeText(saved.embed_snippet);
      toast.success("Embed code copied");
    } catch {
      toast.error("Couldn't copy the code. Select it and copy it by hand.");
    }
  }

  return (
    <SettingsCard
      id="widget-install"
      icon={<Globe />}
      title="Install"
      description="Paste the code before the closing </body> tag of every page that should show the chat."
      aside={
        <div className="flex items-center gap-2">
          <label htmlFor="widget-enabled" className="text-sm font-medium">
            Chat is on
          </label>
          <Switch id="widget-enabled" checked={form.enabled} onCheckedChange={(enabled) => onChange({ enabled })} />
        </div>
      }
    >
      <Field invalid={Boolean(domainError)}>
        <FieldLabel>Sites that can show the chat</FieldLabel>
        <ChipInput
          value={form.domains}
          onValueChange={(domains) => onChange({ domains })}
          listLabel="Allowed sites"
          placeholder="example.com"
          max={DOMAINS_MAX}
          maxLength={DOMAIN_MAX_CHARS}
          separator="comma"
          error={domainError}
        />
        <FieldDescription>
          Add each site by its address, like example.com (www.example.com is included) or *.example.com for every
          subdomain. The chat refuses to load anywhere else.
        </FieldDescription>
      </Field>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium" id="widget-code-label">
            Embed code
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={() => void copy()}>
            <Copy aria-hidden /> Copy code
          </Button>
        </div>
        <pre
          tabIndex={0}
          aria-labelledby="widget-code-label"
          className={cn(MONO, "overflow-x-auto rounded-lg bg-field p-3 whitespace-pre-wrap break-all")}
        >
          {saved.embed_snippet}
        </pre>
        <p className="text-xs text-fg-secondary" role="status">
          {!form.enabled
            ? "The chat is off. Visitors see nothing until you turn it on."
            : live
              ? `Chats started today: ${saved.conversations_today} of ${saved.conversations_daily_limit} your plan allows.`
              : "No sites are allowed yet, so the chat won't show anywhere. Add one above."}
        </p>
      </div>
    </SettingsCard>
  );
}

function LookCard({ form, onChange }: CardProps) {
  const known = widgetAccents.some((accent) => accent.value === form.accent);
  const choices: readonly { name: string; value: string }[] = known
    ? widgetAccents
    : [...widgetAccents, { name: "Current colour", value: form.accent }];
  return (
    <SettingsCard id="widget-look" title="Look" description="Its colour follows your brand; the rest follows the visitor's light or dark setting.">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-5">
          <Field>
            <FieldLabel>Title</FieldLabel>
            <Input value={form.title} maxLength={TITLE_MAX} onChange={(e) => onChange({ title: e.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Greeting</FieldLabel>
            <Textarea
              value={form.greeting}
              maxLength={GREETING_MAX}
              rows={3}
              onChange={(e) => onChange({ greeting: e.target.value })}
            />
            <FieldDescription>The first message a visitor sees when they open the chat.</FieldDescription>
          </Field>
          <div className="space-y-2">
            <p className="text-sm font-medium" id="widget-accent-label">
              Colour
            </p>
            <div role="group" aria-labelledby="widget-accent-label" className="flex flex-wrap gap-3">
              {choices.map((accent) => (
                <button
                  key={accent.value}
                  type="button"
                  aria-label={accent.name}
                  aria-pressed={form.accent === accent.value}
                  title={accent.name}
                  onClick={() => onChange({ accent: accent.value })}
                  style={{ backgroundColor: accent.value }}
                  className={cn(
                    "size-9 rounded-full pointer-coarse:size-10",
                    form.accent === accent.value ? "ring-2 ring-fg ring-offset-2 ring-offset-panel" : "",
                  )}
                />
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium" id="widget-position-label">
              Position
            </p>
            <ToggleGroup
              aria-labelledby="widget-position-label"
              value={form.position}
              onValueChange={(value) => value && onChange({ position: value as WidgetPosition })}
              className="sm:max-w-xs"
            >
              <ToggleGroupItem value="right">Bottom right</ToggleGroupItem>
              <ToggleGroupItem value="left">Bottom left</ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
        <Preview form={form} />
      </div>
    </SettingsCard>
  );
}

/** A picture of the chat as the visitor sees it. Decorative: the controls beside it say the same. */
function Preview({ form }: { form: Form }) {
  return (
    <div aria-hidden className="flex flex-col justify-end rounded-xl bg-canvas p-4">
      <div className={cn("w-full overflow-hidden rounded-xl bg-panel ring-1 ring-line", form.position === "left" ? "mr-auto" : "ml-auto")}>
        <div className="px-4 py-3 text-sm font-semibold text-on-brand" style={{ backgroundColor: form.accent }}>
          {form.title || "Chat with us"}
        </div>
        <div className="space-y-2 p-3">
          <p className="max-w-[85%] rounded-xl bg-field px-3 py-2 text-sm">{form.greeting || "Hi! How can we help?"}</p>
          <p
            className="ml-auto max-w-[70%] rounded-xl px-3 py-2 text-sm text-on-brand"
            style={{ backgroundColor: form.accent }}
          >
            Do you ship to Pune?
          </p>
        </div>
      </div>
      <div
        className={cn("mt-3 size-10 rounded-full", form.position === "left" ? "mr-auto" : "ml-auto")}
        style={{ backgroundColor: form.accent }}
      />
    </div>
  );
}

const CAPTURE_HINT: Record<WidgetEmailCapture, string> = {
  off: "Visitors chat without giving anything. You can still ask for an email in the conversation.",
  optional: "After a visitor's first message the chat offers an email box, which they can skip.",
  required: "The chat asks for an email before the first message. Visitors who don't give one can't start a chat.",
};

function VisitorCard({ form, onChange, errors }: CardProps & { errors: Record<string, string> }) {
  const asks = form.emailCapture !== "off";
  return (
    <SettingsCard
      id="widget-visitors"
      title="Visitor details"
      description="An email turns an anonymous visitor into a contact you can follow up."
    >
      <div className="space-y-2">
        <p className="text-sm font-medium" id="widget-capture-label">
          Ask for an email
        </p>
        <ToggleGroup
          aria-labelledby="widget-capture-label"
          value={form.emailCapture}
          onValueChange={(value) => value && onChange({ emailCapture: value as WidgetEmailCapture })}
          className="flex-col sm:flex-row sm:max-w-xl"
        >
          {(Object.keys(EMAIL_CAPTURE_LABEL) as WidgetEmailCapture[]).map((mode) => (
            <ToggleGroupItem key={mode} value={mode}>
              {EMAIL_CAPTURE_LABEL[mode]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <p className="text-xs text-fg-secondary">{CAPTURE_HINT[form.emailCapture]}</p>
      </div>
      {asks ? (
        <>
          <Field invalid={Boolean(errors.email_prompt)}>
            <FieldLabel>What the email box says</FieldLabel>
            <Input
              value={form.emailPrompt}
              maxLength={EMAIL_PROMPT_MAX}
              onChange={(e) => onChange({ emailPrompt: e.target.value })}
            />
          </Field>
          <div className="space-y-3 border-t border-line pt-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <label htmlFor="widget-consent" className="text-sm font-medium">
                  Ask for marketing consent
                </label>
                <p className="text-xs text-fg-secondary">
                  Adds an unticked box under the email. A ticked box is saved on the contact with these exact words,
                  the site and the time as proof.
                </p>
              </div>
              <Switch
                id="widget-consent"
                checked={form.consentEnabled}
                onCheckedChange={(consentEnabled) => onChange({ consentEnabled })}
              />
            </div>
            {form.consentEnabled ? (
              <Field invalid={Boolean(errors.marketing_consent_text)}>
                <FieldLabel>Words next to the box</FieldLabel>
                <Textarea
                  value={form.consentText}
                  maxLength={CONSENT_TEXT_MAX}
                  rows={2}
                  onChange={(e) => onChange({ consentText: e.target.value })}
                />
              </Field>
            ) : null}
          </div>
        </>
      ) : null}
    </SettingsCard>
  );
}

function BrandingCard({
  saved,
  form,
  slug,
  onChange,
  onUpgrade,
}: CardProps & { saved: WidgetSettings; slug: string; onUpgrade: () => void }) {
  const locked = !saved.can_remove_branding;
  return (
    <SettingsCard
      id="widget-branding"
      title="Branding and AI"
      description="Free workspaces show a small “Powered by Social Hood” link. Pro and Max can turn it off."
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <label htmlFor="widget-branding-switch" className="text-sm font-medium">
            Show “Powered by Social Hood”
          </label>
          {locked ? (
            <p className="text-xs text-fg-secondary">
              Turning it off is part of Pro.{" "}
              <Button type="button" variant="link" className="h-auto px-0 text-xs" onClick={onUpgrade}>
                See plans
              </Button>
            </p>
          ) : null}
        </div>
        <DisabledReason reason={locked ? "Turning it off is part of Pro" : null}>
          <Switch
            id="widget-branding-switch"
            checked={locked ? true : form.branding}
            disabled={locked}
            onCheckedChange={(branding) => onChange({ branding })}
          />
        </DisabledReason>
      </div>
      <p className="border-t border-line pt-5 text-sm text-fg-secondary">
        AI on website chats is set to <strong className="font-medium text-fg">{AI_WORD[saved.ai_mode]}</strong>. Change it
        in{" "}
        <Link href={`/w/${slug}/settings/ai` as Route} className="underline underline-offset-4">
          AI rules and takeover
        </Link>
        . {"Chats the AI can't answer are marked Needs you, and website chats have no 24-hour reply window."}
      </p>
    </SettingsCard>
  );
}

const AI_WORD = { off: "Off", suggest: "Suggest", auto: "Auto" } as const;
