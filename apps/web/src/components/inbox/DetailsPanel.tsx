"use client";

import { AlertTriangle, ExternalLink, Loader2, PauseCircle } from "lucide-react";
import type { ReactNode } from "react";

import { pausedUntil } from "@/components/ai/AiModeControl";
import { AnalysisDetails } from "@/components/ai/AnalysisChips";
import { SummarySection } from "@/components/ai/SummarySection";
import { latestQuestion, useCachedMessages, useTeachAi } from "@/components/ai/TeachAi";
import type { KnowledgeUploader } from "@/components/knowledge/SourceSheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useConversation } from "@/lib/api/queries";
import type { Conversation } from "@/lib/api/types";
import { contactName, ESCALATION_LABEL, PLATFORM_LABEL, platformContactUrl } from "@/lib/inbox/format";
import { formatDay, formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ContactAvatar } from "./ContactAvatar";

const CARD = "rounded-xl border border-line bg-field/60 p-3";

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
        <h2 id={id} className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">
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
 * is set only in the thread header; a takeover pause and an escalation show here as notes.
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
        <Skeleton className="size-12 rounded-full bg-raised" />
        <Skeleton className="h-3 w-2/3 bg-raised" />
        <Skeleton className="h-3 w-1/2 bg-raised" />
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
            <a
              href={platformContactUrl(c.platform, c.contact)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-brand-fg underline-offset-4 hover:underline"
            >
              Open in {platform} <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : null
        }
      >
        <div className={cn(CARD, "space-y-3")}>
          <div className="flex items-center gap-3">
            <ContactAvatar id={c.contact.id} name={name} pictureUrl={c.contact.profile_picture_url} platform={c.platform} />
            <div className="min-w-0">
              <p className="truncate font-semibold">{name}</p>
              {c.contact.username ? <p className="truncate text-sm text-fg-secondary">@{c.contact.username}</p> : null}
              {typeof c.contact.follows_business === "boolean" ? (
                // FR-AUT-22: as Instagram reported it at the last check; nothing while unknown.
                <span
                  data-testid="follow-status"
                  className={cn(
                    "mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium",
                    c.contact.follows_business ? "bg-brand-soft text-brand-fg" : "bg-raised text-fg-secondary",
                  )}
                >
                  {c.contact.follows_business ? "Follows you" : "Doesn't follow you"}
                </span>
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
        </div>
        <Attention conversation={c} now={now} timeZone={workspace.timezone} />
      </Section>

      <Section
        id="details-analysis"
        title="Latest message"
        aside={
          teachAi.canTeach && c.latest_analysis ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs font-medium text-brand-fg hover:underline disabled:opacity-60"
              disabled={teachAi.opening}
              title="Add the customer's question to your knowledge, with your answer"
              onClick={() => {
                const { text, messageId } = latestQuestion(c, cachedMessages());
                void teachAi.teach(text, messageId);
              }}
            >
              {teachAi.opening ? <Loader2 className="size-3 animate-spin" aria-hidden /> : null}
              Teach AI
            </button>
          ) : null
        }
      >
        <div className={CARD}>
          <AnalysisDetails analysis={c.latest_analysis} conversationId={c.id} />
        </div>
      </Section>

      <Section id="details-summary" title="Summary">
        <div className={CARD}>
          <SummarySection conversation={c} now={now} />
        </div>
      </Section>
      {teachAi.sheet}
    </div>
  );
}

function LeadScore({ score }: { score: number }) {
  const lead = Math.max(0, Math.min(100, score));
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-fg-secondary">Lead score</span>
        <span className="font-medium text-brand-fg tabular-nums">{lead} / 100</span>
      </div>
      <span
        role="meter"
        aria-label="Lead score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={lead}
        className="block h-1.5 overflow-hidden rounded-full bg-raised"
      >
        <span className="bg-brand-gradient-decor block h-full rounded-full" style={{ width: `${lead}%` }} />
      </span>
    </div>
  );
}

/** Escalation and takeover, compacted: why a person is needed, and until when Auto is paused. */
function Attention({ conversation, now, timeZone }: { conversation: Conversation; now: Date; timeZone: string }) {
  const paused = pausedUntil(conversation, now);
  if (!conversation.needs_human && !paused) return null;
  const far = paused && paused.getTime() - now.getTime() > 7 * 24 * 3_600_000;
  return (
    <ul className="space-y-1.5 text-xs" aria-label="Attention">
      {conversation.needs_human ? (
        <li className="flex items-center gap-2 rounded-lg bg-danger/15 px-3 py-2 text-danger-fg">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden />
          Needs you{conversation.needs_human_reason ? `: ${ESCALATION_LABEL[conversation.needs_human_reason]}` : ""}
        </li>
      ) : null}
      {paused ? (
        <li className="flex items-center gap-2 rounded-lg bg-warning/15 px-3 py-2 text-warning">
          <PauseCircle className="size-3.5 shrink-0" aria-hidden />
          {far ? "AI paused until you resume it" : `AI paused until ${formatDayTime(paused, timeZone, now)}`}
        </li>
      ) : null}
    </ul>
  );
}
