"use client";

import { Check, CircleSlash, Clock, Users, X, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DisabledReason } from "@/components/ui/disabled-reason";
import { workspaceHref } from "@/lib/agent/routes";
import { useApproveAgentApproval, useRejectAgentApproval } from "@/lib/api/queries";
import type { AgentApproval } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import type { Tone } from "@/lib/ui/tone";

export const CANT_APPROVE = "Only owners and admins can approve this, as in the app.";

const STATUS: Record<AgentApproval["status"], { label: string; tone: Tone }> = {
  pending: { label: "Waiting for approval", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
  superseded: { label: "Replaced", tone: "neutral" },
};

/** The kind of thing a proposal makes, for its icon. */
export function ProposalIcon({ tool }: { tool: string }) {
  const Icon = tool === "propose_segment" ? Users : Zap;
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand-fg" aria-hidden>
      <Icon className="size-4" />
    </span>
  );
}

/** What happened to a decided proposal, in plain words. */
function decidedLine(approval: AgentApproval, timeZone: string, now: Date): string | null {
  const who = approval.decided_by?.name ?? "A team member";
  const when = approval.decided_at ? formatDayTime(approval.decided_at, timeZone, now) : null;
  switch (approval.status) {
    case "approved":
      return approval.outcome?.summary ?? `Approved by ${who}.`;
    case "rejected":
      return `Rejected by ${who}${when ? `, ${when}` : ""}. Nothing was saved.`;
    case "expired":
      return "This expired before anyone approved it. Nothing was saved. Ask again to get it back.";
    case "superseded":
      return "A newer proposal replaced this one. Nothing was saved.";
    case "pending":
      return null;
  }
}

/**
 * GR-36: the state and the controls of one proposed write. Pending: Approve and Reject (Approve is
 * disabled, with the reason, for roles that can't do it by hand), when it expires, and, if the app
 * refused it on approval, why. Decided: what happened, with the screen the result is on.
 */
export function ApprovalPanel({
  wid,
  slug,
  approval,
  timeZone,
  now,
  onOpen,
}: {
  wid: string;
  slug: string;
  approval: AgentApproval;
  timeZone: string;
  now: Date;
  /** Leaving the panel for the result: the caller closes it. */
  onOpen?: () => void;
}) {
  const router = useRouter();
  const approve = useApproveAgentApproval(wid);
  const reject = useRejectAgentApproval(wid);
  const [error, setError] = useState<string | null>(null);
  const busy = approve.isPending || reject.isPending;
  const pending = approval.status === "pending";
  const status = STATUS[approval.status];
  const decided = decidedLine(approval, timeZone, now);
  const refused = pending && approval.outcome && !approval.outcome.ok ? approval.outcome.summary : null;
  const route = approval.status === "approved" ? approval.outcome?.route : null;

  const decide = async (action: "approve" | "reject") => {
    setError(null);
    try {
      if (action === "approve") await approve.mutateAsync({ id: approval.id });
      else await reject.mutateAsync(approval.id);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  };

  return (
    <div className="space-y-3" data-testid="approval" data-status={approval.status}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={status.tone} data-testid="approval-status">
          {status.label}
        </Badge>
        {pending ? (
          <span className="inline-flex items-center gap-1 text-xs text-fg-secondary">
            <Clock className="size-3.5" aria-hidden />
            Expires {formatDayTime(approval.expires_at, timeZone, now)}
          </span>
        ) : null}
      </div>
      {refused ? (
        <Alert tone="danger" data-testid="approval-refused">
          <AlertDescription>{refused}</AlertDescription>
        </Alert>
      ) : null}
      {decided ? (
        <p className="flex items-start gap-1.5 text-sm" data-testid="approval-result">
          {approval.status === "approved" ? (
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
          ) : (
            <CircleSlash className="mt-0.5 size-4 shrink-0 text-fg-secondary" aria-hidden />
          )}
          <span className="min-w-0 break-words">{decided}</span>
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
      {pending ? (
        <div className="flex flex-wrap items-center gap-2">
          <DisabledReason reason={approval.can_decide ? null : CANT_APPROVE}>
            <Button disabled={!approval.can_decide || busy} onClick={() => void decide("approve")}>
              <Check aria-hidden /> Approve
            </Button>
          </DisabledReason>
          <Button variant="secondary" disabled={busy} onClick={() => void decide("reject")}>
            <X aria-hidden /> Reject
          </Button>
        </div>
      ) : route ? (
        <Button
          variant="secondary"
          onClick={() => {
            onOpen?.();
            router.push(workspaceHref(slug, route));
          }}
        >
          {approval.outcome?.resource_kind === "segment" ? "Open the segment" : "Open the automation"}
        </Button>
      ) : null}
    </div>
  );
}
