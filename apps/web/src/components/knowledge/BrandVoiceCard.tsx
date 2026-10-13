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
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
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
    <Card asChild padding="roomy">
      <section aria-labelledby="brand-voice-title">
        <CardHeader>
          <CardTitle id="brand-voice-title">Brand voice</CardTitle>
          <CardDescription>How suggested and automatic replies sound.</CardDescription>
          {!open ? (
            <CardAction>
              <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <Pencil aria-hidden /> Edit
              </Button>
            </CardAction>
          ) : null}
        </CardHeader>
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
    </Card>
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
      <Field id="bv-name" invalid={!!errors.business_name}>
        <FieldLabel>Business name</FieldLabel>
        <Input maxLength={80} placeholder={workspaceName} {...form.register("business_name")} />
        <FieldDescription>Replies use “{workspaceName}” when this is empty.</FieldDescription>
        <FieldError>{errors.business_name?.message}</FieldError>
      </Field>
      <Field id="bv-description" invalid={!!errors.business_description}>
        <FieldLabel>Business description</FieldLabel>
        <Textarea rows={3} maxLength={1000} {...form.register("business_description")} />
        <FieldDescription>{aiCopy.businessDescriptionHint}</FieldDescription>
        <FieldError>{errors.business_description?.message}</FieldError>
      </Field>
      <div className="grid gap-5 md:grid-cols-2">
        <Field aria-labelledby="bv-tone">
          <Label asChild>
            <span id="bv-tone">Tone</span>
          </Label>
          <Controller
            control={form.control}
            name="tone"
            render={({ field }) => (
              // `sm`: the 12 px labels these segments had, so the four tones still fit one row at 375 px.
              <ToggleGroup
                size="sm"
                value={field.value}
                onValueChange={field.onChange}
                aria-labelledby="bv-tone"
                className="flex-wrap"
              >
                {TONE_OPTIONS.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value}>
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
        </Field>
        <Field aria-labelledby="bv-emoji">
          <Label asChild>
            <span id="bv-emoji">Emoji</span>
          </Label>
          <Controller
            control={form.control}
            name="emoji_policy"
            render={({ field }) => (
              <ToggleGroup size="sm" value={field.value} onValueChange={field.onChange} aria-labelledby="bv-emoji">
                {EMOJI_OPTIONS.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value}>
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
        </Field>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Field id="bv-do">
          <Label asChild>
            <span>Always</span>
          </Label>
          <Controller
            control={form.control}
            name="do_list"
            render={({ field }) => (
              <ChipListInput
                id="bv-do"
                label="Always"
                items={field.value}
                onChange={field.onChange}
                // Shorter than Never's, so it fits the field at 16 px on a 320 or 375 px phone.
                placeholder="e.g. Say hello first"
              />
            )}
          />
        </Field>
        <Field id="bv-dont">
          <Label asChild>
            <span>Never</span>
          </Label>
          <Controller
            control={form.control}
            name="dont_list"
            render={({ field }) => (
              <ChipListInput
                id="bv-dont"
                label="Never"
                items={field.value}
                onChange={field.onChange}
                placeholder="e.g. Promise dates"
              />
            )}
          />
        </Field>
      </div>
      <Field id="bv-signoff" invalid={!!errors.sign_off}>
        <FieldLabel>Sign-off</FieldLabel>
        <Input maxLength={60} {...form.register("sign_off")} />
        <FieldDescription>Added at the end of replies, e.g. “Team Maple”. Leave empty for none.</FieldDescription>
        <FieldError>{errors.sign_off?.message}</FieldError>
      </Field>
      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" disabled={!isDirty} loading={update.isPending}>
          Save
        </Button>
      </div>
    </form>
  );
}
