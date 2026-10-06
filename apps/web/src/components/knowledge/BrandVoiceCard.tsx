"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ChipListInput } from "@/components/ai/ChipListInput";
import { useLeaveWarning } from "@/components/settings/SaveBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError } from "@/lib/api/errors";
import { toSettingsUpdate, useUpdateAiSettings } from "@/lib/api/queries";
import type { AiSettings, BrandTone, EmojiPolicy } from "@/lib/api/types";
import { EMOJI_OPTIONS, TONE_OPTIONS } from "@/lib/ai/format";
import { aiCopy } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";

const schema = z.object({
  business_name: z.string().trim().max(80, "Use 80 characters or fewer."),
  business_description: z.string().trim().max(1000, "Use 1,000 characters or fewer."),
  tone: z.enum(["friendly", "professional", "playful", "concise"]),
  emoji_policy: z.enum(["none", "light", "lots"]),
  do_list: z.array(z.string()).max(20),
  dont_list: z.array(z.string()).max(20),
  sign_off: z.string().trim().max(60, "Use 60 characters or fewer."),
});
type Values = z.infer<typeof schema>;

function formValues(settings: AiSettings): Values {
  return {
    business_name: settings.business_name ?? "",
    business_description: settings.business_description ?? "",
    tone: settings.tone,
    emoji_policy: settings.emoji_policy,
    do_list: settings.do_list,
    dont_list: settings.dont_list,
    sign_off: settings.sign_off ?? "",
  };
}

const TONE_LABEL = Object.fromEntries(TONE_OPTIONS.map((o) => [o.value, o.label])) as Record<BrandTone, string>;
const EMOJI_LABEL = Object.fromEntries(EMOJI_OPTIONS.map((o) => [o.value, o.label])) as Record<EmojiPolicy, string>;

/**
 * FR-KB-04 / F-14: how replies sound. Opens as a form while the business description is empty
 * (the first visit); afterwards it shows a summary with Edit. Saves the whole settings object.
 */
export function BrandVoiceCard({ wid, settings, workspaceName }: { wid: string; settings: AiSettings; workspaceName: string }) {
  const [editing, setEditing] = useState(false);
  const open = editing || !settings.business_description?.trim();

  return (
    <section aria-labelledby="brand-voice-title" className="rounded-xl border border-line bg-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="brand-voice-title" className="text-base font-semibold">
            Brand voice
          </h2>
          <p className="text-xs text-fg-secondary">How suggested and automatic replies sound.</p>
        </div>
        {!open ? (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil aria-hidden /> Edit
          </Button>
        ) : null}
      </div>
      {open ? (
        <BrandVoiceForm
          wid={wid}
          settings={settings}
          workspaceName={workspaceName}
          onDone={() => setEditing(false)}
          onCancel={editing ? () => setEditing(false) : undefined}
        />
      ) : (
        <div className="mt-4 space-y-2 text-sm">
          <p className="font-medium">{settings.business_name?.trim() || workspaceName}</p>
          <p className="line-clamp-3 text-fg-secondary">{settings.business_description}</p>
          <p className="text-xs text-fg-secondary">
            {TONE_LABEL[settings.tone]} · {EMOJI_LABEL[settings.emoji_policy]} emoji
            {settings.sign_off ? ` · Signs off “${settings.sign_off}”` : ""}
            {settings.do_list.length ? ` · ${settings.do_list.length} always` : ""}
            {settings.dont_list.length ? ` · ${settings.dont_list.length} never` : ""}
          </p>
        </div>
      )}
    </section>
  );
}

function BrandVoiceForm({
  wid,
  settings,
  workspaceName,
  onDone,
  onCancel,
}: {
  wid: string;
  settings: AiSettings;
  workspaceName: string;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const update = useUpdateAiSettings(wid);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: formValues(settings) });
  const { errors, isDirty } = form.formState;
  // Brand voice saves with Save only: leaving with changes asks first (UI-ISS-022).
  useLeaveWarning(isDirty);

  const onSubmit = form.handleSubmit((values) => {
    update.mutate(
      {
        ...toSettingsUpdate(settings),
        business_name: values.business_name || null,
        business_description: values.business_description || null,
        tone: values.tone,
        emoji_policy: values.emoji_policy,
        do_list: values.do_list,
        dont_list: values.dont_list,
        sign_off: values.sign_off || null,
      },
      {
        onSuccess: (saved) => {
          form.reset(formValues(saved));
          toast.success("Brand voice saved");
          onDone();
        },
        onError: (error) => {
          if (error instanceof ApiError && error.errors.length > 0) {
            for (const field of error.errors) {
              const name = field.field.split(".")[0];
              if (name in values) form.setError(name as keyof Values, { message: field.message });
              else toast.error(field.message);
            }
            return;
          }
          toastError(error);
        },
      },
    );
  });

  return (
    <form onSubmit={onSubmit} noValidate className="mt-5 space-y-5" aria-label="Brand voice">
      <Field id="bv-name" label="Business name" hint={`Replies use “${workspaceName}” when this is empty.`} error={errors.business_name?.message}>
        <Input id="bv-name" maxLength={80} placeholder={workspaceName} {...form.register("business_name")} />
      </Field>
      <Field
        id="bv-description"
        label="Business description"
        hint={aiCopy.businessDescriptionHint}
        error={errors.business_description?.message}
      >
        <Textarea
          id="bv-description"
          rows={3}
          maxLength={1000}
          aria-invalid={!!errors.business_description}
          {...form.register("business_description")}
        />
      </Field>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <p id="bv-tone" className="text-sm font-medium">
            Tone
          </p>
          <Controller
            control={form.control}
            name="tone"
            render={({ field }) => (
              <ToggleGroup value={field.value} onValueChange={field.onChange} aria-labelledby="bv-tone" className="flex-wrap">
                {TONE_OPTIONS.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value} className="text-xs">
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
        </div>
        <div className="space-y-1.5">
          <p id="bv-emoji" className="text-sm font-medium">
            Emoji
          </p>
          <Controller
            control={form.control}
            name="emoji_policy"
            render={({ field }) => (
              <ToggleGroup value={field.value} onValueChange={field.onChange} aria-labelledby="bv-emoji">
                {EMOJI_OPTIONS.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value} className="text-xs">
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
        </div>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Always</p>
          <Controller
            control={form.control}
            name="do_list"
            render={({ field }) => (
              <ChipListInput
                id="bv-do"
                label="Always"
                items={field.value}
                onChange={field.onChange}
                placeholder="e.g. Mention free shipping over ₹3,000"
              />
            )}
          />
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Never</p>
          <Controller
            control={form.control}
            name="dont_list"
            render={({ field }) => (
              <ChipListInput
                id="bv-dont"
                label="Never"
                items={field.value}
                onChange={field.onChange}
                placeholder="e.g. Promise delivery dates"
              />
            )}
          />
        </div>
      </div>
      <Field id="bv-signoff" label="Sign-off" hint="Added at the end of replies, e.g. “Team Maple”. Leave empty for none." error={errors.sign_off?.message}>
        <Input id="bv-signoff" maxLength={60} {...form.register("sign_off")} />
      </Field>
      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" className="bg-brand-gradient text-white" disabled={!isDirty || update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
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
