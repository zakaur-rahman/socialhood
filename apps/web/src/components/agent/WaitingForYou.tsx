"use client";

import { ChevronRight } from "lucide-react";
import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useAgentApprovals } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

import { ApprovalPanel, ProposalIcon } from "./ApprovalPanel";

/**
 * GR-36: "Waiting for you", above the question box in the Ask panel and page: the writes Social
 * Hood proposed that no one has approved yet, soonest to expire first. Each row is the same
 * Approve and Reject as on the answer's card, so a proposal can be found and decided without
 * scrolling back to it. Owners and admins see every one; a team member sees their own. Shown only
 * when something is waiting; a failed load shows nothing (the answer's card still has the controls).
 */
export function WaitingForYou({
  wid,
  slug,
  timeZone,
  now,
  onNavigate,
}: {
  wid: string;
  slug: string;
  timeZone: string;
  now: Date;
  onNavigate?: () => void;
}) {
  const approvals = useAgentApprovals(wid);
  const [open, setOpen] = useState(false);
  const id = useId();
  const items = approvals.data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <section aria-label="Waiting for you" className="mb-2 rounded-xl border border-line bg-panel" data-testid="waiting-for-you">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="flex min-h-10 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-medium hover:bg-hover"
      >
        <ChevronRight className={cn("size-4 shrink-0 motion-safe:transition-transform", open && "rotate-90")} aria-hidden />
        <span className="min-w-0 flex-1 truncate">Waiting for you</span>
        <Badge tone="count" size="md" aria-label={`${items.length} waiting`}>
          {items.length}
        </Badge>
      </button>
      {open ? (
        <ul id={id} className="max-h-72 space-y-3 overflow-y-auto border-t border-line p-3">
          {items.map((approval) => (
            <li key={approval.id} className="space-y-2" data-testid="waiting-item">
              <div className="flex items-start gap-3">
                <ProposalIcon tool={approval.tool} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium break-words">{approval.summary}</p>
                  <p className="line-clamp-2 text-xs break-words text-fg-secondary">Asked: {approval.request}</p>
                </div>
              </div>
              <ul className="space-y-0.5 pl-11 text-xs text-fg-secondary" aria-label="What will happen">
                {(approval.lines ?? []).slice(0, 4).map((line, index) => (
                  <li key={`${index}:${line}`} className="break-words">
                    {line}
                  </li>
                ))}
                {(approval.lines ?? []).length > 4 ? <li>and {(approval.lines ?? []).length - 4} more</li> : null}
              </ul>
              <div className="pl-11">
                <ApprovalPanel
                  wid={wid}
                  slug={slug}
                  approval={approval}
                  timeZone={timeZone}
                  now={now}
                  onOpen={onNavigate}
                />
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
