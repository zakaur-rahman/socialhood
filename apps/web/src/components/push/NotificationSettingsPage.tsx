"use client";

import { BellRing, Mail, RotateCw } from "lucide-react";
import { useState, type ReactNode } from "react";

import { SaveBar } from "@/components/settings/SaveBar";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useNotificationPreferences, useUpdateNotificationPreferences } from "@/lib/api/queries";
import type { NotificationPreferences, PushEvent } from "@/lib/api/types";
import { PUSH_EVENT_COPY, errorMessage } from "@/lib/copy";
import type { PushBrowser } from "@/lib/push/browser";
import { useCurrentWorkspace } from "@/lib/workspace";

import { InstallPrompt } from "./InstallPrompt";
import { PushSetup } from "./PushSetup";

const PUSH_EVENTS: PushEvent[] = ["needs_you", "new_lead", "window_closing", "account"];

function SwitchRow({
  id,
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (on: boolean) => void;
}) {
  return (
    <div className="flex min-h-10 items-start justify-between gap-4 py-2.5">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <p id={`${id}-hint`} className="text-sm text-fg-secondary">
          {hint}
        </p>
      </div>
      <Switch
        id={id}
        checked={checked}
        disabled={disabled}
        aria-describedby={`${id}-hint`}
        onCheckedChange={onChange}
        className="mt-1"
      />
    </div>
  );
}

function Section({
  id,
  title,
  hint,
  icon,
  children,
}: {
  id: string;
  title: string;
  hint?: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <SettingsCard id={id} title={title} description={hint} icon={icon}>
      <div className="space-y-3">{children}</div>
    </SettingsCard>
  );
}

/**
 * UX-SCR-07 Notifications (FR-NOT-03, FR-NOT-04, F-19): the member's weekly digest switch, this
 * device's push state, and a switch per push event. The switches are the member's own, for this
 * workspace (C-049); PUT sends the whole object, and a switch that fails to save moves back.
 * C-066: the settings header and cards; switches still save as they change, so the save bar only
 * says so (saving, saved, or why the last change didn't save).
 */
export function NotificationSettingsPage({ pushBrowser }: { pushBrowser?: PushBrowser }) {
  const workspace = useCurrentWorkspace();
  const prefs = useNotificationPreferences(workspace.id);
  const update = useUpdateNotificationPreferences(workspace.id);
  const [saveError, setSaveError] = useState<string | null>(null);

  const save = (next: NotificationPreferences) => {
    setSaveError(null);
    update.mutate(next, { onError: (error) => setSaveError(errorMessage(error)) });
  };

  const loading = (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-4 w-40 bg-raised motion-reduce:animate-none" />
      <Skeleton className="h-3 w-64 max-w-full bg-raised motion-reduce:animate-none" />
    </div>
  );
  const failed = (
    <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
      <p className="flex-1 text-danger-fg">{errorMessage(prefs.error)}</p>
      <Button variant="secondary" className="min-h-10 md:min-h-8" onClick={() => void prefs.refetch()}>
        <RotateCw aria-hidden /> Try again
      </Button>
    </div>
  );

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          label="Alerts"
          title="Notifications"
          description={`Your own email digest and push alerts for ${workspace.name}. Each member chooses theirs.`}
        />
      }
    >
      <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
        <Section id="digest" title="Email" icon={<Mail />}>
          {prefs.isPending ? (
            loading
          ) : prefs.isError ? (
            failed
          ) : (
            <SwitchRow
              id="email-digest"
              label="Weekly digest"
              hint={`Mondays at 09:00 (${workspace.timezone}): messages, reply rate, response time, top questions and conversations that still need you.`}
              checked={prefs.data.email_digest}
              onChange={(on) => save({ ...prefs.data, email_digest: on })}
            />
          )}
        </Section>

        <Section
          id="push"
          title="Push notifications"
          hint="Alerts on your phone or computer, even when Social Hood isn't open."
          icon={<BellRing />}
        >
          <InstallPrompt
            storageKey="socialhood:install-dismissed"
            title="Install Social Hood"
            body="Open it from your home screen like an app, with alerts on this device."
            includeIos={false}
          />
          <PushSetup browser={pushBrowser} />
          <div className="border-t border-line-subtle pt-3">
            <p className="text-sm font-medium">Send me</p>
            <p className="text-xs text-fg-secondary">For {workspace.name}, on every device where notifications are on.</p>
            {prefs.isPending ? (
              <div className="pt-3">{loading}</div>
            ) : prefs.isError ? (
              <div className="pt-3">{failed}</div>
            ) : (
              <div className="divide-y divide-line-subtle">
                {PUSH_EVENTS.map((event) => (
                  <SwitchRow
                    key={event}
                    id={`push-${event}`}
                    label={PUSH_EVENT_COPY[event].label}
                    hint={PUSH_EVENT_COPY[event].hint}
                    checked={prefs.data.push[event]}
                    onChange={(on) => save({ ...prefs.data, push: { ...prefs.data.push, [event]: on } })}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>
      </div>
      <SaveBar dirty={false} saving={update.isPending} error={saveError} />
    </SettingsFrame>
  );
}
