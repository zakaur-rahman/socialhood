"use client";

import { ExternalLink } from "lucide-react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Skeleton } from "@/components/ui/skeleton";
import { useConversation } from "@/lib/api/queries";
import { contactName, PLATFORM_LABEL, platformContactUrl } from "@/lib/inbox/format";
import { formatDay } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ContactAvatar } from "./ContactAvatar";

function MicroLabel({ children }: { children: string }) {
  return <h2 className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">{children}</h2>;
}

/**
 * UX-INB-09 / FR-INB-11: the customer. The analysis, summary and AI sections join with P5
 * (T5.2, T5.5, T5.7); nothing is shown for them until their data exists.
 */
export function DetailsPanel({ conversationId }: { conversationId: string }) {
  const workspace = useCurrentWorkspace();
  const conversation = useConversation(workspace.id, conversationId);

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
  return (
    <div className="flex flex-col gap-5 p-4">
      <section aria-labelledby="details-customer" className="space-y-3">
        <span id="details-customer">
          <MicroLabel>Customer</MicroLabel>
        </span>
        <div className="flex items-center gap-3">
          <ContactAvatar id={c.contact.id} name={name} pictureUrl={c.contact.profile_picture_url} platform={c.platform} />
          <div className="min-w-0">
            <p className="truncate font-semibold">{name}</p>
            <p className="flex items-center gap-1 truncate text-sm text-fg-secondary">
              <PlatformGlyph platform={c.platform} className="size-3.5" />
              {c.contact.username ? `@${c.contact.username} · ` : ""}
              {platform}
            </p>
          </div>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-fg-secondary">Since</dt>
          <dd>{formatDay(c.contact.first_seen_at, workspace.timezone)}</dd>
          <dt className="text-fg-secondary">Account</dt>
          <dd className="truncate">
            {c.social_account.username ? `@${c.social_account.username}` : (c.social_account.display_name ?? platform)}
          </dd>
          {c.lead_score !== null && c.lead_score !== undefined ? (
            <>
              <dt className="text-fg-secondary">Lead score</dt>
              <dd className="tabular-nums">{c.lead_score} / 100</dd>
            </>
          ) : null}
        </dl>
        <a
          href={platformContactUrl(c.platform, c.contact)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-brand-fg underline-offset-4 hover:underline"
        >
          Open in {platform} <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </section>
    </div>
  );
}
