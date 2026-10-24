import { MessageSquareReply } from "lucide-react";
import Link from "next/link";
import { useId } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { moreLeads, prepareRepliesHint, prepareRepliesRequest, scoreText, stageLabel } from "@/lib/agent/leads";
import { refPath, visualPath, workspaceHref } from "@/lib/agent/routes";
import type { LeadListVisual } from "@/lib/api/types";
import { formatCount } from "@/lib/comments/format";

/**
 * VIS-08: the leads waiting for a reply, best score first (list_contacts with awaiting_reply), at
 * most 10. A row opens the conversation (a contact who never wrote opens the Contacts page); the
 * name is the customer's own text, drawn as text. A score the API has not worked out yet reads "No
 * score", never 0.
 *
 * VIS-12: "Prepare replies" asks the agent, in this thread, to draft a reply for each of the
 * `reply_ids` the API chose. The drafts come back as action cards that open each conversation with
 * its draft. Nothing is sent. It shows only when the caller can ask (the latest answer).
 */
export function LeadList({
  visual,
  slug,
  onNavigate,
  onAsk,
  busy,
}: {
  visual: LeadListVisual;
  slug: string;
  onNavigate?: () => void;
  /** Ask in the same thread; absent for older answers, where the button isn't offered. */
  onAsk?: (request: string) => void;
  /** A question is being sent, or another run in the thread is working. */
  busy?: boolean;
}) {
  const titleId = useId();
  const more = moreLeads(visual);
  const morePath = visualPath(visual.more_route);
  const canPrepare = onAsk !== undefined && visual.reply_ids.length > 0;

  return (
    <Card asChild padding="standard" className="space-y-3">
      <section aria-labelledby={titleId} data-testid="visual-lead-list">
        <CardHeader>
          <CardTitle id={titleId} className="text-sm">
            {visual.title}
          </CardTitle>
          <CardDescription>
            {visual.total === 1 ? "1 lead is waiting" : `${formatCount(visual.total)} leads are waiting`}, best score first
          </CardDescription>
        </CardHeader>
        {visual.items.length === 0 ? (
          <p className="text-sm text-fg-secondary">Nobody is waiting for a reply.</p>
        ) : (
          <ul className="divide-y divide-line-subtle" aria-label={visual.title}>
            {visual.items.map((lead) => {
              const path = lead.conversation_id
                ? refPath({ kind: "conversation", id: lead.conversation_id, label: lead.name })
                : refPath({ kind: "contact", id: lead.contact_id, label: lead.name });
              const platform = lead.platform.charAt(0).toUpperCase() + lead.platform.slice(1);
              return (
                <li key={lead.contact_id} data-testid="lead-row">
                  <Link
                    href={workspaceHref(slug, path)}
                    onClick={onNavigate}
                    className="flex min-h-11 items-center justify-between gap-3 rounded-md py-2"
                  >
                    <span className="min-w-0 space-y-0.5">
                      <span className="block truncate text-sm font-medium">{lead.name}</span>
                      <span className="block truncate text-xs text-fg-secondary">
                        {[platform, lead.last_activity_label].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <span className="text-sm font-medium tabular-nums" data-testid="lead-score">
                        {scoreText(lead.lead_score)}
                      </span>
                      <Badge tone="neutral">{stageLabel(lead.lead_stage)}</Badge>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
        {more > 0 ? (
          <p className="text-sm text-fg-secondary" data-testid="lead-more">
            {morePath ? (
              <Link href={workspaceHref(slug, morePath)} onClick={onNavigate} className="text-brand-fg underline-offset-4 hover:underline">
                +{formatCount(more)} more
              </Link>
            ) : (
              <>+{formatCount(more)} more</>
            )}
          </p>
        ) : null}
        {canPrepare ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1">
            <Button variant="soft" size="sm" disabled={busy} onClick={() => onAsk?.(prepareRepliesRequest(visual.reply_ids))}>
              <MessageSquareReply aria-hidden /> Prepare replies
            </Button>
            <span className="text-xs text-fg-secondary">{prepareRepliesHint(visual.reply_ids.length)}</span>
          </div>
        ) : null}
      </section>
    </Card>
  );
}
