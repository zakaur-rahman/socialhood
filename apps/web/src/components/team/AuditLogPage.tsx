"use client";

import { ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuditEvents, useMembers } from "@/lib/api/queries";
import type { AuditEvent } from "@/lib/api/types";
import { PERMISSION, useCan } from "@/lib/permissions";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

const ANY = "any";
const RANGES = [
  { value: ANY, label: "Any time", hours: null },
  { value: "24h", label: "Last 24 hours", hours: 24 },
  { value: "7d", label: "Last 7 days", hours: 24 * 7 },
  { value: "30d", label: "Last 30 days", hours: 24 * 30 },
] as const;

/** "automation.created" as "Automation created". */
export function actionLabel(action: string): string {
  const words = action.replace(/[._]/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function detailText(event: AuditEvent): string {
  return Object.entries(event.detail)
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

/**
 * GR-19: Settings → Audit log. Who sent, edited or deleted what, newest first, for owners and
 * admins. Filter by member, action and how far back; page with Newer and Older. It holds names and
 * ids, never message text.
 */
export function AuditLogPage() {
  const wid = useCurrentWorkspace().id;
  const { can, ready } = useCan();
  const allowed = can(PERMISSION.readAudit);
  const members = useMembers(wid, allowed);
  const [member, setMember] = useState<string | null>(null);
  const [action, setAction] = useState<string | null>(null);
  const [range, setRange] = useState<string>(ANY);
  const [page, setPage] = useState(0);
  const hours = RANGES.find((r) => r.value === range)?.hours ?? null;
  // useNow is rounded to the minute, so the query key doesn't change on every render.
  const now = useNow();
  const since = useMemo(
    () => (hours === null ? null : new Date(now.getTime() - hours * 3_600_000).toISOString()),
    [hours, now],
  );
  const events = useAuditEvents(wid, { member, action, since, page }, allowed);

  function filter<T>(set: (value: T) => void, value: T) {
    set(value);
    setPage(0);
  }

  const items = events.data?.items ?? [];
  let content;
  if (!ready || (allowed && events.isPending)) {
    content = (
      <Card>
        <ul aria-busy="true" aria-label="Loading the audit log" className="divide-y divide-line-subtle">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="space-y-2 px-4 py-4">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </li>
          ))}
        </ul>
      </Card>
    );
  } else if (!allowed) {
    content = (
      <Card>
        <EmptyState
          size="compact"
          icon={<ScrollText />}
          title="The audit log is for owners and admins"
          body="Ask an owner or admin of this workspace what changed."
        />
      </Card>
    );
  } else if (events.isError) {
    content = <ErrorState error={events.error} onRetry={() => void events.refetch()} />;
  } else if (items.length === 0) {
    content = (
      <Card>
        <EmptyState
          size="compact"
          icon={<ScrollText />}
          title="Nothing here"
          body="No changes match these filters yet."
        />
      </Card>
    );
  } else {
    content = (
      <Card className="overflow-hidden p-0">
        <ul aria-label="Audit log" className="divide-y divide-line-subtle">
          {items.map((event) => (
            <li key={event.id} className="space-y-1 px-4 py-3" data-testid="audit-row">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="text-sm font-medium">{actionLabel(event.action)}</p>
                <time dateTime={event.at} className="text-xs text-fg-secondary">
                  {new Date(event.at).toLocaleString()}
                </time>
              </div>
              <p className="text-sm text-fg-secondary">{event.actor_name ?? "Someone who has left"}</p>
              {Object.keys(event.detail).length > 0 ? (
                <p className="break-words text-xs text-fg-secondary">{detailText(event)}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>
    );
  }

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Audit log"
          description="Who sent, edited or deleted what in this workspace. It records names and ids, never message text."
        />
      }
    >
      {allowed ? (
        <div className="mb-4 flex flex-wrap gap-2">
          <Select value={member ?? ANY} onValueChange={(value) => filter(setMember, value === ANY ? null : value)}>
            <SelectTrigger aria-label="Member" className="w-full sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Everyone</SelectItem>
              {(members.data?.items ?? []).map((m) => (
                <SelectItem key={m.user_id} value={m.user_id}>
                  {m.name ?? m.email}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={action ?? ANY} onValueChange={(value) => filter(setAction, value === ANY ? null : value)}>
            <SelectTrigger aria-label="Action" className="w-full sm:w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any action</SelectItem>
              {(events.data?.actions ?? []).map((a) => (
                <SelectItem key={a} value={a}>
                  {actionLabel(a)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={range} onValueChange={(value) => filter(setRange, value)}>
            <SelectTrigger aria-label="Date range" className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RANGES.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {content}
      {allowed && events.data && (page > 0 || events.data.has_more) ? (
        <div className="mt-4 flex justify-between gap-2">
          <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
            Newer
          </Button>
          <Button variant="secondary" disabled={!events.data.has_more} onClick={() => setPage(page + 1)}>
            Older
          </Button>
        </div>
      ) : null}
    </SettingsFrame>
  );
}
