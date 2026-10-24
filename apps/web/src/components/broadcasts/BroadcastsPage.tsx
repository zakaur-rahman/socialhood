"use client";

import { Megaphone, Plus } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { useBroadcastAvailability, useBroadcasts } from "@/lib/api/queries";
import type { Broadcast } from "@/lib/api/types";
import { BROADCAST_STATUS, formatCount, formatMoney, reached } from "@/lib/broadcasts/format";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";
import { META } from "@/styles/tokens";

/** The page every broadcast screen shows when the server setting is off or the call fails. */
export function BroadcastsUnavailable() {
  return (
    <PageFrame title="Broadcasts">
      <EmptyState
        icon={<Megaphone />}
        title="Broadcasts aren't available yet"
        body="We're finishing the checks that let you message people on WhatsApp in bulk. They will appear here."
      />
    </PageFrame>
  );
}

/**
 * GR-23: Broadcasts. One approved WhatsApp template sent to a saved segment of people who agreed to
 * marketing messages. Owners and admins only. Shows nothing but a plain notice while the server
 * setting is off. Meta bills the business directly for each message (PD-3), so costs here are
 * estimates, never charges.
 */
export function BroadcastsPage() {
  const workspace = useCurrentWorkspace();
  const availability = useBroadcastAvailability(workspace.id);
  const enabled = availability.data?.enabled === true;
  const list = useBroadcasts(workspace.id, enabled);

  if (availability.isPending) {
    return (
      <PageFrame title="Broadcasts">
        <Skeleton className="h-24 w-full" />
      </PageFrame>
    );
  }
  const plan = availability.data;
  if (!enabled || !plan) return <BroadcastsUnavailable />;

  return (
    <PageFrame
      title="Broadcasts"
      actions={
        plan.plan_allowed ? (
          <Button asChild size="lg">
            <Link href={`/w/${workspace.slug}/broadcasts/new` as Route}>
              <Plus aria-hidden /> New <span className="max-[359px]:sr-only">broadcast</span>
            </Link>
          </Button>
        ) : null
      }
    >
      <div className="space-y-5">
        {plan.plan_allowed ? (
          <Card className="space-y-2">
            <Meter
              label="Broadcast recipients this month"
              value={plan.used_this_period}
              max={plan.monthly_limit}
              unit="people"
            />
            <p className={META}>
              Meta charges your WhatsApp Business Account directly for each message, using the payment method you set up
              when you connected the number. Social Hood adds nothing.
            </p>
          </Card>
        ) : (
          <Alert tone="brand" variant="outline">
            <AlertTitle>Broadcasts are part of Pro</AlertTitle>
            <AlertDescription>
              Send a WhatsApp template to everyone in a segment who agreed to hear from you.{" "}
              <Link href={`/w/${workspace.slug}/settings/billing` as Route} className="text-brand-fg underline-offset-4 hover:underline">
                See plans
              </Link>
            </AlertDescription>
          </Alert>
        )}

        {list.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        ) : list.data.items.length === 0 ? (
          <Card>
            <EmptyState
              size="compact"
              icon={<Megaphone />}
              title="No broadcasts yet"
              body="Pick a segment and an approved template. People who haven't agreed to marketing messages are never sent to."
              action={
                plan.plan_allowed ? (
                  <Button asChild size="sm">
                    <Link href={`/w/${workspace.slug}/broadcasts/new` as Route}>
                      <Plus aria-hidden /> New broadcast
                    </Link>
                  </Button>
                ) : undefined
              }
            />
          </Card>
        ) : (
          <ul aria-label="Broadcasts" className="space-y-3">
            {list.data.items.map((broadcast) => (
              <li key={broadcast.id}>
                <BroadcastRow broadcast={broadcast} slug={workspace.slug} timeZone={workspace.timezone} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageFrame>
  );
}

function BroadcastRow({ broadcast, slug, timeZone }: { broadcast: Broadcast; slug: string; timeZone: string }) {
  const status = BROADCAST_STATUS[broadcast.status];
  const c = broadcast.counts;
  const when = broadcast.scheduled_at && broadcast.status === "scheduled" ? broadcast.scheduled_at : (broadcast.started_at ?? broadcast.created_at);
  return (
    <Card className="space-y-2" data-testid="broadcast-row">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/w/${slug}/broadcasts/${broadcast.id}` as Route}
          className="min-w-0 truncate text-base font-semibold underline-offset-4 hover:underline"
        >
          {broadcast.name}
        </Link>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <p className={META}>
        {broadcast.template.name} to {broadcast.segment_name}
        {broadcast.account_label ? ` from ${broadcast.account_label}` : ""} · {formatDayTime(when, timeZone)}
      </p>
      {broadcast.status === "draft" || broadcast.status === "scheduled" ? null : (
        <p className="text-sm tabular-nums">
          {formatCount(broadcast.audience_size)} people · {formatCount(reached(c))} sent · {formatCount(c.delivered + c.read)}{" "}
          delivered · {formatCount(c.read)} read · {formatCount(c.failed)} failed
          {c.replied > 0 ? ` · ${formatCount(c.replied)} replied` : ""}
        </p>
      )}
      {broadcast.paused_reason && (broadcast.status === "paused" || broadcast.status === "failed") ? (
        <p className="text-sm text-warning">{broadcast.paused_reason}</p>
      ) : null}
      {broadcast.cost ? (
        <p className={META}>
          About {formatMoney(broadcast.cost.total, broadcast.cost.currency)} from Meta (estimate)
        </p>
      ) : null}
    </Card>
  );
}
