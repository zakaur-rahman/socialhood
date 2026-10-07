import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { PriorityConversation } from "@/lib/api/types";
import { contactName, ESCALATION_LABEL, PLATFORM_LABEL, TONE_CLASS } from "@/lib/inbox/format";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

import { agoLabel, formatCount } from "./format";
import { queueState } from "./rules";

const PLATFORM_TONE = {
  instagram: "border-instagram/40 text-fg",
  whatsapp: "border-whatsapp/40 text-fg",
} as const;

function QueueRow({ item, slug, now }: { item: PriorityConversation; slug: string; now: Date }) {
  const name = contactName(item.contact, item.platform);
  const handle = item.contact.username && item.contact.username !== name ? item.contact.username : null;
  const state = queueState(item);
  const when = item.last_customer_message_at ? agoLabel(relativeTime(item.last_customer_message_at, now)) : null;
  return (
    <li data-testid="queue-row" className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <ContactAvatar id={item.contact.id} name={name} pictureUrl={item.contact.profile_picture_url} size={32} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="font-medium">{name}</span>
            {handle ? <span className="text-fg-secondary">@{handle}</span> : null}
            <span
              data-testid="queue-platform"
              className={cn("rounded-full border px-2 text-2xs", PLATFORM_TONE[item.platform])}
            >
              {PLATFORM_LABEL[item.platform]}
            </span>
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
        <span
          data-testid="queue-state"
          className={cn("rounded-full px-2 text-2xs leading-5 font-medium", TONE_CLASS[state.chip.tone])}
        >
          {state.chip.label}
        </span>
        <Button asChild variant={state.action === "Review & Send" ? "default" : "outline"}>
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
 * and suggestions.
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
    <section aria-labelledby="home-queue" className="rounded-xl border border-line bg-panel">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line p-4">
        <div>
          <h2 id="home-queue" className="text-base font-semibold">
            Live priority queue
          </h2>
          <p className="text-xs text-fg-secondary">Conversations waiting for you, most urgent first.</p>
        </div>
        <Link
          href={`/w/${slug}/inbox?view=needs_reply` as Route}
          className="-my-1 inline-flex min-h-8 items-center gap-0.5 rounded-md text-sm font-medium text-brand-fg hover:underline pointer-coarse:min-h-10"
        >
          Open Inbox <span className="tabular-nums">({formatCount(needsReply)})</span>
          <ChevronRight className="size-4" aria-hidden />
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="p-4 text-sm text-fg-secondary" data-testid="queue-empty">
          Nothing is waiting. Conversations that need a reply show up here as they arrive.
        </p>
      ) : (
        <ul className="divide-y divide-line-subtle">
          {items.map((item) => (
            <QueueRow key={item.id} item={item} slug={slug} now={now} />
          ))}
        </ul>
      )}
    </section>
  );
}

export function PriorityQueueSkeleton() {
  return (
    <div aria-hidden className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <Skeleton className="h-4 w-40" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
