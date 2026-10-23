"use client";

import { Clock } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useBusinessHours, useRemoveAccountHours, useSaveBusinessHours } from "@/lib/api/queries";
import type { AccountBusinessHours, BusinessHours } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { localProblem, summary, toBody, toForm, type HoursForm } from "@/lib/hours/form";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import { HoursEditor, type HoursErrors } from "./HoursEditor";

/**
 * GR-22: Settings → Business hours. The workspace's week, an away message for chats that arrive
 * while it is closed, and whether Auto mode works at any hour or only when closed. An account can
 * have its own week instead. Owners and admins edit; agents read.
 */
export function BusinessHoursPage() {
  const workspace = useCurrentWorkspace();
  const canEdit = workspace.role !== "agent";
  const hours = useBusinessHours(workspace.id);

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Business hours"
          description={`When you are open, in ${workspace.timezone}. Outside them you can send an away message and let Auto mode answer. Change the time zone in Workspace settings.`}
        />
      }
    >
      {hours.isPending ? (
        <div role="status" aria-busy="true" aria-label="Loading business hours" className="space-y-3">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : hours.isError ? (
        <ErrorState error={hours.error} onRetry={() => void hours.refetch()} />
      ) : (
        <>
          <ScheduleCard
            id="workspace-hours"
            title="Workspace hours"
            description="Used by every account that doesn't have its own."
            wid={workspace.id}
            accountId={null}
            saved={hours.data.workspace}
            timeZone={hours.data.timezone}
            canEdit={canEdit}
          />
          {hours.data.accounts.length === 0 ? (
            <EmptyState size="compact" title="No accounts yet" body="Connect an account to give it its own hours." />
          ) : (
            hours.data.accounts.map((account) => (
              <AccountCard
                key={account.social_account_id}
                wid={workspace.id}
                account={account}
                workspaceHours={hours.data.workspace}
                timeZone={hours.data.timezone}
                canEdit={canEdit}
              />
            ))
          )}
        </>
      )}
    </SettingsFrame>
  );
}

/** A form's state is reset when the saved hours change, by keying it on them. */
function signature(hours: BusinessHours | null): string {
  return JSON.stringify(hours ?? null);
}

function ScheduleCard({
  id,
  title,
  description,
  wid,
  accountId,
  saved,
  timeZone,
  canEdit,
  aside,
  footer,
}: {
  id: string;
  title: string;
  description: string;
  wid: string;
  accountId: string | null;
  saved: BusinessHours | null;
  timeZone: string;
  canEdit: boolean;
  aside?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <SettingsCard id={id} icon={<Clock />} title={title} description={description} aside={aside}>
      <ScheduleForm
        key={signature(saved)}
        idPrefix={id}
        wid={wid}
        accountId={accountId}
        saved={saved}
        timeZone={timeZone}
        canEdit={canEdit}
        footer={footer}
      />
    </SettingsCard>
  );
}

function ScheduleForm({
  idPrefix,
  wid,
  accountId,
  saved,
  timeZone,
  canEdit,
  footer,
}: {
  idPrefix: string;
  wid: string;
  accountId: string | null;
  saved: BusinessHours | null;
  timeZone: string;
  canEdit: boolean;
  footer?: React.ReactNode;
}) {
  const save = useSaveBusinessHours(wid);
  const [form, setForm] = useState<HoursForm>(() => toForm(saved));
  const [errors, setErrors] = useState<HoursErrors>({});
  const local = localProblem(form);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setErrors({});
    save.mutate(
      { accountId, body: toBody(form) },
      {
        onSuccess: () => toast.success("Business hours saved"),
        onError: (error) => {
          if (error instanceof ApiError && error.errors.length > 0) {
            setErrors(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
          } else {
            toastError(error);
          }
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <HoursEditor
        idPrefix={idPrefix}
        form={form}
        onChange={(next) => {
          setForm(next);
          setErrors({});
        }}
        errors={errors}
        disabled={!canEdit}
        timeZone={timeZone}
      />
      {canEdit ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <Button type="submit" loading={save.isPending} disabled={local !== null}>
            Save hours
          </Button>
          {local ? <p className="text-sm text-fg-secondary">{local}</p> : null}
          {footer}
        </div>
      ) : (
        <p className="text-sm text-fg-secondary">Owners and admins can change business hours.</p>
      )}
    </form>
  );
}

function AccountCard({
  wid,
  account,
  workspaceHours,
  timeZone,
  canEdit,
}: {
  wid: string;
  account: AccountBusinessHours;
  workspaceHours: BusinessHours;
  timeZone: string;
  canEdit: boolean;
}) {
  const remove = useRemoveAccountHours(wid);
  const [starting, setStarting] = useState(false);
  const label = accountLabel(account);
  const id = `account-hours-${account.social_account_id}`;
  const own = account.override;
  // A new override starts from the workspace's week, so it only needs the differences.
  const starter = useMemo<BusinessHours>(
    () => ({ ...workspaceHours, social_account_id: account.social_account_id, enabled: true }),
    [workspaceHours, account.social_account_id],
  );

  if (!own && !starting) {
    return (
      <SettingsCard
        id={id}
        icon={<Clock />}
        title={label}
        description={
          workspaceHours.enabled
            ? `Uses the workspace hours: ${summary(workspaceHours.days)}.`
            : "Uses the workspace hours, which are off, so this account is always open."
        }
        aside={
          canEdit ? (
            <Button variant="secondary" size="sm" onClick={() => setStarting(true)}>
              Set its own hours
            </Button>
          ) : null
        }
      />
    );
  }

  return (
    <ScheduleCard
      id={id}
      title={label}
      description="This account's own hours replace the workspace's."
      wid={wid}
      accountId={account.social_account_id}
      saved={own ?? starter}
      timeZone={timeZone}
      canEdit={canEdit}
      aside={own?.enabled ? <Badge tone={own.open_now ? "success" : "neutral"}>{own.open_now ? "Open now" : "Closed now"}</Badge> : null}
      footer={
        canEdit ? (
          <Button
            type="button"
            variant="ghost"
            loading={remove.isPending}
            onClick={() => {
              if (!own) return setStarting(false);
              remove.mutate(account.social_account_id, {
                onSuccess: () => {
                  setStarting(false);
                  toast.success("Back to the workspace hours");
                },
                onError: (error) => toastError(error),
              });
            }}
          >
            Use the workspace hours
          </Button>
        ) : null
      }
    />
  );
}
