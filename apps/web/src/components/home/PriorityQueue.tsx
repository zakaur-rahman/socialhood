import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardBleed, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PriorityConversation } from "@/lib/api/types";
import { contactName, ESCALATION_LABEL, PLATFORM_LABEL } from "@/lib/inbox/format";
import { relativeTime } from "@/lib/time";

import { agoLabel, formatCount } from "./format";
import { queueState } from "./rules";

function QueueRow({ item, slug, now }: { item: PriorityConversation; slug: string; now: Date }) {
  const name = contactName(item.contact, item.platform);
  const handle = item.contact.username && item.contact.username !== name ? item.contact.username : null;
  const state = queueState(item);
  const when = item.last_customer_message_at ? agoLabel(relativeTime(item.last_customer_message_at, now)) : null;
  return (
    <li data-testid="queue-row" className="flex flex-col gap-3 px-(--card-padding) py-3 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <ContactAvatar id={item.contact.id} name={name} pictureUrl={item.contact.profile_picture_url} size={32} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="font-medium">{name}</span>
            {handle ? <span className="text-fg-secondary">@{handle}</span> : null}
            <Badge data-testid="queue-platform">{PLATFORM_LABEL[item.platform]}</Badge>
            {when ? (
              <time dateTime={item.last_customer_message_at ?? undefined} className="text-xs text-fg-secondary tabular-nums">
                {when}
              </time>
            ) : null}
          </p>
          <p className="mt-0.5 truncate text-sm text-fg-secondary">
            {item.last_customer_message ? `“${item.last_customer_message}”` : "No message text"}
          </p>
          {item.needs_you && item.needs_human_reason ? (
            <p className="mt-0.5 text-xs text-danger-fg">Handed to you: {ESCALATION_LABEL[item.needs_human_reason]}</p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 pl-11 sm:pl-0">
        <Badge data-testid="queue-state" tone={state.chip.tone}>
          {state.chip.label}
        </Badge>
        <Button asChild variant={state.action === "Review & Send" ? "secondary" : "outline"}>
          <Link href={`/w/${slug}/inbox/${item.id}` as Route} aria-label={`${state.action}: ${name}`}>
            {state.action}
          </Link>
        </Button>
      </div>
    </li>
  );
}

/**
 * Home's Live Priority Queue: up to five conversations to answer first, as the API orders them
 * (services/priority_queue.py: needs you, then lead score, priority and the longest wait), and
 * Open Inbox with the Needs reply count. It refreshes with the overview on new messages, replies
 * and suggestions. The rows run to the card's edges (CardBleed).
 */
export function PriorityQueue({
  items,
  needsReply,
  slug,
  now,
}: {
  items: PriorityConversation[];
  needsReply: number;
  slug: string;
  now: Date;
}) {
  return (
    <Card asChild>
      <section aria-labelledby="home-queue">
        <CardHeader>
          <CardTitle id="home-queue">Live priority queue</CardTitle>
          <CardDescription>Conversations waiting for you, most urgent first.</CardDescription>
          <CardAction>
            <Button asChild variant="link" size="sm">
              <Link href={`/w/${slug}/inbox?view=needs_reply` as Route}>
                Open Inbox <span className="tabular-nums">({formatCount(needsReply)})</span>
                <ChevronRight aria-hidden />
              </Link>
            </Button>
          </CardAction>
        </CardHeader>
        <CardBleed className="mt-4 border-t border-line">
          {items.length === 0 ? (
            <div data-testid="queue-empty" className="px-(--card-padding) pt-4">
              {/* The queue leaves out conversations whose reply window has closed (no free-form reply
                  is possible any more), so an empty queue can sit beside a Needs reply count. Say so
                  instead of "Nothing is waiting". */}
              {needsReply > 0 ? (
                <EmptyState
                  size="compact"
                  title="No replies are possible right now."
                  body={`${formatCount(needsReply)} ${needsReply === 1 ? "conversation needs" : "conversations need"} a reply, but the reply window has closed. A free-form reply opens again when the customer writes.`}
                />
              ) : (
                <EmptyState
                  size="compact"
                  title="Nothing is waiting."
                  body="Conversations that need a reply show up here as they arrive."
                />
              )}
            </div>
          ) : (
            <ul className="divide-y divide-line-subtle">
              {items.map((item) => (
                <QueueRow key={item.id} item={item} slug={slug} now={now} />
              ))}
            </ul>
          )}
        </CardBleed>
      </section>
    </Card>
  );
}

export function PriorityQueueSkeleton() {
  return (
    <Card aria-hidden className="space-y-3">
      <Skeleton className="h-4 w-40" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </Card>
  );
}
