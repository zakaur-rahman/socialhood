"use client";

import { Activity, AlertTriangle, CheckCircle2, CircleSlash, RotateCcw, Unplug } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cardVariants } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useActivity, useAutomations, useBroadcastAvailability, useRetryActivity, useSocialAccounts } from "@/lib/api/queries";
import type { ActivityFilters } from "@/lib/api/queries";
import type { ActivityItem, ActivityKind, ActivityOutcome } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

const ALL = "all";

const KINDS: { value: ActivityKind; label: string }[] = [
  { value: "automation_run", label: "Automation runs" },
  { value: "flow_step", label: "Flow steps" },
  { value: "message", label: "Messages" },
  { value: "webhook_delivery", label: "Webhooks" },
  { value: "account", label: "Accounts" },
  { value: "broadcast", label: "Broadcasts" }, // GR-23: shown only with broadcasts on
  { value: "sequence", label: "Sequences" }, // GR-24
  { value: "order", label: "Orders" }, // GR-32
];

const OUTCOME: Record<ActivityOutcome, { label: string; tone: "success" | "warning" | "danger"; icon: ReactNode }> = {
  ok: { label: "Worked", tone: "success", icon: <CheckCircle2 /> },
  failed: { label: "Failed", tone: "danger", icon: <AlertTriangle /> },
  partial: { label: "Half sent", tone: "warning", icon: <AlertTriangle /> },
  skipped: { label: "Skipped", tone: "warning", icon: <CircleSlash /> },
  attention: { label: "Needs you", tone: "danger", icon: <Unplug /> },
};

/**
 * Settings, Activity (GR-05): what automations and sends did and what failed, newest first. Each
 * row says what happened, when, the reason in a sentence and the one thing to do: a link, or Retry
 * where retrying is safe. Failures only by default; filter by automation, account or type. Owners
 * and admins (the API's activity route is admin-only). An alert's link opens it filtered to one
 * automation (?automation=).
 */
export function ActivityPage() {
  const { id: wid, slug } = useCurrentWorkspace();
  const params = useSearchParams();
  const [failuresOnly, setFailuresOnly] = useState(true);
  const [kind, setKind] = useState<ActivityKind | null>(null);
  const [automationId, setAutomationId] = useState<string | null>(params.get("automation"));
  const [accountId, setAccountId] = useState<string | null>(null);
  const broadcastsOn = useBroadcastAvailability(wid).data?.enabled === true; // GR-23
  const filters: ActivityFilters = { failuresOnly, kind, automationId, accountId };
  const filtered = Boolean(kind || automationId || accountId);

  const activity = useActivity(wid, filters);
  const accounts = useSocialAccounts(wid).data ?? [];
  const automations = useAutomations(wid, { accountId: null, status: null, trigger: null, q: "", sort: "created" });
  const items = activity.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Activity"
          description="What your automations and messages did, and why anything failed. Each problem has one thing to do about it."
        />
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={failuresOnly} onCheckedChange={setFailuresOnly} aria-label="Failures only" />
          Failures only
        </label>
        <Select value={automationId ?? ALL} onValueChange={(value) => setAutomationId(value === ALL ? null : value)}>
          <SelectTrigger aria-label="Automation" size="lg" className="max-w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All automations</SelectItem>
            {(automations.data?.items ?? []).map((automation) => (
              <SelectItem key={automation.id} value={automation.id}>
                {automation.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {accounts.length > 1 ? (
          <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
            <SelectTrigger aria-label="Account" size="lg" className="max-w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All accounts</SelectItem>
              {accounts.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {accountLabel(account)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}
        <Select value={kind ?? ALL} onValueChange={(value) => setKind(value === ALL ? null : (value as ActivityKind))}>
          <SelectTrigger aria-label="Type" size="lg">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            {KINDS.filter((option) => option.value !== "broadcast" || broadcastsOn).map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {activity.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : activity.isError ? (
        <EmptyState
          icon={<AlertTriangle />}
          title="Activity didn't load"
          body="Check your connection and try again."
          action={
            <Button variant="secondary" onClick={() => void activity.refetch()}>
              Try again
            </Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Activity />}
          title={filtered || !failuresOnly ? "Nothing here" : "Nothing has failed"}
          body={
            filtered || !failuresOnly
              ? "Nothing matches these filters."
              : "Automations and messages are running without problems. Anything that fails shows up here with the reason."
          }
        />
      ) : (
        <>
          <ul className="space-y-3" aria-label="Activity">
            {items.map((item) => (
              <ActivityRow key={`${item.kind}:${item.id}`} item={item} wid={wid} slug={slug} />
            ))}
          </ul>
          {activity.hasNextPage ? (
            <div className="flex justify-center">
              <Button variant="secondary" loading={activity.isFetchingNextPage} onClick={() => void activity.fetchNextPage()}>
                Show older
              </Button>
            </div>
          ) : null}
        </>
      )}
    </SettingsFrame>
  );
}

function ActivityRow({ item, wid, slug }: { item: ActivityItem; wid: string; slug: string }) {
  const retry = useRetryActivity(wid);
  const outcome = OUTCOME[item.outcome];
  const ago = relativeTime(item.occurred_at);
  return (
    <li className={cn(cardVariants(), "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between")}>
      <div className="flex min-w-0 gap-3">
        <span className="mt-0.5 flex size-5 shrink-0 items-center text-fg-secondary [&_svg]:size-5" aria-hidden>
          {outcome.icon}
        </span>
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{item.title}</p>
            <Badge tone={outcome.tone}>{outcome.label}</Badge>
          </div>
          {item.reason ? <p className="text-sm text-fg-secondary">{item.reason}</p> : null}
          <p className="text-xs text-fg-secondary">
            {[item.account_label, ago === "now" ? "Just now" : `${ago} ago`].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {item.retryable && item.retry ? (
          <Button
            variant="secondary"
            size="sm"
            loading={retry.isPending}
            onClick={() => retry.mutate(item, { onError: (error) => toastError(error) })}
          >
            <RotateCcw aria-hidden /> Retry
          </Button>
        ) : null}
        {item.action ? (
          <Button variant="secondary" size="sm" asChild>
            <Link href={`/w/${slug}${item.action.href}` as Route}>{item.action.label}</Link>
          </Button>
        ) : null}
      </div>
    </li>
  );
}
