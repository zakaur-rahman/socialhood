"use client";

import { AlertTriangle, ExternalLink, PauseCircle } from "lucide-react";
import type { ReactNode } from "react";

import { pausedUntil } from "@/components/ai/AiModeControl";
import { AnalysisDetails } from "@/components/ai/AnalysisChips";
import { SummarySection } from "@/components/ai/SummarySection";
import { latestQuestion, useCachedMessages, useTeachAi } from "@/components/ai/TeachAi";
import type { KnowledgeUploader } from "@/components/knowledge/SourceSheet";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useConversation } from "@/lib/api/queries";
import type { Conversation } from "@/lib/api/types";
import { contactName, ESCALATION_LABEL, PLATFORM_LABEL, platformContactUrl } from "@/lib/inbox/format";
import { formatDay, formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";
import { EYEBROW } from "@/styles/tokens";

import { ContactAvatar } from "./ContactAvatar";

/**
 * A section's action beside its eyebrow (Open in Instagram, Teach AI): the link Button, `xs`, so
 * it is 24 px tall (40 px on coarse pointers), flush with the panel's right edge.
 */
const ASIDE_ACTION = "px-0";

function Section({
  id,
  title,
  aside,
  children,
}: {
  id: string;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-2">
      <div className="flex min-h-6 items-center justify-between gap-2">
        <h2 id={id} className={EYEBROW}>
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/**
 * The context panel (UX-INB-09, FR-INB-11, C-063): the customer, the latest message's analysis
 * (FR-AI-02, FR-AI-04) with Teach AI, and the summary with its next step (FR-AI-03). The AI mode
 * is set only in the thread header; a takeover pause and an escalation show here as notes. Each
 * section's group is a CardInset (UI-031): the panel is a pane, not a card, so its groups are inset
 * panels with a `line` edge and no fill.
 */
export function DetailsPanel({
  conversationId,
  knowledgeUpload,
}: {
  conversationId: string;
  /** Tests inject a fake for Teach AI's file sources. */
  knowledgeUpload?: KnowledgeUploader;
}) {
  const workspace = useCurrentWorkspace();
  const conversation = useConversation(workspace.id, conversationId);
  const now = useNow();
  const cachedMessages = useCachedMessages(conversationId);
  const teachAi = useTeachAi({ upload: knowledgeUpload });

  if (!conversation.data) {
    return (
      <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading details">
        <Skeleton className="size-12 rounded-full" />
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    );
  }
  const c = conversation.data;
  const name = contactName(c.contact, c.platform);
  const platform = PLATFORM_LABEL[c.platform];
  const linked = c.social_account.username ? `@${c.social_account.username}` : (c.social_account.display_name ?? platform);
  // A profile to open: an Instagram username, or a WhatsApp number.
  const profile = c.platform === "instagram" ? Boolean(c.contact.username) : Boolean(c.contact.platform_user_id);

  return (
    <div className="flex flex-col gap-5 p-4">
      <Section
        id="details-customer"
        title="Customer"
        aside={
          profile ? (
            <Button asChild variant="link" size="xs" className={ASIDE_ACTION}>
              <a href={platformContactUrl(c.platform, c.contact)} target="_blank" rel="noreferrer">
                Open in {platform} <ExternalLink aria-hidden />
              </a>
            </Button>
          ) : null
        }
      >
        <CardInset padding="compact" className="space-y-3">
          <div className="flex items-center gap-3">
            <ContactAvatar id={c.contact.id} name={name} pictureUrl={c.contact.profile_picture_url} platform={c.platform} />
            <div className="min-w-0">
              <p className="truncate font-semibold">{name}</p>
              {c.contact.username ? <p className="truncate text-sm text-fg-secondary">@{c.contact.username}</p> : null}
              {typeof c.contact.follows_business === "boolean" ? (
                // FR-AUT-22: as Instagram reported it at the last check; nothing while unknown.
                <Badge
                  tone={c.contact.follows_business ? "brand" : "neutral"}
                  className="mt-1"
                  data-testid="follow-status"
                >
                  {c.contact.follows_business ? "Follows you" : "Doesn't follow you"}
                </Badge>
              ) : null}
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-3 border-t border-line pt-3 text-sm">
            <div className="min-w-0">
              <dt className="text-xs text-fg-secondary">Customer since</dt>
              <dd className="truncate font-medium">{formatDay(c.contact.first_seen_at, workspace.timezone)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs text-fg-secondary">Linked account</dt>
              <dd className="truncate font-medium">{linked}</dd>
            </div>
          </dl>
          {c.lead_score !== null && c.lead_score !== undefined ? <LeadScore score={c.lead_score} /> : null}
        </CardInset>
        <Attention conversation={c} now={now} timeZone={workspace.timezone} />
      </Section>

      <Section
        id="details-analysis"
        title="Latest message"
        aside={
          teachAi.canTeach && c.latest_analysis ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="link"
                  size="xs"
                  className={ASIDE_ACTION}
                  loading={teachAi.opening}
                  onClick={() => {
                    const { text, messageId } = latestQuestion(c, cachedMessages());
                    void teachAi.teach(text, messageId);
                  }}
                >
                  Teach AI
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Add the customer&apos;s question to your knowledge, with your answer</TooltipContent>
            </Tooltip>
          ) : null
        }
      >
        <CardInset padding="compact">
          <AnalysisDetails analysis={c.latest_analysis} conversationId={c.id} />
        </CardInset>
      </Section>

      <Section id="details-summary" title="Summary">
        <CardInset padding="compact">
          <SummarySection conversation={c} now={now} />
        </CardInset>
      </Section>
      {teachAi.sheet}
    </div>
  );
}

/**
 * The lead score as a Meter (UI-031): `slot`, so a high score stays brand and never turns to the
 * consumable warning colours. The value text, on screen and for assistive tech, is "72 of 100".
 * TODO(UI-031 follow-up): Meter has no kind for scores, and a full slot adds "All used", which a
 * score of 100 shows too; a `score` kind (no thresholds, no full message) belongs to the primitive.
 */
function LeadScore({ score }: { score: number }) {
  const lead = Math.max(0, Math.min(100, score));
  return <Meter label="Lead score" kind="slot" value={lead} max={100} />;
}

/** Escalation and takeover, compacted: why a person is needed, and until when Auto is paused. */
function Attention({ conversation, now, timeZone }: { conversation: Conversation; now: Date; timeZone: string }) {
  const paused = pausedUntil(conversation, now);
  if (!conversation.needs_human && !paused) return null;
  const far = paused && paused.getTime() - now.getTime() > 7 * 24 * 3_600_000;
  return (
    <div className="space-y-1.5" aria-label="Attention" role="group">
      {conversation.needs_human ? (
        <Alert tone="danger" icon={<AlertTriangle />}>
          Needs you{conversation.needs_human_reason ? `: ${ESCALATION_LABEL[conversation.needs_human_reason]}` : ""}
        </Alert>
      ) : null}
      {paused ? (
        <Alert tone="warning" icon={<PauseCircle />}>
          {far ? "AI paused until you resume it" : `AI paused until ${formatDayTime(paused, timeZone, now)}`}
        </Alert>
      ) : null}
    </div>
  );
}
