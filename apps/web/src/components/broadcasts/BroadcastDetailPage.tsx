"use client";

import { Pause, Play, Send, Trash2, XCircle } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  RECIPIENT_PAGE,
  useBroadcast,
  useBroadcastAction,
  useBroadcastAvailability,
  useBroadcastRecipients,
  useDeleteBroadcast,
  useStartBroadcast,
} from "@/lib/api/queries";
import type { Broadcast, RecipientStatus } from "@/lib/api/types";
import {
  BROADCAST_STATUS,
  RECIPIENT_FILTERS,
  RECIPIENT_STATUS,
  describeVariable,
  formatCount,
  formatMoney,
  percent,
  reached,
} from "@/lib/broadcasts/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";
import { CARD_TITLE, ITEM_TITLE, KPI, META } from "@/styles/tokens";
import { BroadcastsUnavailable } from "./BroadcastsPage";

type Confirm = "cancel" | "delete" | "send" | null;

/**
 * GR-23: one broadcast: where it stands, the counts at each stage, why it paused or didn't start,
 * the message and its cost estimate, and the audience in pages with each person's status. It polls
 * while the broadcast is sending, so the statuses move on their own.
 */
export function BroadcastDetailPage({ id }: { id: string }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const router = useRouter();
  const availability = useBroadcastAvailability(wid);
  const broadcast = useBroadcast(wid, id);
  const act = useBroadcastAction(wid);
  const remove = useDeleteBroadcast(wid);
  const start = useStartBroadcast(wid);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [filter, setFilter] = useState<RecipientStatus | null>(null);
  const [page, setPage] = useState(0);
  const live = broadcast.data?.status === "sending";
  const recipients = useBroadcastRecipients(wid, id, filter, page, live);

  const back = { href: `/w/${workspace.slug}/broadcasts` as Route, label: "Broadcasts" };
  if (availability.isPending) {
    return (
      <PageFrame title="Broadcast" back={back}>
        <Skeleton className="h-40 w-full" />
      </PageFrame>
    );
  }
  if (availability.data?.enabled !== true) return <BroadcastsUnavailable />;
  if (broadcast.isPending) {
    return (
      <PageFrame title="Broadcast" back={back}>
        <Skeleton className="h-40 w-full" />
      </PageFrame>
    );
  }
  if (broadcast.isError) {
    return (
      <PageFrame title="Broadcast" back={back}>
        <ErrorState error={broadcast.error} onRetry={() => void broadcast.refetch()} />
      </PageFrame>
    );
  }

  const b = broadcast.data;
  const status = BROADCAST_STATUS[b.status];
  const c = b.counts;
  const handedOver = Math.max(0, b.audience_size - c.queued);

  function run(action: "pause" | "resume" | "cancel") {
    act.mutate(
      { id, action },
      {
        onSuccess: () => toast.success(action === "pause" ? "Paused" : action === "resume" ? "Sending again" : "Cancelled"),
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <PageFrame
      title={b.name}
      back={back}
      actions={
        <>
          {b.status === "sending" ? (
            <Button variant="secondary" size="lg" onClick={() => run("pause")} loading={act.isPending}>
              <Pause aria-hidden /> Pause
            </Button>
          ) : null}
          {b.status === "paused" ? (
            <Button size="lg" onClick={() => run("resume")} loading={act.isPending}>
              <Play aria-hidden /> Resume
            </Button>
          ) : null}
          {b.status === "draft" ? (
            <Button size="lg" onClick={() => setConfirm("send")}>
              <Send aria-hidden /> Send now
            </Button>
          ) : null}
          {b.status === "scheduled" || b.status === "sending" || b.status === "paused" ? (
            <Button variant="destructive-ghost" size="lg" onClick={() => setConfirm("cancel")}>
              <XCircle aria-hidden /> Cancel
            </Button>
          ) : null}
          {b.status === "draft" || b.status === "cancelled" || b.status === "failed" ? (
            <Button variant="destructive-ghost" size="lg" onClick={() => setConfirm("delete")}>
              <Trash2 aria-hidden /> Delete
            </Button>
          ) : null}
        </>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          <p className={META}>{whenText(b, workspace.timezone)}</p>
        </div>

        {b.paused_reason && (b.status === "paused" || b.status === "failed") ? (
          <Alert tone="warning" variant="outline">
            <AlertDescription data-testid="paused-reason">{b.paused_reason}</AlertDescription>
          </Alert>
        ) : null}

        {b.status === "draft" || b.status === "scheduled" ? null : (
          <Card className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className={CARD_TITLE} id="broadcast-progress">
                  Progress
                </h2>
                <p className={META}>
                  {formatCount(handedOver)} of {formatCount(b.audience_size)} handed to WhatsApp
                </p>
              </div>
              <Progress
                aria-labelledby="broadcast-progress"
                value={handedOver}
                max={Math.max(1, b.audience_size)}
                valueText={`${formatCount(handedOver)} of ${formatCount(b.audience_size)} people`}
              />
            </div>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6" data-testid="counts">
              <Stat label="Sent" value={reached(c)} note={percent(reached(c), b.audience_size)} />
              <Stat label="Delivered" value={c.delivered + c.read} note={percent(c.delivered + c.read, b.audience_size)} />
              <Stat label="Read" value={c.read} note={percent(c.read, b.audience_size)} />
              <Stat label="Replied" value={c.replied} note={c.stopped > 0 ? `${formatCount(c.stopped)} said STOP` : undefined} />
              <Stat label="Failed" value={c.failed} tone={c.failed > 0 ? "danger" : undefined} />
              <Stat label="Skipped" value={c.skipped} note={c.queued > 0 ? `${formatCount(c.queued)} waiting` : undefined} />
            </dl>
          </Card>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="space-y-3">
            <h2 className={CARD_TITLE}>Message</h2>
            <p className="whitespace-pre-wrap rounded-lg bg-field p-3 text-sm" data-testid="template-body">
              {b.template.body}
            </p>
            <p className={META}>
              {b.template.name} ({b.template.language}), {b.template.category}
            </p>
            {b.variables.length > 0 ? (
              <ol className="space-y-0.5 text-sm">
                {b.variables.map((variable, index) => (
                  <li key={index}>
                    <span className="text-fg-secondary">Variable {index + 1}: </span>
                    {describeVariable(variable)}
                  </li>
                ))}
              </ol>
            ) : null}
          </Card>

          <Card className="space-y-3">
            <h2 className={CARD_TITLE}>Who and from where</h2>
            <p className="text-sm">
              {b.segment_name}
              {b.account_label ? ` on ${b.account_label}` : ""}
            </p>
            {b.cost ? (
              <>
                <p className="text-sm">
                  About <span className="font-semibold tabular-nums">{formatMoney(b.cost.total, b.cost.currency)}</span> from
                  Meta for {formatCount(b.audience_size)} {b.audience_size === 1 ? "person" : "people"}.
                </p>
                <p className={META}>
                  {`An estimate from Meta's rate card for India as of ${b.cost.as_of}`}
                  {b.cost.verified ? "." : " (typed in by hand, not yet checked against Meta)."} Meta bills your WhatsApp
                  Business Account directly; Social Hood charges nothing for it.
                </p>
              </>
            ) : (
              <p className={META}>The people and the cost are worked out when it starts.</p>
            )}
          </Card>
        </div>

        {b.status === "draft" || b.status === "scheduled" ? null : (
          <Card className="space-y-3 p-0">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
              <h2 className={CARD_TITLE}>People</h2>
              <ToggleGroup
                variant="chips"
                aria-label="Show"
                value={filter ?? "all"}
                onValueChange={(value) => {
                  if (!value) return;
                  setFilter(value === "all" ? null : (value as RecipientStatus));
                  setPage(0);
                }}
              >
                {RECIPIENT_FILTERS.map((option) => (
                  <ToggleGroupItem key={option.value ?? "all"} value={option.value ?? "all"}>
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>
            {recipients.isPending ? (
              <div className="space-y-2 px-4 pb-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : recipients.isError ? (
              <div className="px-4 pb-4">
                <ErrorState error={recipients.error} onRetry={() => void recipients.refetch()} size="compact" />
              </div>
            ) : recipients.data.items.length === 0 ? (
              <p className="px-4 pb-4 text-sm text-fg-secondary">No one here.</p>
            ) : (
              <ul aria-label="People" className="divide-y divide-line-subtle border-t border-line-subtle">
                {recipients.data.items.map((r) => {
                  const shown = RECIPIENT_STATUS[r.status];
                  return (
                    <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3" data-testid="recipient-row">
                      <div className="min-w-0 flex-1">
                        {r.conversation_id ? (
                          <Link
                            href={`/w/${workspace.slug}/inbox/${r.conversation_id}` as Route}
                            className={`${ITEM_TITLE} truncate underline-offset-4 hover:underline`}
                          >
                            {r.contact_name}
                          </Link>
                        ) : (
                          <p className={`${ITEM_TITLE} truncate`}>{r.contact_name}</p>
                        )}
                        {r.reason ? <p className="text-sm text-fg-secondary">{r.reason}</p> : null}
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {r.stopped ? <Badge tone="warning">Said STOP</Badge> : r.replied ? <Badge tone="brand">Replied</Badge> : null}
                        <Badge tone={shown.tone}>{shown.label}</Badge>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            {recipients.data && recipients.data.total > RECIPIENT_PAGE ? (
              <div className="flex items-center justify-between gap-2 px-4 pb-4">
                <p className={META}>
                  {formatCount(page * RECIPIENT_PAGE + 1)} to {formatCount(Math.min((page + 1) * RECIPIENT_PAGE, recipients.data.total))} of{" "}
                  {formatCount(recipients.data.total)}
                </p>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={(page + 1) * RECIPIENT_PAGE >= recipients.data.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </Card>
        )}
      </div>

      <AlertDialog open={confirm !== null} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm === "cancel" ? "Cancel this broadcast?" : confirm === "delete" ? "Delete this broadcast?" : "Send this broadcast now?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm === "cancel"
                ? "Everyone who hasn't been sent to yet is skipped. Messages already handed to WhatsApp still go out."
                : confirm === "delete"
                  ? "It is removed from the list. This can't be undone."
                  : "Everyone in the segment who agreed to marketing messages gets it. Messages already sent can't be taken back."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{confirm === "send" ? "Not yet" : "Keep it"}</AlertDialogCancel>
            <AlertDialogAction
              variant={confirm === "send" ? "default" : "destructive"}
              onClick={() => {
                if (confirm === "cancel") run("cancel");
                else if (confirm === "delete")
                  remove.mutate(id, {
                    onSuccess: () => {
                      toast.success("Broadcast deleted");
                      router.push(back.href);
                    },
                    onError: (error) => toastError(error),
                  });
                else
                  start.mutate(
                    { id },
                    { onSuccess: () => toast.success("Broadcast started"), onError: (error) => toastError(error) },
                  );
              }}
            >
              {confirm === "cancel" ? "Cancel broadcast" : confirm === "delete" ? "Delete" : "Send"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}

function whenText(b: Broadcast, timeZone: string): string {
  if (b.status === "scheduled" && b.scheduled_at) return `Goes out ${formatDayTime(b.scheduled_at, timeZone)}`;
  if (b.completed_at && (b.status === "completed" || b.status === "cancelled")) {
    return `${b.status === "completed" ? "Finished" : "Cancelled"} ${formatDayTime(b.completed_at, timeZone)}`;
  }
  if (b.started_at) return `Started ${formatDayTime(b.started_at, timeZone)}`;
  return `Saved ${formatDayTime(b.created_at, timeZone)}`;
}

function Stat({ label, value, note, tone }: { label: string; value: number; note?: string; tone?: "danger" }) {
  return (
    <div>
      <dt className={META}>{label}</dt>
      <dd className={tone === "danger" ? `${KPI} text-danger-fg` : KPI}>{formatCount(value)}</dd>
      {note ? <dd className={META}>{note}</dd> : null}
    </div>
  );
}
