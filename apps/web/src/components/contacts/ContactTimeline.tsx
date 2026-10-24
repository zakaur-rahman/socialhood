"use client";

import {
  AtSign,
  Flag,
  Megaphone,
  MessageCircle,
  MessageSquare,
  ShieldCheck,
  Tag,
  ListOrdered,
  UserCheck,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useContactTimeline } from "@/lib/api/queries";
import type { TimelineItem, TimelineKind } from "@/lib/api/types";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";

const ICON: Record<TimelineKind, LucideIcon> = {
  conversation: MessageCircle,
  comment: MessageSquare,
  automation_run: Zap,
  story_mention: AtSign,
  consent: ShieldCheck,
  tag: Tag,
  lead_stage: Flag,
  broadcast: Megaphone,
  assignment: UserCheck,
  sequence: ListOrdered,
};

/**
 * A contact's timeline (GR-17), newest first and read-only: their conversation, comments,
 * automation runs, story mentions, consent, tags, lead stage moves, the broadcasts they were sent (GR-23),
 * who had their conversation (GR-20) and the sequence steps they were sent or skipped (GR-24).
 * Older items load on request. Captured answers join when that feature has a table of its own.
 */
export function ContactTimeline({ contactId }: { contactId: string }) {
  const { id: wid, slug, timezone } = useCurrentWorkspace();
  const timeline = useContactTimeline(wid, contactId);
  const items = timeline.data?.pages.flatMap((page) => page.items) ?? [];

  if (timeline.isPending) {
    return (
      <div role="status" aria-label="Loading the timeline" className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  if (timeline.isError) {
    return (
      <p className="text-sm text-fg-secondary">
        The timeline did not load.{" "}
        <Button variant="link" size="xs" className="px-0" onClick={() => void timeline.refetch()}>
          Try again
        </Button>
      </p>
    );
  }
  if (items.length === 0) return <p className="text-sm text-fg-secondary">Nothing has happened with this contact yet.</p>;

  return (
    <div className="space-y-3">
      <ol aria-label="Timeline" className="space-y-3">
        {items.map((item) => (
          <TimelineRow key={item.id} item={item} slug={slug} timezone={timezone} />
        ))}
      </ol>
      {timeline.hasNextPage ? (
        <Button variant="secondary" size="sm" loading={timeline.isFetchingNextPage} onClick={() => void timeline.fetchNextPage()}>
          Show older
        </Button>
      ) : null}
    </div>
  );
}

function TimelineRow({ item, slug, timezone }: { item: TimelineItem; slug: string; timezone: string }) {
  const Icon = ICON[item.kind];
  return (
    <li data-testid="timeline-item" data-kind={item.kind} className="flex gap-3">
      <span className="mt-0.5 flex size-5 shrink-0 items-center text-fg-secondary" aria-hidden>
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 space-y-0.5 text-sm">
        <p className="font-medium break-words">{item.title}</p>
        {item.detail ? <p className="text-fg-secondary break-words">{item.detail}</p> : null}
        <p className="text-xs text-fg-secondary">
          {formatDayTime(item.occurred_at, timezone)}
          {item.conversation_id ? (
            <>
              {" · "}
              <Link
                href={`/w/${slug}/inbox/${item.conversation_id}` as Route}
                className="text-brand-fg underline-offset-4 hover:underline"
              >
                Open conversation
              </Link>
            </>
          ) : null}
        </p>
      </div>
    </li>
  );
}
