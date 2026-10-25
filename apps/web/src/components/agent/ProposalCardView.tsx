"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgentApprovals } from "@/lib/api/queries";
import type { ProposalCard } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { CARD_TITLE, META } from "@/styles/tokens";

import { ApprovalPanel, ProposalIcon } from "./ApprovalPanel";

/**
 * GR-36: a write the agent proposed, in an Ask answer. It says in plain words what will happen
 * (the flow's steps, or the segment's filters and how many people match) and, beside it, whether
 * a member has approved it yet. The approval's state is read from the API, so the card is right
 * after a reload and for whoever else opens the run. Nothing is saved until Approve.
 */
export function ProposalCardView({
  card,
  wid,
  runId,
  slug,
  timeZone,
  now,
  onOpen,
}: {
  card: ProposalCard;
  wid: string | undefined;
  runId: string | undefined;
  slug: string;
  timeZone: string;
  now: Date;
  onOpen?: () => void;
}) {
  const approvals = useAgentApprovals(wid ?? "", { status: "all", runId }, Boolean(wid && runId));
  const approval = approvals.data?.items.find((item) => item.id === card.approval_id);
  const segment = card.kind === "segment_proposal";

  return (
    <Card
      asChild
      padding="standard"
      className="space-y-3 bg-hover"
    >
      <section aria-label={segment ? "Segment proposal" : "Automation proposal"} data-testid={`action-${card.kind}`}>
        <div className="flex items-start gap-3">
          <ProposalIcon tool={segment ? "propose_segment" : "propose_flow"} />
          <div className="min-w-0 flex-1">
            <h3 className={`${CARD_TITLE} break-words`}>{card.title}</h3>
            <p className={META}>{card.note ?? "Nothing is saved until you approve it."}</p>
          </div>
        </div>
        <ul className="space-y-1 text-sm" aria-label="What will happen" data-testid="proposal-lines">
          {card.lines.map((line, index) => (
            <li key={`${index}:${line}`} className="break-words">
              {line}
            </li>
          ))}
        </ul>
        {card.kind === "segment_proposal" ? (
          <p className={META} data-testid="proposal-count">
            {card.match_count === 1 ? "1 person matches" : `${card.match_count} people match`} when proposed
          </p>
        ) : null}
        {approval && wid ? (
          <ApprovalPanel wid={wid} slug={slug} approval={approval} timeZone={timeZone} now={now} onOpen={onOpen} />
        ) : approvals.isError ? (
          <p role="alert" className="text-xs text-danger-fg">
            {errorMessage(approvals.error)}
          </p>
        ) : approvals.isPending && wid ? (
          <div role="status" aria-busy="true" aria-label="Checking whether this was approved">
            <Skeleton className="h-8 w-40" />
          </div>
        ) : null}
      </section>
    </Card>
  );
}
